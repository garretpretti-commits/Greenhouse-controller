"""
Database module for Greenhouse Controller
Stores sensor data, settings, and control history
"""

import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import threading

class GreenhouseDB:
    """SQLite database manager for greenhouse data"""
    
    def __init__(self, db_path: str = "greenhouse.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize database tables"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Sensor data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    temperature REAL,
                    humidity REAL,
                    soil1 REAL,
                    soil2 REAL,
                    soil3 REAL,
                    soil4 REAL
                )
            ''')
            
            # Relay control history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS relay_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    relay_name TEXT NOT NULL,
                    state INTEGER NOT NULL,
                    mode TEXT NOT NULL
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            ''')
            
            # Light schedule table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS light_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    on_time TEXT NOT NULL,
                    off_time TEXT NOT NULL
                )
            ''')
            
            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_sensor_timestamp 
                ON sensor_data(timestamp)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_relay_timestamp 
                ON relay_history(timestamp)
            ''')
            
            conn.commit()
            conn.close()
    
    def log_sensor_data(self, data: Dict[str, Any]):
        """Log sensor readings"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            soil = data.get('soil_moisture', {})
            
            cursor.execute('''
                INSERT INTO sensor_data 
                (timestamp, temperature, humidity, soil1, soil2, soil3, soil4)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data.get('timestamp', time.time()),
                data.get('temperature'),
                data.get('humidity'),
                soil.get('soil1'),
                soil.get('soil2'),
                soil.get('soil3'),
                soil.get('soil4')
            ))
            
            conn.commit()
            conn.close()
    
    def log_relay_change(self, relay_name: str, state: bool, mode: str = "manual"):
        """Log relay state change"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO relay_history (timestamp, relay_name, state, mode)
                VALUES (?, ?, ?, ?)
            ''', (time.time(), relay_name, int(state), mode))
            
            conn.commit()
            conn.close()
    
    def get_latest_sensor_data(self) -> Optional[Dict[str, Any]]:
        """Get most recent sensor reading"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM sensor_data 
            ORDER BY timestamp DESC LIMIT 1
        ''')
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'timestamp': row['timestamp'],
                'temperature': row['temperature'],
                'humidity': row['humidity'],
                'soil_moisture': {
                    'soil1': row['soil1'],
                    'soil2': row['soil2'],
                    'soil3': row['soil3'],
                    'soil4': row['soil4']
                }
            }
        return None
    
    def get_sensor_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get sensor data for the last N hours"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cutoff_time = time.time() - (hours * 3600)
        
        cursor.execute('''
            SELECT * FROM sensor_data 
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        ''', (cutoff_time,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{
            'timestamp': row['timestamp'],
            'temperature': row['temperature'],
            'humidity': row['humidity'],
            'soil1': row['soil1'],
            'soil2': row['soil2'],
            'soil3': row['soil3'],
            'soil4': row['soil4']
        } for row in rows]
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['value']
        return default
    
    def set_setting(self, key: str, value: Any):
        """Set a setting value"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
            ''', (key, str(value), time.time()))
            
            conn.commit()
            conn.close()
    
    def get_all_settings(self) -> Dict[str, str]:
        """Get all settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, value FROM settings')
        rows = cursor.fetchall()
        conn.close()
        
        return {row['key']: row['value'] for row in rows}
    
    def set_light_schedule(self, on_time: str, off_time: str, enabled: bool = True):
        """Set light schedule"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Delete existing schedule
            cursor.execute('DELETE FROM light_schedule')
            
            # Insert new schedule
            cursor.execute('''
                INSERT INTO light_schedule (enabled, on_time, off_time)
                VALUES (?, ?, ?)
            ''', (int(enabled), on_time, off_time))
            
            conn.commit()
            conn.close()
    
    def get_light_schedule(self) -> Optional[Dict[str, Any]]:
        """Get light schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM light_schedule LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'enabled': bool(row['enabled']),
                'on_time': row['on_time'],
                'off_time': row['off_time']
            }
        return None
    
    def cleanup_old_data(self, days: int = 30):
        """Remove sensor data older than N days"""
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cutoff_time = time.time() - (days * 86400)
            
            cursor.execute('DELETE FROM sensor_data WHERE timestamp < ?', (cutoff_time,))
            cursor.execute('DELETE FROM relay_history WHERE timestamp < ?', (cutoff_time,))
            
            conn.commit()
            deleted = cursor.rowcount
            conn.close()
            
            return deleted


# Initialize default settings
def init_default_settings(db: GreenhouseDB):
    """Initialize default settings if they don't exist"""
    defaults = {
        'mode': 'manual',  # 'manual' or 'auto'
        'target_temp': '22.0',
        'temp_tolerance': '1.0',
        'target_humidity': '60.0',
        'humidity_tolerance': '5.0',
        'light_mode': 'schedule',  # 'manual' or 'schedule'
    }
    
    for key, value in defaults.items():
        if db.get_setting(key) is None:
            db.set_setting(key, value)
