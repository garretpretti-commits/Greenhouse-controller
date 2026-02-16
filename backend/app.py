"""
Flask Backend Server for Greenhouse Controller
Provides REST API for sensor data, control, and settings
"""

from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import time
import threading
from datetime import datetime
from rp2040_interface import Board1Controller
from database import GreenhouseDB, init_default_settings
from climate_controller import ClimateController, LightScheduler

app = Flask(__name__, 
            static_folder='../frontend/static',
            template_folder='../frontend/templates')
CORS(app)

# Initialize components
db = GreenhouseDB('greenhouse.db')
init_default_settings(db)

board1 = Board1Controller()
climate_controller = None
light_scheduler = None

# Global state
system_status = {
    'board1_connected': False,
    'last_sensor_update': 0,
    'errors': [],
    'cached_sensor_data': None  # Cache the last sensor reading
}

def init_system():
    """Initialize hardware connections and controllers"""
    global climate_controller, light_scheduler, system_status
    
    # Reset ML models on startup (fresh start each boot)
    import os
    import glob
    models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    model_files = glob.glob(os.path.join(models_dir, '*.pkl'))
    for model_file in model_files:
        try:
            os.remove(model_file)
            print(f"Removed ML model: {os.path.basename(model_file)}")
        except Exception as e:
            print(f"Error removing {model_file}: {e}")
    print("ML models reset for fresh training")
    
    # Connect to RP2040 Board 1
    print("Connecting to RP2040 Board 1...")
    if board1.connect():
        system_status['board1_connected'] = True
        print("✓ Board 1 connected")
    else:
        system_status['board1_connected'] = False
        system_status['errors'].append("Failed to connect to Board 1")
        print("✗ Board 1 connection failed")
    
    # Initialize climate controller
    climate_controller = ClimateController(board1, db)
    
    # Check if should start in auto mode
    if db.get_setting('mode') == 'auto':
        climate_controller.start()
    
    # Initialize light scheduler
    light_scheduler = LightScheduler(board1, db)
    
    # Check if should start light scheduler
    if db.get_setting('light_mode') == 'schedule':
        light_scheduler.start()

def sensor_logging_loop():
    """Background thread to log sensor data periodically"""
    while True:
        try:
            if system_status['board1_connected']:
                data = board1.get_sensor_data()
                if data and data.get('temperature') is not None:
                    db.log_sensor_data(data)
                    system_status['last_sensor_update'] = time.time()
                    system_status['cached_sensor_data'] = data  # Cache the reading
            
            time.sleep(30)  # Log every 30 seconds
        except Exception as e:
            print(f"Error in sensor logging: {e}")
            time.sleep(60)

# Start sensor logging thread
logging_thread = threading.Thread(target=sensor_logging_loop, daemon=True)

# ============= API ROUTES =============

@app.route('/')
def index():
    """Serve main dashboard"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """Get system status"""
    return jsonify({
        'status': 'ok',
        'board1_connected': system_status['board1_connected'],
        'last_sensor_update': system_status['last_sensor_update'],
        'climate_controller': climate_controller.get_status() if climate_controller else None,
        'light_scheduler': light_scheduler.get_status() if light_scheduler else None,
        'errors': system_status['errors']
    })

@app.route('/api/sensors/current')
def api_current_sensors():
    """Get current sensor readings (returns cached data for instant response)"""
    try:
        if not system_status['board1_connected']:
            return jsonify({'error': 'Board not connected'}), 503
        
        # Return cached data instantly instead of reading fresh from RP2040
        if system_status['cached_sensor_data']:
            return jsonify(system_status['cached_sensor_data'])
        
        # Only if no cache exists yet, read fresh (first load only)
        data = board1.get_sensor_data()
        if data:
            system_status['cached_sensor_data'] = data
            return jsonify(data)
        else:
            return jsonify({'error': 'Failed to read sensors'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sensors/history')
def api_sensor_history():
    """Get sensor data history"""
    try:
        hours = request.args.get('hours', default=24, type=int)
        history = db.get_sensor_history(hours)
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relays')
def api_get_relays():
    """Get current relay states with status messages"""
    try:
        if not system_status['board1_connected']:
            return jsonify({'error': 'Board not connected'}), 503
        
        states = board1.get_relay_states()
        
        # Get current sensor data to determine why relays are in their state
        sensor_data = system_status.get('cached_sensor_data', {})
        temp = sensor_data.get('temperature')
        humidity = sensor_data.get('humidity')
        
        # Use fallback values if sensor data is None
        if temp is None:
            temp = 20.0
        if humidity is None:
            humidity = 50.0
        
        # Get climate settings
        climate_status = climate_controller.get_status()
        target_temp = climate_status['target_temp']
        target_humidity = climate_status['target_humidity']
        
        # Get light schedule
        light_schedule = light_scheduler.schedule
        
        # Add status messages with timing info
        status_messages = {}
        current_time = time.time()
        
        # Get state change history for each relay
        for relay_name in ['humidifier', 'dehumidifier', 'heater', 'light']:
            history = db.get_relay_state_changes(relay_name, limit=2)
            
            # Find when current state started
            start_time = None
            if history and len(history) > 0:
                latest = history[0]
                if latest['state'] == states.get(relay_name):
                    start_time = latest['timestamp']
            
            # Calculate duration
            duration_str = ""
            if start_time and states.get(relay_name):
                duration_mins = int((current_time - start_time) / 60)
                if duration_mins < 60:
                    duration_str = f" ({duration_mins}m)"
                else:
                    hours = duration_mins // 60
                    mins = duration_mins % 60
                    duration_str = f" ({hours}h {mins}m)"
            
            # Build status messages
            if relay_name == 'humidifier':
                if states.get('humidifier'):
                    status_messages['humidifier'] = f"Humidifying to {target_humidity}%{duration_str}"
                else:
                    status_messages['humidifier'] = f"Off - At {humidity:.0f}%"
            
            elif relay_name == 'dehumidifier':
                if states.get('dehumidifier'):
                    status_messages['dehumidifier'] = f"Dehumidifying to {target_humidity}%{duration_str}"
                else:
                    status_messages['dehumidifier'] = f"Off - At {humidity:.0f}%"
            
            elif relay_name == 'heater':
                if states.get('heater'):
                    status_messages['heater'] = f"Heating to {(target_temp * 9/5 + 32):.0f}°F{duration_str}"
                else:
                    temp_f = (temp * 9/5 + 32)
                    status_messages['heater'] = f"Off - At {temp_f:.0f}°F"
            
            elif relay_name == 'light':
                if states.get('light'):
                    # Calculate time until off
                    if light_schedule and light_schedule.get('off_time'):
                        now = datetime.now()
                        off_time_parts = light_schedule['off_time'].split(':')
                        off_hour = int(off_time_parts[0])
                        off_minute = int(off_time_parts[1])
                        
                        off_today = now.replace(hour=off_hour, minute=off_minute, second=0, microsecond=0)
                        if off_today < now:
                            off_today = off_today.replace(day=now.day + 1)
                        
                        time_until_off = (off_today - now).seconds // 60
                        hours_left = time_until_off // 60
                        mins_left = time_until_off % 60
                        
                        status_messages['light'] = f"On{duration_str} - Off at {light_schedule['off_time']}"
                    else:
                        status_messages['light'] = f"On{duration_str}"
                else:
                    if light_schedule and light_schedule.get('on_time'):
                        status_messages['light'] = f"Off - On at {light_schedule['on_time']}"
                    else:
                        status_messages['light'] = "Off"
        
        return jsonify({
            'states': states,
            'messages': status_messages
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relays/<relay_name>', methods=['POST'])
def api_set_relay(relay_name):
    """Control a specific relay"""
    try:
        if not system_status['board1_connected']:
            return jsonify({'error': 'Board not connected'}), 503
        
        data = request.get_json()
        state = data.get('state', False)
        
        # Check if in auto mode for climate devices
        if relay_name in ['humidifier', 'dehumidifier', 'heater']:
            if climate_controller.enabled:
                return jsonify({
                    'error': 'Climate controller is in auto mode',
                    'message': 'Switch to manual mode first'
                }), 400
        
        # Check if light is in schedule mode
        if relay_name == 'light':
            if light_scheduler.enabled:
                return jsonify({
                    'error': 'Light is in schedule mode',
                    'message': 'Switch to manual mode first'
                }), 400
        
        # Set relay
        if relay_name == 'light':
            success = board1.control_light(state)
        elif relay_name in ['humidifier', 'dehumidifier', 'heater']:
            actions = {'humidifier': False, 'dehumidifier': False, 'heater': False}
            actions[relay_name] = state
            success = board1.control_climate(**actions)
        else:
            return jsonify({'error': 'Invalid relay name'}), 400
        
        if success:
            db.log_relay_change(relay_name, state, mode='manual')
            return jsonify({'success': True, 'relay': relay_name, 'state': state})
        else:
            return jsonify({'error': 'Failed to control relay'}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/climate/mode', methods=['GET', 'POST'])
def api_climate_mode():
    """Get or set climate control mode"""
    try:
        if request.method == 'GET':
            return jsonify({
                'mode': 'auto' if climate_controller.enabled else 'manual',
                'status': climate_controller.get_status()
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            mode = data.get('mode', 'manual')
            
            if mode == 'auto':
                climate_controller.start()
            else:
                climate_controller.stop()
            
            return jsonify({
                'success': True,
                'mode': mode,
                'status': climate_controller.get_status()
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/climate/settings', methods=['GET', 'POST'])
def api_climate_settings():
    """Get or update climate control settings"""
    try:
        if request.method == 'GET':
            return jsonify(climate_controller.get_status())
        
        elif request.method == 'POST':
            data = request.get_json()
            
            climate_controller.update_settings(
                target_temp=data.get('target_temp'),
                temp_tolerance=data.get('temp_tolerance'),
                target_humidity=data.get('target_humidity'),
                humidity_tolerance=data.get('humidity_tolerance'),
                use_ml=data.get('use_ml')
            )
            
            return jsonify({
                'success': True,
                'settings': climate_controller.get_status()
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/light/mode', methods=['GET', 'POST'])
def api_light_mode():
    """Get or set light control mode"""
    try:
        if request.method == 'GET':
            return jsonify({
                'mode': 'schedule' if light_scheduler.enabled else 'manual',
                'status': light_scheduler.get_status()
            })
        
        elif request.method == 'POST':
            data = request.get_json()
            mode = data.get('mode', 'manual')
            
            if mode == 'schedule':
                light_scheduler.start()
            else:
                light_scheduler.stop()
            
            return jsonify({
                'success': True,
                'mode': mode,
                'status': light_scheduler.get_status()
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/light/schedule', methods=['GET', 'POST'])
def api_light_schedule():
    """Get or set light schedule"""
    try:
        if request.method == 'GET':
            schedule = db.get_light_schedule()
            return jsonify(schedule)
        
        elif request.method == 'POST':
            data = request.get_json()
            on_time = data.get('on_time')
            off_time = data.get('off_time')
            enabled = data.get('enabled', True)
            
            if not on_time or not off_time:
                return jsonify({'error': 'on_time and off_time required'}), 400
            
            light_scheduler.set_schedule(on_time, off_time, enabled)
            
            return jsonify({
                'success': True,
                'schedule': light_scheduler.get_status()
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/temp/schedule', methods=['GET', 'POST'])
def api_temp_schedule():
    """Get or set temperature schedule"""
    try:
        if request.method == 'GET':
            schedule = db.get_temp_schedule()
            return jsonify(schedule if schedule else {'enabled': False, 'periods': []})
        
        elif request.method == 'POST':
            data = request.get_json()
            periods = data.get('periods', [])
            enabled = data.get('enabled', True)
            
            if not periods or len(periods) == 0:
                return jsonify({'error': 'At least one period required'}), 400
            
            if len(periods) > 4:
                return jsonify({'error': 'Maximum 4 periods allowed'}), 400
            
            # Validate periods
            for period in periods:
                if 'time' not in period or 'temperature' not in period:
                    return jsonify({'error': 'Each period needs time and temperature'}), 400
            
            db.set_temp_schedule(periods, enabled)
            climate_controller.load_settings()  # Reload settings to pick up new schedule
            
            return jsonify({
                'success': True,
                'schedule': db.get_temp_schedule()
            })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings', methods=['GET'])
def api_get_settings():
    """Get all settings"""
    try:
        settings = db.get_all_settings()
        return jsonify(settings)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/settings/<key>', methods=['POST'])
def api_set_setting(key):
    """Set a specific setting"""
    try:
        data = request.get_json()
        value = data.get('value')
        
        db.set_setting(key, value)
        
        return jsonify({'success': True, 'key': key, 'value': value})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/restart', methods=['POST'])
def api_restart_controller():
    """Restart the greenhouse controller service"""
    try:
        import subprocess
        import os
        
        # Disconnect from hardware before restart
        if board1:
            board1.disconnect()
        
        # Schedule restart after response is sent
        def restart_service():
            time.sleep(1)
            os.system('sudo systemctl restart greenhouse.service')
        
        restart_thread = threading.Thread(target=restart_service, daemon=True)
        restart_thread.start()
        
        return jsonify({'success': True, 'message': 'Controller restarting...'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= MACHINE LEARNING API =============

@app.route('/api/ml/train', methods=['POST'])
def api_ml_train():
    """Train ML climate models"""
    try:
        if not hasattr(climate_controller, 'ml_predictor') or climate_controller.ml_predictor is None:
            return jsonify({'error': 'ML predictor not available'}), 503
        
        # Train in background thread to avoid blocking
        def train_async():
            climate_controller.ml_predictor.train_models()
        
        threading.Thread(target=train_async, daemon=True).start()
        
        return jsonify({'success': True, 'message': 'Training started in background'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/predict', methods=['GET'])
def api_ml_predict():
    """Get ML prediction for current conditions"""
    try:
        if not hasattr(climate_controller, 'ml_predictor') or climate_controller.ml_predictor is None:
            return jsonify({'error': 'ML predictor not available'}), 503
        
        if climate_controller.ml_predictor.temp_model is None:
            return jsonify({'error': 'Models not trained yet'}), 503
        
        # Get current sensor data
        sensor_data = system_status.get('cached_sensor_data', {})
        if not sensor_data:
            return jsonify({'error': 'No sensor data available'}), 503
        
        # Get current relay states
        relay_states = board1.get_relay_states()
        
        # Make prediction
        prediction = climate_controller.ml_predictor.predict(sensor_data, relay_states)
        
        return jsonify({
            'success': True,
            'current': sensor_data,
            'prediction': prediction,
            'horizon_minutes': climate_controller.ml_predictor.prediction_horizon
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/status', methods=['GET'])
def api_ml_status():
    """Get ML system status"""
    try:
        if not hasattr(climate_controller, 'ml_predictor') or climate_controller.ml_predictor is None:
            return jsonify({
                'available': False,
                'enabled': False
            })
        
        ml_pred = climate_controller.ml_predictor
        
        return jsonify({
            'available': True,
            'enabled': climate_controller.use_ml,
            'models_trained': ml_pred.temp_model is not None,
            'last_train_time': ml_pred.last_train_time,
            'prediction_horizon_minutes': ml_pred.prediction_horizon,
            'feature_importance': ml_pred.get_feature_importance() if ml_pred.temp_model else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/toggle', methods=['POST'])
def api_ml_toggle():
    """Enable/disable ML predictions"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        climate_controller.use_ml = enabled
        
        return jsonify({
            'success': True,
            'ml_enabled': climate_controller.use_ml
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/reset', methods=['POST'])
def api_ml_reset():
    """Reset ML models (clear trained data)"""
    try:
        if not hasattr(climate_controller, 'ml_predictor') or climate_controller.ml_predictor is None:
            return jsonify({'error': 'ML predictor not available'}), 503
        
        success = climate_controller.ml_predictor.reset_models()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'ML models reset. Train with new data to enable predictions.'
            })
        else:
            return jsonify({'error': 'Failed to reset models'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= PLANT TRACKER API =============

@app.route('/api/plants', methods=['GET'])
def api_get_plants():
    """Get all plants"""
    try:
        plants = db.get_plants()
        return jsonify(plants)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plants', methods=['POST'])
def api_add_plant():
    """Add a new plant"""
    try:
        data = request.json
        plant_id = db.add_plant(
            strain_name=data.get('strain_name'),
            plant_type=data.get('plant_type'),
            veg_start_date=data.get('veg_start_date'),
            flower_start_date=data.get('flower_start_date'),
            harvest_date=data.get('harvest_date'),
            dry_weight=data.get('dry_weight'),
            notes=data.get('notes')
        )
        return jsonify({'success': True, 'plant_id': plant_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/plants/<int:plant_id>/archive', methods=['POST'])
def api_archive_plant(plant_id):
    """Archive a plant"""
    try:
        db.archive_plant(plant_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/system/crashes', methods=['GET'])
def api_get_crashes():
    """Get recent system crashes/watchdog events"""
    try:
        limit = request.args.get('limit', 50, type=int)
        crashes = db.get_system_crashes(limit)
        return jsonify(crashes)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============= STARTUP =============

if __name__ == '__main__':
    print("=" * 50)
    print("Greenhouse Controller Server Starting...")
    print("=" * 50)
    
    # Initialize system
    init_system()
    
    # Start sensor logging
    logging_thread.start()
    
    print("\nServer ready!")
    print("Access dashboard at: http://localhost:8000")
    print("=" * 50)
    
    try:
        # Run Flask server
        app.run(host='0.0.0.0', port=8000, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        # Cleanup
        if climate_controller:
            climate_controller.shutdown()
        if light_scheduler:
            light_scheduler.shutdown()
        if board1:
            board1.disconnect()
        print("Shutdown complete")
