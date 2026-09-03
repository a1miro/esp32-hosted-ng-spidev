# ESP32 SPI & GPIO Controller

A robust Python 3 script for interfacing with an ESP32 module over Linux SPI (`/dev/spidev`) and GPIO (`libgpiod`) subsystems. The application dynamically parses hardware parameters from a JSON configuration file, handles modern Linux GPIO character device abstractions, and manages safe hardware lifecycles.

## Features

- **Automated Configuration**: Generates a default `config.json` if missing.
- **Modern GPIO Integration**: Uses `libgpiod` character device APIs instead of deprecated sysfs wrappers.
- **Dynamic Bank Parsing**: Translates standard NXP/IMX string patterns (e.g., `GPIO2_IO12`) directly into kernel hardware offsets.
- **Hardware Lifecycle Safety**: Employs structural exception guards to guarantee pins release cleanly on crash or termination.

---

## Hardware Pin Mapping Reference

The application defaults to the following hardware definitions parsed directly from `config.json`:

| Subsystem | Parameter | Default Value | Target / Hardware Pin | Direction / Mode |
| :--- | :--- | :--- | :--- | :--- |
| **SPI** | Device Path | `/dev/spidev5.0` | Physical SPI Bus 5 | Master |
| **SPI** | Mode | `2` | Clock High (`CPOL=1`, `CPHA=0`) | Bi-directional |
| **SPI** | Speed | `1000000` (1 MHz) | Clock Frequency | - |
| **ESP32 Control** | `reset` | `GPIO2_IO04` | `/dev/gpiochip2`, Offset `4` | Output (Active Low Init) |
| **ESP32 Control** | `prog` | `GPIO2_IO15` | `/dev/gpiochip2`, Offset `15` | Output (Active Low Init) |
| **ESP32 Status** | `dataready` | `GPIO2_IO12` | `/dev/gpiochip2`, Offset `12` | Input |
| **ESP32 Status** | `handshake` | `GPIO2_IO13` | `/dev/gpiochip2`, Offset `13` | Input |

---

## System Requirements & Prerequisites

### 1. Hardware Access Rights
Interfacing with the Linux kernel character devices requires elevated hardware permissions. Ensure your user belongs to both `gpio` and `spi` groups, or execute the script using administrative flags (`sudo`).

### 2. Operating System Packages
Install the required native compiler tools and system-level bindings:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-spidev python3-gpiod
```

*Note: If `python3-gpiod` is unavailable via your package manager, install development libraries (`sudo apt-get install libgpiod-dev`) and compile via pip: `pip3 install gpiod`.*

---

## Installation & Execution

### 1. Project Setup
Clone or place the script file `esp32_spi_gpio.py` and your firmware directory structure inside your working directory:
```bash
mkdir -p build
```

### 2. Run the Interface Script
Execute the program to generate the default configuration and initialize communication:
```bash
sudo python3 esp32_spi_gpio.py
```

### 3. Customizing Parameter Maps
Modify `config.json` directly to remap hardware buses or pin structures. The script reloads these metrics every runtime initialization loop:
```json
{
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
```

---

## Architecture Flow

1. **Bootstrap Phase**: The runtime checks for `config.json`. If missing, it writes your precise target parameters to disk.
2. **Translation Engine**: The parser separates `GPIO2_IO12` using internal regex structures into chip target `/dev/gpiochip2` and raw offset entry `12`.
3. **GPIO Lock Execution**: Pins are claimed through `gpiod`. Outputs initialize into safe operational bounds.
4. **SPI Allocation**: The `spidev` device opens, claims exclusive clock metrics, and establishes structural configurations.
5. **Execution Loop**: Performs read/write transactions.
6. **Destruction Guard**: Intercepted interrupts execute `line.release()` operations, preventing target pins from remaining locked in the kernel state if the application closes unexpectedly.

