"""
RP2040-Zero Board 1 - Greenhouse Controller
Handles: DHT22, 4x Soil Moisture Sensors, 4x Relays (Humidifier, Dehumidifier, Heater, Light)

Wiring:
- GPIO13: DHT22 data
- GPIO27: Soil sensors 1&2 data (shared)
- GPIO26: Soil sensors 3&4 data (shared)
- GPIO15,14,6,8: Transistor switches for soil sensor selection
- GPIO12: Humidifier relay (active low)
- GPIO11: Dehumidifier relay (active low)
- GPIO10: Heater relay (active low)
- GPIO9: Light relay (active low)
"""

import board
import digitalio
import time
import adafruit_dht
import analogio
import json
import usb_cdc

# Initialize DHT22 sensor
dht_sensor = adafruit_dht.DHT22(board.GP13, use_pulseio=False)

# Soil sensor data pins (analog)
soil_data_pin1 = analogio.AnalogIn(board.GP27)  # Sensors 1 & 2
soil_data_pin2 = analogio.AnalogIn(board.GP26)  # Sensors 3 & 4

# Transistor switches for soil sensor selection (active low)
soil_switches = {
    1: digitalio.DigitalInOut(board.GP15),
    2: digitalio.DigitalInOut(board.GP14),
    3: digitalio.DigitalInOut(board.GP6),
    4: digitalio.DigitalInOut(board.GP8)
}

# Initialize soil sensor switches
for switch in soil_switches.values():
    switch.direction = digitalio.Direction.OUTPUT
    switch.value = True  # High = OFF (not selected)

# Relay pins (active low - LOW = ON, HIGH = OFF)
relays = {
    'humidifier': digitalio.DigitalInOut(board.GP12),
    'dehumidifier': digitalio.DigitalInOut(board.GP11),
    'heater': digitalio.DigitalInOut(board.GP10),
    'light': digitalio.DigitalInOut(board.GP9)
}

# Initialize relays (all OFF initially)
for relay in relays.values():
    relay.direction = digitalio.Direction.OUTPUT
    relay.value = True  # High = OFF

# Serial communication
serial = usb_cdc.data

def read_dht22():
    """Read temperature and humidity from DHT22"""
    try:
        temperature = dht_sensor.temperature
        humidity = dht_sensor.humidity
        return {
            'temperature': round(temperature, 1),
            'humidity': round(humidity, 1),
            'status': 'ok'
        }
    except Exception as e:
        return {
            'temperature': None,
            'humidity': None,
            'status': f'error: {str(e)}'
        }

def read_soil_moisture(sensor_num):
    """
    Read soil moisture from specified sensor (1-4)
    Uses transistor switching to select the correct sensor
    """
    if sensor_num not in [1, 2, 3, 4]:
        return None
    
    # Turn off all switches first
    for switch in soil_switches.values():
        switch.value = True
    
    time.sleep(0.01)  # Small delay for switching
    
    # Select the target sensor (active low)
    soil_switches[sensor_num].value = False
    time.sleep(0.05)  # Wait for sensor to stabilize
    
    # Read from appropriate data pin
    if sensor_num in [1, 2]:
        raw_value = soil_data_pin1.value
    else:  # sensor 3 or 4
        raw_value = soil_data_pin2.value
    
    # Turn off the switch
    soil_switches[sensor_num].value = True
    
    # Convert to percentage (0-65535 raw to 0-100%)
    # Capacitive sensors: higher value = drier soil
    # Adjust these calibration values based on your sensors
    moisture_percent = 100 - ((raw_value / 65535) * 100)
    
    return round(moisture_percent, 1)

def read_all_soil_sensors():
    """Read all 4 soil moisture sensors"""
    return {
        'soil1': read_soil_moisture(1),
        'soil2': read_soil_moisture(2),
        'soil3': read_soil_moisture(3),
        'soil4': read_soil_moisture(4)
    }

def set_relay(relay_name, state):
    """
    Control relay state
    relay_name: 'humidifier', 'dehumidifier', 'heater', 'light'
    state: True (ON) or False (OFF)
    Active low logic: LOW = ON, HIGH = OFF
    """
    if relay_name in relays:
        relays[relay_name].value = not state  # Invert for active low
        return True
    return False

def get_relay_states():
    """Get current state of all relays"""
    return {
        'humidifier': not relays['humidifier'].value,
        'dehumidifier': not relays['dehumidifier'].value,
        'heater': not relays['heater'].value,
        'light': not relays['light'].value
    }

def process_command(cmd):
    """Process commands from Raspberry Pi"""
    try:
        data = json.loads(cmd)
        command = data.get('command')
        
        if command == 'read_all':
            # Read all sensors
            dht_data = read_dht22()
            soil_data = read_all_soil_sensors()
            relay_states = get_relay_states()
            
            response = {
                'temperature': dht_data['temperature'],
                'humidity': dht_data['humidity'],
                'soil_moisture': soil_data,
                'relays': relay_states,
                'status': 'ok'
            }
            return json.dumps(response)
        
        elif command == 'set_relay':
            relay_name = data.get('relay')
            state = data.get('state')
            success = set_relay(relay_name, state)
            return json.dumps({
                'command': 'set_relay',
                'relay': relay_name,
                'state': state,
                'success': success
            })
        
        elif command == 'get_relays':
            return json.dumps({
                'relays': get_relay_states(),
                'status': 'ok'
            })
        
        elif command == 'ping':
            return json.dumps({'status': 'ok', 'board': 'rp2040_board1'})
        
        else:
            return json.dumps({'error': 'unknown_command'})
    
    except Exception as e:
        return json.dumps({'error': str(e)})

# Main loop
print("RP2040 Board 1 - Greenhouse Controller Started")
buffer = ""

while True:
    # Check for incoming serial data
    if serial and serial.in_waiting > 0:
        try:
            incoming = serial.read(serial.in_waiting)
            buffer += incoming.decode('utf-8')
            
            # Process complete commands (ended with newline)
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                line = line.strip()
                
                if line:
                    response = process_command(line)
                    serial.write((response + '\n').encode('utf-8'))
        
        except Exception as e:
            error_msg = json.dumps({'error': f'serial_error: {str(e)}'})
            serial.write((error_msg + '\n').encode('utf-8'))
    
    time.sleep(0.01)  # Small delay to prevent CPU hogging
