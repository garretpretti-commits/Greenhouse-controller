"""
RP2040 Board Interface Module
Handles USB serial communication with RP2040-Zero boards
"""

import serial
import serial.tools.list_ports
import json
import time
import threading
from typing import Optional, Dict, Any

class RP2040Board:
    """Interface for communicating with RP2040-Zero board via USB serial"""
    
    def __init__(self, board_name: str, vendor_id: int = 0x2E8A, product_id: int = 0x0005):
        """
        Initialize RP2040 board connection
        vendor_id: Raspberry Pi RP2040 VID (0x2E8A)
        product_id: RP2040 PID (0x0005)
        """
        self.board_name = board_name
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.serial_port: Optional[serial.Serial] = None
        self.connected = False
        self.last_data = {}
        self.lock = threading.Lock()
    
    def find_port(self) -> Optional[str]:
        """Find the serial port for the RP2040 board"""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if port.vid == self.vendor_id and port.pid == self.product_id:
                return port.device
        return None
    
    def connect(self, port: Optional[str] = None, baudrate: int = 115200) -> bool:
        """Connect to the RP2040 board"""
        try:
            if port is None:
                port = self.find_port()
            
            if port is None:
                print(f"Could not find {self.board_name}")
                return False
            
            self.serial_port = serial.Serial(
                port=port,
                baudrate=baudrate,
                timeout=1,
                write_timeout=1
            )
            
            time.sleep(2)  # Wait for board to initialize
            
            # Test connection with ping
            response = self.send_command({'command': 'ping'})
            if response and response.get('status') == 'ok':
                self.connected = True
                print(f"Connected to {self.board_name} on {port}")
                return True
            else:
                print(f"Failed to ping {self.board_name}")
                return False
        
        except Exception as e:
            print(f"Error connecting to {self.board_name}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the board"""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        self.connected = False
    
    def send_command(self, command: Dict[str, Any], timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        """
        Send a command to the board and wait for response
        Returns parsed JSON response or None on error
        """
        if not self.connected or not self.serial_port:
            return None
        
        with self.lock:
            try:
                # Clear input buffer
                self.serial_port.reset_input_buffer()
                
                # Send command
                cmd_str = json.dumps(command) + '\n'
                self.serial_port.write(cmd_str.encode('utf-8'))
                self.serial_port.flush()
                
                # Wait for response
                start_time = time.time()
                response_line = ""
                
                while time.time() - start_time < timeout:
                    if self.serial_port.in_waiting > 0:
                        char = self.serial_port.read(1).decode('utf-8')
                        response_line += char
                        
                        if char == '\n':
                            try:
                                response = json.loads(response_line.strip())
                                return response
                            except json.JSONDecodeError:
                                print(f"Invalid JSON from {self.board_name}: {response_line}")
                                return None
                    
                    time.sleep(0.01)
                
                print(f"Timeout waiting for response from {self.board_name}")
                return None
            
            except Exception as e:
                print(f"Error communicating with {self.board_name}: {e}")
                return None
    
    def read_all_sensors(self) -> Optional[Dict[str, Any]]:
        """Read all sensor data from the board"""
        response = self.send_command({'command': 'read_all'})
        if response:
            self.last_data = response
        return response
    
    def set_relay(self, relay_name: str, state: bool) -> bool:
        """
        Control a relay
        relay_name: 'humidifier', 'dehumidifier', 'heater', 'light'
        state: True (ON) or False (OFF)
        """
        response = self.send_command({
            'command': 'set_relay',
            'relay': relay_name,
            'state': state
        })
        return response and response.get('success', False)
    
    def get_relay_states(self) -> Optional[Dict[str, bool]]:
        """Get current state of all relays"""
        response = self.send_command({'command': 'get_relays'})
        if response:
            return response.get('relays')
        return None


class Board1Controller:
    """High-level controller for RP2040 Board 1 (Main sensors and climate control)"""
    
    def __init__(self):
        self.board = RP2040Board("Board1")
    
    def connect(self, port: Optional[str] = None) -> bool:
        """Connect to Board 1"""
        return self.board.connect(port)
    
    def disconnect(self):
        """Disconnect from Board 1"""
        self.board.disconnect()
    
    def get_sensor_data(self) -> Dict[str, Any]:
        """Get all sensor readings"""
        data = self.board.read_all_sensors()
        if data:
            return {
                'temperature': data.get('temperature'),
                'humidity': data.get('humidity'),
                'soil_moisture': data.get('soil_moisture', {}),
                'timestamp': time.time()
            }
        return {}
    
    def get_climate_data(self) -> Dict[str, Any]:
        """Get temperature and humidity only"""
        data = self.board.read_all_sensors()
        if data:
            return {
                'temperature': data.get('temperature'),
                'humidity': data.get('humidity'),
                'timestamp': time.time()
            }
        return {}
    
    def control_climate(self, humidifier: bool, dehumidifier: bool, heater: bool) -> bool:
        """Control climate devices"""
        success = True
        success &= self.board.set_relay('humidifier', humidifier)
        success &= self.board.set_relay('dehumidifier', dehumidifier)
        success &= self.board.set_relay('heater', heater)
        return success
    
    def control_light(self, state: bool) -> bool:
        """Control grow light"""
        return self.board.set_relay('light', state)
    
    def get_relay_states(self) -> Dict[str, bool]:
        """Get current relay states"""
        return self.board.get_relay_states() or {}


# Example usage
if __name__ == "__main__":
    board1 = Board1Controller()
    
    if board1.connect():
        print("\n=== Testing Board 1 ===")
        
        # Read sensors
        print("\nSensor Data:")
        data = board1.get_sensor_data()
        print(json.dumps(data, indent=2))
        
        # Test relays
        print("\nTesting relays...")
        print("Turning light ON")
        board1.control_light(True)
        time.sleep(2)
        
        print("Turning light OFF")
        board1.control_light(False)
        
        # Get relay states
        print("\nRelay States:")
        states = board1.get_relay_states()
        print(json.dumps(states, indent=2))
        
        board1.disconnect()
    else:
        print("Failed to connect to Board 1")
