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
        
        # Control state
        self.enabled = False
        self.use_ml = True  # Enable ML predictions by default
        self.last_action_time = 0
        self.min_action_interval = 60  # Minimum seconds between actions
        
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
        
        # ML predictor
        self.ml_predictor = None
        if ML_AVAILABLE:
            try:
                self.ml_predictor = MLClimatePredictor(database)
                print("ML Climate Predictor initialized")
            except Exception as e:
                print(f"Failed to initialize ML predictor: {e}")
        
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
            self.use_ml = self.db.get_setting('use_ml', 'True').lower() == 'true'
        except (ValueError, TypeError):
            print("Error loading settings, using defaults")
    
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
        Uses ML predictions if available for proactive control
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
        
        # Use ML prediction if available and enabled
        prediction = None
        if self.use_ml and self.ml_predictor and self.ml_predictor.temp_model is not None:
            try:
                current_data = {
                    'temperature': temperature,
                    'humidity': humidity
                }
                prediction = self.ml_predictor.predict(current_data, relay_states)
                
                if prediction:
                    # Check if models need retraining
                    if self.ml_predictor.should_retrain():
                        print("Retraining ML models in background...")
                        threading.Thread(target=self.ml_predictor.train_models, daemon=True).start()
                
            except Exception as e:
                print(f"ML prediction error: {e}")
                prediction = None
        
        # Temperature control with ML predictions
        temp_low = self.target_temp - self.temp_tolerance
        temp_high = self.target_temp + self.temp_tolerance
        
        print(f"[CONTROL] Temp: {temperature:.1f}°C ({temperature*9/5+32:.1f}°F), Target: {self.target_temp:.1f}°C ({self.target_temp*9/5+32:.1f}°F), Low: {temp_low:.1f}°C, High: {temp_high:.1f}°C")
        
        if prediction and self.use_ml:
            # Predictive control: turn on heater if we predict temperature will drop below target
            predicted_temp = prediction['predicted_temp']
            
            if predicted_temp < temp_low:
                actions['heater'] = True
            elif temperature > temp_high:
                actions['heater'] = False
            else:
                # Within range, use prediction to decide
                actions['heater'] = predicted_temp < self.target_temp
        else:
            # Basic reactive control
            if temperature < temp_low:
                actions['heater'] = True
                print(f"[CONTROL] Heater ON: temp {temperature:.1f}°C < low threshold {temp_low:.1f}°C")
            elif temperature > temp_high:
                actions['heater'] = False
                print(f"[CONTROL] Heater OFF: temp {temperature:.1f}°C > high threshold {temp_high:.1f}°C")
        
        # Humidity control with ML predictions
        humidity_low = self.target_humidity - self.humidity_tolerance
        humidity_high = self.target_humidity + self.humidity_tolerance
        
        if prediction and self.use_ml:
            # Predictive control
            predicted_humidity = prediction['predicted_humidity']
            
            if predicted_humidity < humidity_low:
                actions['humidifier'] = True
                actions['dehumidifier'] = False
            elif predicted_humidity > humidity_high:
                actions['humidifier'] = False
                actions['dehumidifier'] = True
            else:
                # Within range, use prediction to decide
                if predicted_humidity < self.target_humidity:
                    actions['humidifier'] = True
                    actions['dehumidifier'] = False
                elif predicted_humidity > self.target_humidity:
                    actions['humidifier'] = False
                    actions['dehumidifier'] = True
                else:
                    actions['humidifier'] = False
                    actions['dehumidifier'] = False
        else:
            # Basic reactive control
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
    
    def calculate_adaptive_cycle_times(self, temperature: float, humidity: float) -> Dict[str, Dict[str, float]]:
        """
        Calculate adaptive on/off times based on distance from target and effectiveness
        Returns dict with min_on_time and min_off_time for each relay
        """
        cycle_times = {}
        
        # Heater cycle times
        # Use default if target_temp is None
        target_temp = self.target_temp if self.target_temp else 22.0
        temp_diff = abs(target_temp - temperature)
        temp_percent_off = (temp_diff / target_temp) * 100
        
        # Adaptive heater timing:
        # Close to target (< 5% off): 10 min on, 20 min off
        # Medium distance (5-15% off): 20 min on, 10 min off  
        # Far from target (> 15% off): 30+ min on, 5 min off
        if temp_percent_off < 5:
            heater_on = 600  # 10 minutes
            heater_off = 1200  # 20 minutes
        elif temp_percent_off < 15:
            heater_on = 1200  # 20 minutes
            heater_off = 600   # 10 minutes
        else:
            # Scale up to 60 min for very far distances
            heater_on = min(3600, 1800 + (temp_percent_off * 60))  # 30-60 minutes
            heater_off = 300  # 5 minutes
        
        cycle_times['heater'] = {'min_on': heater_on, 'min_off': heater_off}
        
        # Humidifier cycle times
        # Use default if target_humidity is None
        target_humidity = self.target_humidity if self.target_humidity else 60.0
        humidity_diff = abs(target_humidity - humidity)
        humidity_percent_off = (humidity_diff / target_humidity) * 100
        
        # Adaptive humidifier timing:
        if humidity_percent_off < 5:
            humid_on = 600   # 10 minutes
            humid_off = 1200  # 20 minutes
        elif humidity_percent_off < 15:
            humid_on = 1200  # 20 minutes
            humid_off = 600   # 10 minutes
        else:
            humid_on = min(3600, 1800 + (humidity_percent_off * 60))  # 30-60 minutes
            humid_off = 300  # 5 minutes
        
        cycle_times['humidifier'] = {'min_on': humid_on, 'min_off': humid_off}
        
        # Dehumidifier - similar to humidifier
        cycle_times['dehumidifier'] = {'min_on': humid_on, 'min_off': humid_off}
        
        return cycle_times
    
    def check_relay_effectiveness(self, relay: str, temperature: float, humidity: float) -> bool:
        """
        Check if a relay is being effective (making progress toward target)
        Returns True if effective, False if wasting energy
        """
        if relay not in self.last_sensor_values:
            # No history yet, assume effective
            return True
        
        last_values = self.last_sensor_values[relay]
        time_running = time.time() - self.relay_on_times.get(relay, time.time())
        
        # Need at least 5 minutes of data to judge
        if time_running < 300:
            return True
        
        # Check progress based on relay type
        if relay == 'heater':
            last_temp = last_values.get('temperature', temperature)
            temp_change = temperature - last_temp
            # If we're trying to heat but temp is dropping, not effective
            if temp_change <= 0 and temperature < self.target_temp:
                return False
            # If temp rising too slowly (< 0.1°C per 5 min), might not be effective
            if temp_change < 0.1 and (self.target_temp - temperature) > 2:
                return False
                
        elif relay == 'humidifier':
            last_humidity = last_values.get('humidity', humidity)
            humidity_change = humidity - last_humidity
            # If we're trying to humidify but humidity dropping, not effective
            if humidity_change <= 0 and humidity < self.target_humidity:
                return False
            # If humidity rising too slowly
            if humidity_change < 0.5 and (self.target_humidity - humidity) > 10:
                return False
                
        elif relay == 'dehumidifier':
            last_humidity = last_values.get('humidity', humidity)
            humidity_change = humidity - last_humidity
            # If we're trying to dehumidify but humidity rising, not effective
            if humidity_change >= 0 and humidity > self.target_humidity:
                return False
        
        return True
    
    def apply_control_actions(self, actions: Dict[str, bool], temperature: float = None, humidity: float = None) -> bool:
        """Apply control actions to relays with adaptive duty cycling"""
        try:
            # Use provided sensor data or fetch it
            if temperature is None or humidity is None:
                try:
                    data = self.board.get_climate_data()
                    temperature = data.get('temperature', self.target_temp)
                    humidity = data.get('humidity', self.target_humidity)
                except:
                    # Fallback to targets if we can't get data
                    temperature = self.target_temp
                    humidity = self.target_humidity
            
            # Calculate adaptive cycle times based on current conditions
            cycle_times = self.calculate_adaptive_cycle_times(temperature, humidity)
            
            current_time = time.time()
            modified_actions = actions.copy()
            
            # Apply adaptive duty cycling
            for relay in ['heater', 'humidifier', 'dehumidifier']:
                desired_state = actions.get(relay, False)
                current_state = self.last_relay_states.get(relay)
                
                min_on = cycle_times[relay]['min_on']
                min_off = cycle_times[relay]['min_off']
                
                # Safety limits for heater and humidifier
                MAX_RUNTIME = 3600  # 1 hour maximum
                MIN_COOLDOWN = 450  # 7.5 minutes minimum cooldown
                
                # Check if we want to turn ON
                if desired_state and not current_state:
                    # Check if minimum OFF time has passed
                    last_off = self.relay_off_times.get(relay, 0)
                    time_off = current_time - last_off
                    
                    # Enforce minimum cooldown for heater and humidifier
                    required_off_time = min_off
                    if relay in ['heater', 'humidifier']:
                        required_off_time = max(min_off, MIN_COOLDOWN)
                    
                    if time_off < required_off_time:
                        # Too soon to turn back on
                        modified_actions[relay] = False
                        cooldown_remaining = int(required_off_time - time_off)
                        print(f"{relay.capitalize()} cooldown: {cooldown_remaining}s remaining")
                        continue
                    else:
                        # OK to turn on, record the time and current sensor values
                        self.relay_on_times[relay] = current_time
                        self.last_sensor_values[relay] = {
                            'temperature': temperature,
                            'humidity': humidity,
                            'time': current_time
                        }
                
                # Check if we want to turn OFF
                elif not desired_state and current_state:
                    # Check if minimum ON time has passed
                    last_on = self.relay_on_times.get(relay, 0)
                    time_on = current_time - last_on
                    
                    # Safety: Force off if max runtime exceeded for heater/humidifier
                    if relay in ['heater', 'humidifier'] and time_on >= MAX_RUNTIME:
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        print(f"{relay.capitalize()} max runtime reached, forcing off for cooldown")
                        continue
                    
                    # Allow immediate shutoff if target is reached or exceeded
                    should_shutoff_immediately = False
                    if relay == 'heater':
                        # Shut off if at or above target
                        should_shutoff_immediately = temperature >= self.target_temp
                    elif relay == 'humidifier':
                        # Shut off if at or above target
                        should_shutoff_immediately = humidity >= self.target_humidity
                    elif relay == 'dehumidifier':
                        # Shut off if at or below target
                        should_shutoff_immediately = humidity <= self.target_humidity
                    
                    if should_shutoff_immediately:
                        # Target reached, allow immediate shutoff regardless of min_on time
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        print(f"{relay.capitalize()} target reached, shutting off immediately")
                        continue
                    
                    # Check effectiveness - if not making progress, allow early shutoff
                    is_effective = self.check_relay_effectiveness(relay, temperature, humidity)
                    
                    # If ineffective and ran for at least 10 minutes, allow shutoff
                    if not is_effective and time_on >= 600:
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        # Force longer off time if ineffective (30 min)
                        self.relay_off_times[relay] = current_time - min_off + 1800
                        continue
                    
                    # Normal minimum on time check
                    if time_on < min_on:
                        # Too soon to turn off, keep it on
                        modified_actions[relay] = True
                        continue
                    else:
                        # OK to turn off, record the time
                        self.relay_off_times[relay] = current_time
                
                # Safety check: If relay is currently ON, check max runtime
                elif current_state:
                    last_on = self.relay_on_times.get(relay, 0)
                    time_on = current_time - last_on
                    
                    # Force off if max runtime exceeded for heater/humidifier
                    if relay in ['heater', 'humidifier'] and time_on >= MAX_RUNTIME:
                        modified_actions[relay] = False
                        self.relay_off_times[relay] = current_time
                        print(f"{relay.capitalize()} safety limit: max runtime exceeded, forcing off")
            
            success = self.board.control_climate(
                humidifier=modified_actions['humidifier'],
                dehumidifier=modified_actions['dehumidifier'],
                heater=modified_actions['heater']
            )
            
            # Log actions to database ONLY if state changed
            if success:
                for relay, state in modified_actions.items():
                    # Only log if this is a state change
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
            print("[DEBUG] Control cycle executing...")
            data = self.board.get_climate_data()
            
            if not data or data.get('temperature') is None or data.get('humidity') is None:
                print("Warning: Missing sensor data")
                return False
            
            temperature = data['temperature']
            humidity = data['humidity']
            
            # Calculate required actions
            actions = self.calculate_control_actions(temperature, humidity)
            
            # Apply actions (with rate limiting), pass sensor data to avoid re-fetching
            current_time = time.time()
            if current_time - self.last_action_time >= self.min_action_interval:
                success = self.apply_control_actions(actions, temperature, humidity)
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
        
        # Initialize relay_on_times for any relays that are already ON
        try:
            current_states = self.board.get_relay_states()
            current_time = time.time()
            for relay in ['humidifier', 'dehumidifier', 'heater']:
                if current_states.get(relay, False):
                    # Relay is already ON, set start time to now to track from this point
                    self.relay_on_times[relay] = current_time
                    print(f"{relay.capitalize()} was already ON at startup, tracking from now")
        except Exception as e:
            print(f"Error initializing relay states: {e}")
        
        # Train ML models on startup if available and not trained
        if self.ml_predictor and self.ml_predictor.temp_model is None:
            print("Training ML models on startup...")
            try:
                self.ml_predictor.train_models()
            except Exception as e:
                print(f"Initial ML training failed: {e}")
        
        while self.running:
            try:
                print(f"[DEBUG] Loop iteration - enabled:{self.enabled}, running:{self.running}", flush=True)
                if self.enabled:
                    # Reload settings periodically
                    self.load_settings()
                    
                    # Execute control cycle
                    self.control_cycle()
                    
                    # Check if ML models need retraining
                    if self.ml_predictor and self.use_ml:
                        if self.ml_predictor.should_retrain():
                            print("Auto-retraining ML models for seasonal adaptation...")
                            # Train in background thread to not block control
                            threading.Thread(target=self.ml_predictor.train_models, daemon=True).start()
                
                # Sleep between cycles
                print("[DEBUG] Sleeping 10 seconds...", flush=True)
                time.sleep(10)  # Check every 10 seconds
                print("[DEBUG] Woke from sleep, looping...", flush=True)
            
            except Exception as e:
                print(f"Error in control loop: {e}", flush=True)
                import traceback
                traceback.print_exc()
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
