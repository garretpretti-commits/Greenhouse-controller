"""
Flask Backend Server for Greenhouse Controller
Provides REST API for sensor data, control, and settings
"""

from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
import time
import threading
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
    'errors': []
}

def init_system():
    """Initialize hardware connections and controllers"""
    global climate_controller, light_scheduler, system_status
    
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
    """Get current sensor readings"""
    try:
        if not system_status['board1_connected']:
            return jsonify({'error': 'Board not connected'}), 503
        
        data = board1.get_sensor_data()
        if data:
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
    """Get current relay states"""
    try:
        if not system_status['board1_connected']:
            return jsonify({'error': 'Board not connected'}), 503
        
        states = board1.get_relay_states()
        return jsonify(states)
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
                humidity_tolerance=data.get('humidity_tolerance')
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
