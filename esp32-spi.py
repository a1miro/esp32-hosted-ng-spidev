import json
import os
import sys
import spidev
import gpiod

CONFIG_FILE = "esp32-spi.json"

DEFAULT_CONFIG = {
    "SPI": {
        "device": "/dev/spidev5.0",
        "mode": 2,
        "clock": 1000000
    },
    "ESP32": {
        "reset": "GPIO2_IO04",
        "dataready": "GPIO2_IO12",
        "handshake": "GPIO2_IO13",
        "prog": "GPIO2_IO15",
        "firmware_builddir": "./build"
    }
}

def load_or_create_config():
    """Loads configuration from JSON file or creates a default one if missing."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Configuration file missing. Creating default {CONFIG_FILE}...")
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4)
            return DEFAULT_CONFIG
        except Exception as e:
            print(f"Error creating default config file: {e}")
            sys.exit(1)
            
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading configuration file: {e}")
        sys.exit(1)

def parse_gpio_string(gpio_str):
    """
    Parses strings like 'GPIO2_IO12' to extract chip number and line offset.
    Assumes standard NXP/Linux naming convention: GPIO<chip>_IO<line>
    """
    try:
        parts = gpio_str.split('_')
        chip_part = parts[0].replace("GPIO", "")
        line_part = parts[1].replace("IO", "")
        return int(chip_part), int(line_part)
    except (IndexError, ValueError):
        print(f"Error parsing GPIO string format: {gpio_str}. Expected format 'GPIO<chip>_IO<line>'.")
        sys.exit(1)

def main():
    # 1. Load and Parse configuration
    config = load_or_create_config()
    
    spi_cfg = config["SPI"]
    esp_cfg = config["ESP32"]
    
    print("--- Loaded Configuration ---")
    print(f"SPI Device: {spi_cfg['device']} (Mode: {spi_cfg['mode']}, Clock: {spi_cfg['clock']} Hz)")
    print(f"ESP32 Pins - Reset: {esp_cfg['reset']}, DataReady: {esp_cfg['dataready']}, Handshake: {esp_cfg['handshake']}, Prog: {esp_cfg['prog']}")
    print(f"Firmware Build Directory: {esp_cfg['firmware_builddir']}\n")

    # 2. Initialize SPI Device
    print("Initializing SPI device...")
    try:
        # Extract bus and device from e.g., '/dev/spidev5.0'
        dev_path = spi_cfg["device"]
        bus_dev = dev_path.split("spidev")[-1].split(".")
        bus = int(bus_dev[0])
        device = int(bus_dev[1])
        
        spi = spidev.SpiDev()
        spi.open(bus, device)
        spi.mode = spi_cfg["mode"]
        spi.max_speed_hz = spi_cfg["clock"]
        print("SPI interface initialized successfully.")
    except Exception as e:
        print(f"Failed to open SPI device: {e}")
        spi = None

    # 3. Initialize GPIOs using modern libgpiod (v1.x/v2.x compatible structure)
    print("\nInitializing GPIO pins via libgpiod...")
    
    # Map pin names to their intended directions
    pin_directions = {
        "reset": "output",      # Host controls ESP32 reset line
        "prog": "output",       # Host controls ESP32 programming/boot mode line
        "dataready": "input",   # Host listens to ESP32 data ready indicator
        "handshake": "input"    # Host listens to ESP32 flow control/handshake line
    }
    
    gpio_lines = {}
    gpio_chips = {}

    try:
        for pin_name, direction in pin_directions.items():
            gpio_str = esp_cfg[pin_name]
            chip_num, line_offset = parse_gpio_string(gpio_str)
            
            chip_path = f"/dev/gpiochip{chip_num}"
            
            # Re-use or open the specific gpiochip
            if chip_path not in gpio_chips:
                try:
                    gpio_chips[chip_path] = gpiod.Chip(chip_path)
                except FileNotFoundError:
                    # Fallback for systems that name chips sequentially regardless of banking names
                    fallback_path = f"/dev/gpiochip{chip_num-1}"
                    print(f"Warning: {chip_path} not found. Trying fallback path {fallback_path}...")
                    gpio_chips[chip_path] = gpiod.Chip(fallback_path)
            
            chip = gpio_chips[chip_path]
            line = chip.get_line(line_offset)
            
            # Request the line based on the direction
            # Using consumer tag for identification in 'lsgpio'
            consumer_name = f"esp32_{pin_name}"
            if direction == "output":
                line.request(consumer=consumer_name, type=gpiod.LINE_REQ_DIR_OUT, default_vals=[0])
                print(f"Configured {gpio_str} ({pin_name}) as OUTPUT (Default: 0)")
            else:
                line.request(consumer=consumer_name, type=gpiod.LINE_REQ_DIR_IN)
                print(f"Configured {gpio_str} ({pin_name}) as INPUT")
                
            gpio_lines[pin_name] = line

        # 4. Demonstrate Get/Set operations
        print("\n--- Testing GPIO Operations ---")
        
        # Toggle Reset Pin (Output)
        print("Setting Reset PIN to HIGH...")
        gpio_lines["reset"].set_value(1)
        
        # Read DataReady Pin (Input)
        dr_value = gpio_lines["dataready"].get_value()
        print(f"Read DataReady PIN value: {dr_value}")
        
        # Read Handshake Pin (Input)
        hs_value = gpio_lines["handshake"].get_value()
        print(f"Read Handshake PIN value: {hs_value}")
        
        # 5. Demonstrate SPI Data Transfer (If interface initialized)
        if spi:
            print("\n--- Testing SPI Transfer ---")
            test_data = [0xAA, 0xBB, 0xCC, 0xDD]
            print(f"Sending test bytes: {[hex(x) for x in test_data]}")
            rx_data = spi.xfer2(test_data)
            print(f"Received bytes: {[hex(x) for x in rx_data]}")

    except Exception as e:
        print(f"GPIO/SPI Operation Error: {e}")
        
    finally:
        # Clean up resources
        print("\nCleaning up hardware resources...")
        for line in gpio_lines.values():
            line.release()
        for chip in gpio_chips.values():
            chip.close()
        if spi:
            spi.close()
        print("Done.")

if __name__ == "__main__":
    main()
