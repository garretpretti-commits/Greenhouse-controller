# RP2040 Board 1 Setup Instructions

## Hardware Connections

### Power
- 5V → Relay board power
- 3V → DHT22 VCC
- GND → DHT22 GND, Relay board GND, Soil sensors GND

### Sensors
- **GPIO13** → DHT22 Data Pin
- **GPIO27** → Soil Sensors 1 & 2 Data (shared via analog input)
- **GPIO26** → Soil Sensors 3 & 4 Data (shared via analog input)

### Soil Sensor Selection (Transistor Switches)
- **GPIO15** → Soil Sensor 1 selector (active low)
- **GPIO14** → Soil Sensor 2 selector (active low)
- **GPIO6** → Soil Sensor 3 selector (active low)
- **GPIO8** → Soil Sensor 4 selector (active low)

### Relays (Active Low Logic)
- **GPIO12** → Humidifier Relay (LOW = ON, HIGH = OFF)
- **GPIO11** → Dehumidifier Relay (LOW = ON, HIGH = OFF)
- **GPIO10** → Heater Relay (LOW = ON, HIGH = OFF)
- **GPIO9** → Light Relay (LOW = ON, HIGH = OFF)

## Software Setup

### 1. Install CircuitPython on RP2040-Zero

1. Download CircuitPython for RP2040:
   - Go to: https://circuitpython.org/board/raspberry_pi_pico/
   - Download the latest .UF2 file

2. Enter bootloader mode:
   - Hold BOOT button on RP2040-Zero
   - While holding, plug USB cable into Raspberry Pi
   - Release BOOT button
   - RP2040 should appear as USB drive "RPI-RP2"

3. Copy CircuitPython .UF2 file to the drive
   - Board will reboot and appear as "CIRCUITPY"

### 2. Install Required Libraries

1. Download CircuitPython Library Bundle:
   - Go to: https://circuitpython.org/libraries
   - Download the bundle matching your CircuitPython version

2. Extract and copy these libraries to `CIRCUITPY/lib/`:
   - `adafruit_dht.mpy`
   - Or the entire `adafruit_dht` folder if .mpy not available

### 3. Upload Code

1. Copy `code.py` to the root of CIRCUITPY drive:
   ```bash
   cp rp2040_board1/code.py /media/pi/CIRCUITPY/
   ```

2. Board will automatically restart and run the code

### 4. Verify Connection

Test communication from Raspberry Pi:

```bash
python3 backend/rp2040_interface.py
```

This should:
- Find the RP2040 board
- Connect via USB serial
- Read sensor data
- Test relay control

## Quick Command Reference

```bash
# Find RP2040 USB device
ls /dev/ttyACM*

# Monitor serial output (debugging)
screen /dev/ttyACM0 115200

# Check if board is recognized
lsusb | grep 2e8a
```

## Troubleshooting

### Board not found
- Check USB cable is data-capable (not charge-only)
- Verify CircuitPython is installed: `ls /media/pi/CIRCUITPY`
- Check USB connection: `lsusb | grep "2e8a"`

### Sensor errors
- Verify DHT22 wiring (Data on GPIO13)
- Check soil sensor power and ground connections
- Ensure transistor switches are wired correctly

### Relays not working
- Verify active-low logic (LOW = ON)
- Check relay board power (5V connection)
- Test relay manually: `echo '{"command":"set_relay","relay":"light","state":true}' > /dev/ttyACM0`

### Serial communication issues
- Ensure only one program is accessing the serial port
- Check permissions: `sudo usermod -a -G dialout pi`
- Reboot after adding to dialout group

## Calibration

### Soil Moisture Sensors

The capacitive soil moisture sensors need calibration:

1. **Dry reading**: Leave sensor in open air, note the percentage
2. **Wet reading**: Submerge sensor in water (don't submerge electronics!), note percentage

3. Adjust in `code.py` around line 108:
   ```python
   # Adjust these values based on your calibration
   DRY_VALUE = 65535  # Raw value in air
   WET_VALUE = 20000  # Raw value in water
   moisture_percent = 100 - ((raw_value - WET_VALUE) / (DRY_VALUE - WET_VALUE)) * 100
   ```

## Communication Protocol

The board responds to JSON commands over USB serial:

### Commands

**Read all sensors:**
```json
{"command": "read_all"}
```

**Set relay:**
```json
{"command": "set_relay", "relay": "humidifier", "state": true}
```

**Get relay states:**
```json
{"command": "get_relays"}
```

**Ping:**
```json
{"command": "ping"}
```

### Responses

All responses are JSON format:

```json
{
  "temperature": 22.5,
  "humidity": 65.0,
  "soil_moisture": {
    "soil1": 45.2,
    "soil2": 52.1,
    "soil3": 38.9,
    "soil4": 41.5
  },
  "relays": {
    "humidifier": false,
    "dehumidifier": false,
    "heater": false,
    "light": true
  },
  "status": "ok"
}
```
