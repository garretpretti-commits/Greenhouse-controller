"""
Machine Learning Climate Controller
Uses simple control logic and ML predictions for greenhouse climate control
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime
import threading

try:
    from ml_climate_predictor import MLClimatePredictor
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: ML predictor not available, using basic control only")

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
        self.temp_tolerance = 0.5
        self.target_humidity = 60.0
        self.humidity_tolerance = 5.0
        
        # Temperature schedule
        self.temp_schedule_enabled = False
        self.temp_schedule = None
        
        # Control state
        self.enabled = False
        self.use_ml = False  # Disable ML by default - use simple control
        self.last_action_time = time.time()
        self.min_action_interval = 30  # Minimum seconds between actions
        
        # Adaptive duty cycling parameters
        self.relay_on_times = {}  # Track when each relay turned on
        self.relay_off_times = {}  # Track when each relay turned off
        self.relay_effectiveness = {}  # Track if relay is making progress
        self.last_sensor_values = {}  # Track sensor history for rate of change
        
        # Track last known relay states to avoid redundant logging
        self.last_relay_states = {
            'humidifier': None,
            'dehumidifier': None,
            'heater': None
        }
        
        # ML predictor - disabled for simplicity
        self.ml_predictor = None
        # ML features disabled - using simple reactive control only
        print("Using simple reactive climate control (ML disabled)")
        
        # Thread control
        self.control_thread = None
        self.running = False
        
        self.load_settings()
    
    def load_settings(self):
        """Load control settings from database"""
        try:
            self.target_temp = float(self.db.get_setting('target_temp', '22.0'))
            self.temp_tolerance = float(self.db.get_setting('temp_tolerance', '0.5'))
            self.target_humidity = float(self.db.get_setting('target_humidity', '60.0'))
            self.humidity_tolerance = float(self.db.get_setting('humidity_tolerance', '5.0'))
            self.use_ml = self.db.get_setting('use_ml', 'False').lower() == 'true'
            
            # Load temperature schedule
            temp_schedule = self.db.get_temp_schedule()
            if temp_schedule:
                self.temp_schedule_enabled = temp_schedule['enabled']
                self.temp_schedule = temp_schedule['periods']
            
            # Update target temp from schedule if enabled
            if self.temp_schedule_enabled and self.temp_schedule:
                scheduled_temp = self.get_scheduled_temperature()
                if scheduled_temp is not None:
                    self.target_temp = scheduled_temp
        except (ValueError, TypeError):
            print("Error loading settings, using defaults")
    
    def get_scheduled_temperature(self) -> Optional[float]:
        """Get the current scheduled temperature based on time of day"""
        if not self.temp_schedule or len(self.temp_schedule) == 0:
            return None
        
        now = datetime.now()
        current_time = now.strftime('%H:%M')
        
        # Sort periods by time
        sorted_periods = sorted(self.temp_schedule, key=lambda x: x['time'])
        
        # Find the active period
        active_temp = None
        for i, period in enumerate(sorted_periods):
            if current_time >= period['time']:
                active_temp = period['temperature']
            else:
                break
        
        # If no period found, use the last period of the day (wraps to next day)
        if active_temp is None and len(sorted_periods) > 0:
            active_temp = sorted_periods[-1]['temperature']
        
        return active_temp
    
    def update_settings(self, target_temp: Optional[float] = None, 
                       temp_tolerance: Optional[float] = None,
                       target_humidity: Optional[float] = None,
                       humidity_tolerance: Optional[float] = None,
                       use_ml: Optional[bool] = None):
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
        
        if use_ml is not None:
            self.use_ml = use_ml
            self.db.set_setting('use_ml', str(use_ml))
    
    def calculate_control_actions(self, temperature: float, humidity: float, relay_states: Optional[Dict[str, bool]] = None) -> Dict[str, bool]:
        """
        Calculate required control actions based on sensor readings
        Uses simple reactive control logic
        Returns dict with relay states for humidifier, dehumidifier, heater
        """
        actions = {
            'humidifier': False,
            'dehumidifier': False,
            'heater': False
        }
        
        # Get current relay states if not provided
        if relay_states is None:
            try:
                relay_states = self.board.get_relay_states()
            except:
                relay_states = actions.copy()
        
        # Simple temperature control (no ML)
        temp_low = self.target_temp - self.temp_tolerance
        temp_high = self.target_temp + self.temp_tolerance
        
        # Simple reactive control
        if temperature < temp_low:
            actions['heater'] = True
            print(f"[CONTROL] Temp: {temperature:.1f}°C ({temperature*9/5+32:.1f}°F) < {temp_low:.1f}°C - Heater ON")
        elif temperature >= self.target_temp:
            actions['heater'] = False
            if temperature > temp_high:
                print(f"[CONTROL] Temp: {temperature:.1f}°C > {temp_high:.1f}°C - Heater OFF")
        
        # Simple humidity control
        humidity_low = self.target_humidity - self.humidity_tolerance
        humidity_high = self.target_humidity + self.humidity_tolerance
        
        # Simple reactive control
        if humidity < humidity_low:
            actions['humidifier'] = True
            actions['dehumidifier'] = False
            print(f"[CONTROL] Humidity: {humidity:.1f}% < {humidity_low:.1f}% - Humidifier ON")
        elif humidity >= self.target_humidity:
            actions['humidifier'] = False
            if humidity > humidity_high:
                actions['dehumidifier'] = True
                print(f"[CONTROL] Humidity: {humidity:.1f}% > {humidity_high:.1f}% - Dehumidifier ON")
            else:
                actions['dehumidifier'] = False
        else:
            actions['dehumidifier'] = False
        
        return actions
    
    def calculate_adaptive_cycle_times(self, temperature: float, humidity: float) -> Dict[str, Dict[str, float]]:
        """
        Simple fixed cycle times for reliable operation
        Returns dict with min_on_time and min_off_time for each relay
        """
        # Simple fixed cycle times
        # Minimum 3 minutes on, 2 minutes off for all devices
        # This prevents rapid cycling while being responsive
        cycle_times = {
            'heater': {'min_on': 180, 'min_off': 120},        # 3 min on, 2 min off
            'humidifier': {'min_on': 180, 'min_off': 120},    # 3 min on, 2 min off
            'dehumidifier': {'min_on': 180, 'min_off': 120}   # 3 min on, 2 min off
        }
        
        return cycle_times
    
    def check_relay_effectiveness(self, relay: str, temperature: float, humidity: float) -> bool:
        """
        Simple effectiveness check - always return True for simpler operation
        Can be enhanced later if needed
        """
        return True
    
    def apply_control_actions(self, actions: Dict[str, bool], temperature: float = None, humidity: float = None) -> bool:
        """Apply control actions to relays with simple timing protection"""
        try:
            # Use provided sensor data or fetch it
            if temperature is None or humidity is None:
                try:
                    data = self.board.get_climate_data()
                    temperature = data.get('temperature', self.target_temp)
                    humidity = data.get('humidity', self.target_humidity)
                except:
                    temperature = self.target_temp
                    humidity = self.target_humidity
            
            # Get simple cycle times
            cycle_times = self.calculate_adaptive_cycle_times(temperature, humidity)
            
            current_time = time.time()
            modified_actions = actions.copy()
            
            # Safety limits
            MAX_RUNTIME = 3600  # 1 hour maximum
            MIN_COOLDOWN = 600  # 10 minutes minimum cooldown after max runtime
            
            # Apply simple timing protection for each relay
            for relay in ['heater', 'humidifier', 'dehumidifier']:
                desired_state = actions.get(relay, False)
                current_state = self.last_relay_states.get(relay)
                
                # IMMEDIATE SHUTOFF if target reached
                if current_state is True:
                    should_shutoff = False
                    if relay == 'heater' and temperature >= self.target_temp:
                        should_shutoff = True
                    elif relay == 'humidifier' and humidity >= self.target_humidity:
                        should_shutoff = True
                    elif relay == 'dehumidifier' and humidity <= self.target_humidity:
                        should_shutoff = True
                    
                    if should_shutoff:
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        print(f"{relay.capitalize()} target reached, turning OFF")
                        continue
                
                min_on = cycle_times[relay]['min_on']
                min_off = cycle_times[relay]['min_off']
                
                # Safety: Check max runtime for heater and humidifier
                if current_state is True and relay in ['heater', 'humidifier']:
                    last_on = self.relay_on_times.get(relay, current_time)
                    time_on = current_time - last_on
                    
                    if time_on >= MAX_RUNTIME:
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        print(f"{relay.capitalize()} SAFETY: Max runtime (1hr) reached, forcing OFF")
                        continue
                
                # Turning ON
                if desired_state and not current_state:
                    last_off = self.relay_off_times.get(relay, 0)
                    time_off = current_time - last_off
                    
                    # Enforce longer cooldown if we hit max runtime (stored in relay_off_times)
                    required_cooldown = min_off
                    if relay in ['heater', 'humidifier']:
                        last_on = self.relay_on_times.get(relay, 0)
                        if last_on > 0 and (last_off - last_on) >= MAX_RUNTIME:
                            required_cooldown = MIN_COOLDOWN
                    
                    if time_off < required_cooldown:
                        modified_actions[relay] = False
                        remaining = int(required_cooldown - time_off)
                        print(f"{relay.capitalize()} cooldown: {remaining}s remaining")
                        continue
                    else:
                        self.relay_on_times[relay] = current_time
                
                # Turning OFF  
                elif not desired_state and current_state:
                    last_on = self.relay_on_times.get(relay, 0)
                    time_on = current_time - last_on
                    
                    if time_on < min_on:
                        modified_actions[relay] = True
                        continue
                    else:
                        self.relay_off_times[relay] = current_time
            
            # Apply the relay states
            success = self.board.control_climate(
                humidifier=modified_actions['humidifier'],
                dehumidifier=modified_actions['dehumidifier'],
                heater=modified_actions['heater']
            )
            
            # Log state changes
            if success:
                for relay, state in modified_actions.items():
                    if self.last_relay_states.get(relay) != state:
                        self.db.log_relay_change(relay, state, mode='auto')
                        self.last_relay_states[relay] = state
            
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
            
            # Apply actions with timing protection
            success = self.apply_control_actions(actions, temperature, humidity)
            return success
        
        except Exception as e:
            print(f"Error in control cycle: {e}")
            return False
    
    def control_loop(self):
        """Main control loop (runs in separate thread)"""
        print("Climate controller started (simple mode - no ML)")
        
        # Initialize relay_on_times for any relays that are already ON
        try:
            current_states = self.board.get_relay_states()
            current_time = time.time()
            for relay in ['humidifier', 'dehumidifier', 'heater']:
                if current_states.get(relay, False):
                    # Relay is ON, set start time to now
                    self.relay_on_times[relay] = current_time
                    print(f"{relay.capitalize()} was already ON at startup")
        except Exception as e:
            print(f"Error checking initial relay states: {e}")
        
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
                import traceback
                traceback.print_exc()
                time.sleep(30)
        
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
            'use_ml': self.use_ml,
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
        
        # Immediately check if light should be on with new schedule
        if self.enabled:
            should_be_on = self.should_light_be_on()
            self.board.control_light(should_be_on)
            self.db.log_relay_change('light', should_be_on, mode='schedule')
            print(f"Schedule updated: Light {'ON' if should_be_on else 'OFF'}")
    
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
        
        # Force initial state check
        last_state = None
        if self.enabled:
            should_be_on = self.should_light_be_on()
            self.board.control_light(should_be_on)
            self.db.log_relay_change('light', should_be_on, mode='schedule')
            last_state = should_be_on
            print(f"Light initial state: {'ON' if should_be_on else 'OFF'} (schedule)")
        
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
