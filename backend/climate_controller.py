"""
Machine Learning Climate Controller
Uses simple control logic and optional ML for greenhouse climate control
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime
import threading

class ClimateController:
    """
    Intelligent climate control system for greenhouse
    Controls humidifier, dehumidifier, and heater based on sensor readings
    """
    
    def __init__(self, board_controller, database):
        self.board = board_controller
        self.db = database
        
        # Control parameters (loaded from database)
        self.target_temp = 22.0
        self.temp_tolerance = 1.0
        self.target_humidity = 60.0
        self.humidity_tolerance = 5.0
        
        # Control state
        self.enabled = False
        self.last_action_time = 0
        self.min_action_interval = 60  # Minimum seconds between actions
        
        # Thread control
        self.control_thread = None
        self.running = False
        
        self.load_settings()
    
    def load_settings(self):
        """Load control settings from database"""
        try:
            self.target_temp = float(self.db.get_setting('target_temp', '22.0'))
            self.temp_tolerance = float(self.db.get_setting('temp_tolerance', '1.0'))
            self.target_humidity = float(self.db.get_setting('target_humidity', '60.0'))
            self.humidity_tolerance = float(self.db.get_setting('humidity_tolerance', '5.0'))
        except (ValueError, TypeError):
            print("Error loading settings, using defaults")
    
    def update_settings(self, target_temp: Optional[float] = None, 
                       temp_tolerance: Optional[float] = None,
                       target_humidity: Optional[float] = None,
                       humidity_tolerance: Optional[float] = None):
        """Update control settings"""
        if target_temp is not None:
            self.target_temp = target_temp
            self.db.set_setting('target_temp', str(target_temp))
        
        if temp_tolerance is not None:
            self.temp_tolerance = temp_tolerance
            self.db.set_setting('temp_tolerance', str(temp_tolerance))
        
        if target_humidity is not None:
            self.target_humidity = target_humidity
            self.db.set_setting('target_humidity', str(target_humidity))
        
        if humidity_tolerance is not None:
            self.humidity_tolerance = humidity_tolerance
            self.db.set_setting('humidity_tolerance', str(humidity_tolerance))
    
    def calculate_control_actions(self, temperature: float, humidity: float) -> Dict[str, bool]:
        """
        Calculate required control actions based on sensor readings
        Returns dict with relay states for humidifier, dehumidifier, heater
        """
        actions = {
            'humidifier': False,
            'dehumidifier': False,
            'heater': False
        }
        
        # Temperature control
        temp_low = self.target_temp - self.temp_tolerance
        temp_high = self.target_temp + self.temp_tolerance
        
        if temperature < temp_low:
            actions['heater'] = True
        elif temperature > temp_high:
            actions['heater'] = False
            # Could add cooling logic here if you have cooling equipment
        
        # Humidity control
        humidity_low = self.target_humidity - self.humidity_tolerance
        humidity_high = self.target_humidity + self.humidity_tolerance
        
        if humidity < humidity_low:
            actions['humidifier'] = True
            actions['dehumidifier'] = False
        elif humidity > humidity_high:
            actions['humidifier'] = False
            actions['dehumidifier'] = True
        else:
            actions['humidifier'] = False
            actions['dehumidifier'] = False
        
        return actions
    
    def apply_control_actions(self, actions: Dict[str, bool]) -> bool:
        """Apply control actions to relays"""
        try:
            success = self.board.control_climate(
                humidifier=actions['humidifier'],
                dehumidifier=actions['dehumidifier'],
                heater=actions['heater']
            )
            
            # Log actions to database
            if success:
                for relay, state in actions.items():
                    self.db.log_relay_change(relay, state, mode='auto')
            
            return success
        except Exception as e:
            print(f"Error applying control actions: {e}")
            return False
    
    def control_cycle(self):
        """Single control cycle - read sensors and apply control"""
        try:
            # Get current sensor data
            data = self.board.get_climate_data()
            
            if not data or data.get('temperature') is None or data.get('humidity') is None:
                print("Warning: Missing sensor data")
                return False
            
            temperature = data['temperature']
            humidity = data['humidity']
            
            # Calculate required actions
            actions = self.calculate_control_actions(temperature, humidity)
            
            # Apply actions (with rate limiting)
            current_time = time.time()
            if current_time - self.last_action_time >= self.min_action_interval:
                success = self.apply_control_actions(actions)
                if success:
                    self.last_action_time = current_time
                return success
            
            return True
        
        except Exception as e:
            print(f"Error in control cycle: {e}")
            return False
    
    def control_loop(self):
        """Main control loop (runs in separate thread)"""
        print("Climate controller started")
        
        while self.running:
            try:
                if self.enabled:
                    # Reload settings periodically
                    self.load_settings()
                    
                    # Execute control cycle
                    self.control_cycle()
                
                # Sleep between cycles
                time.sleep(10)  # Check every 10 seconds
            
            except Exception as e:
                print(f"Error in control loop: {e}")
                time.sleep(30)  # Wait longer on error
        
        print("Climate controller stopped")
    
    def start(self):
        """Start automatic climate control"""
        if not self.running:
            self.running = True
            self.enabled = True
            self.control_thread = threading.Thread(target=self.control_loop, daemon=True)
            self.control_thread.start()
            self.db.set_setting('mode', 'auto')
            print("Climate control enabled")
    
    def stop(self):
        """Stop automatic climate control"""
        self.enabled = False
        self.db.set_setting('mode', 'manual')
        print("Climate control disabled")
    
    def shutdown(self):
        """Shutdown the controller thread"""
        self.enabled = False
        self.running = False
        if self.control_thread:
            self.control_thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current controller status"""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'target_temp': self.target_temp,
            'temp_tolerance': self.temp_tolerance,
            'target_humidity': self.target_humidity,
            'humidity_tolerance': self.humidity_tolerance,
            'last_action_time': self.last_action_time
        }


class LightScheduler:
    """Schedule-based light controller"""
    
    def __init__(self, board_controller, database):
        self.board = board_controller
        self.db = database
        self.enabled = False
        self.running = False
        self.scheduler_thread = None
        
        # Load schedule from database
        self.schedule = self.db.get_light_schedule()
        if not self.schedule:
            # Default schedule: 6 AM to 10 PM
            self.schedule = {
                'enabled': False,
                'on_time': '06:00',
                'off_time': '22:00'
            }
            self.db.set_light_schedule(
                self.schedule['on_time'],
                self.schedule['off_time'],
                self.schedule['enabled']
            )
    
    def set_schedule(self, on_time: str, off_time: str, enabled: bool = True):
        """Set light schedule (HH:MM format)"""
        self.schedule = {
            'enabled': enabled,
            'on_time': on_time,
            'off_time': off_time
        }
        self.db.set_light_schedule(on_time, off_time, enabled)
        self.enabled = enabled
    
    def should_light_be_on(self) -> bool:
        """Check if light should be on based on schedule"""
        if not self.schedule['enabled']:
            return False
        
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        on_time = self.schedule['on_time']
        off_time = self.schedule['off_time']
        
        # Handle schedules that cross midnight
        if on_time < off_time:
            return on_time <= current_time < off_time
        else:
            return current_time >= on_time or current_time < off_time
    
    def scheduler_loop(self):
        """Main scheduler loop"""
        print("Light scheduler started")
        last_state = None
        
        while self.running:
            try:
                if self.enabled:
                    should_be_on = self.should_light_be_on()
                    
                    # Only change state if different from last state
                    if should_be_on != last_state:
                        self.board.control_light(should_be_on)
                        self.db.log_relay_change('light', should_be_on, mode='schedule')
                        last_state = should_be_on
                        print(f"Light {'ON' if should_be_on else 'OFF'} (schedule)")
                
                time.sleep(30)  # Check every 30 seconds
            
            except Exception as e:
                print(f"Error in light scheduler: {e}")
                time.sleep(60)
        
        print("Light scheduler stopped")
    
    def start(self):
        """Start light scheduler"""
        if not self.running:
            self.enabled = self.schedule['enabled']
            self.running = True
            self.scheduler_thread = threading.Thread(target=self.scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            self.db.set_setting('light_mode', 'schedule')
            print("Light scheduler enabled")
    
    def stop(self):
        """Stop light scheduler"""
        self.enabled = False
        self.db.set_setting('light_mode', 'manual')
        print("Light scheduler disabled")
    
    def shutdown(self):
        """Shutdown the scheduler thread"""
        self.enabled = False
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status"""
        return {
            'enabled': self.enabled,
            'running': self.running,
            'schedule': self.schedule,
            'current_state': self.should_light_be_on()
        }
