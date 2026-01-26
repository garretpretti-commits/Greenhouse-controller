"""
Machine Learning Climate Predictor
Learns from historical data to predict future temperature and humidity changes
Enables proactive climate control instead of reactive
"""

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import pickle
import os
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import time

class MLClimatePredictor:
    """
    Machine learning model to predict temperature and humidity changes
    Uses historical sensor data and relay states to learn patterns
    """
    
    def __init__(self, database, model_dir='models'):
        self.db = database
        self.model_dir = model_dir
        
        # Create models directory if it doesn't exist
        os.makedirs(model_dir, exist_ok=True)
        
        # Models for temperature and humidity prediction
        self.temp_model = None
        self.humidity_model = None
        self.temp_scaler = StandardScaler()
        self.humidity_scaler = StandardScaler()
        
        # Model parameters
        self.prediction_horizon = 10  # minutes ahead to predict
        self.min_training_samples = 100
        self.retrain_interval = 900  # Retrain every 15 minutes for rapid adaptation
        self.last_train_time = 0
        self.training_window_hours = 72  # Use last 3 days (adapts faster to seasonal changes)
        
        # Load existing models if available
        self.load_models()
    
    def create_features(self, sensor_data, relay_states, time_features=None):
        """
        Create feature vector from sensor data and relay states
        Features include:
        - Current temperature and humidity
        - Relay states (heater, humidifier, dehumidifier)
        - Time of day (hour, minute)
        - Time since last relay change
        """
        if time_features is None:
            now = datetime.now()
            time_features = {
                'hour': now.hour,
                'minute': now.minute,
                'day_of_week': now.weekday()
            }
        
        features = [
            sensor_data['temperature'],
            sensor_data['humidity'],
            1 if relay_states.get('heater', False) else 0,
            1 if relay_states.get('humidifier', False) else 0,
            1 if relay_states.get('dehumidifier', False) else 0,
            time_features['hour'],
            time_features['minute'],
            time_features['day_of_week']
        ]
        
        return np.array(features)
    
    def prepare_training_data(self, hours_back=None):
        """
        Prepare training data from historical sensor readings
        Returns X (features) and y (targets) for both temp and humidity
        """
        if hours_back is None:
            hours_back = self.training_window_hours
        
        # Get historical sensor data
        cutoff_time = time.time() - (hours_back * 3600)
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get sensor data with timestamps
        cursor.execute('''
            SELECT timestamp, temperature, humidity
            FROM sensor_data
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        ''', (cutoff_time,))
        
        sensor_rows = cursor.fetchall()
        
        if len(sensor_rows) < self.min_training_samples:
            conn.close()
            return None, None, None, None
        
        # Get relay state history
        cursor.execute('''
            SELECT timestamp, relay_name, state
            FROM relay_history
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        ''', (cutoff_time,))
        
        relay_rows = cursor.fetchall()
        conn.close()
        
        # Build relay state timeline
        relay_timeline = {}
        for row in relay_rows:
            ts = row['timestamp']
            name = row['relay_name']
            state = bool(row['state'])
            if ts not in relay_timeline:
                relay_timeline[ts] = {}
            relay_timeline[ts][name] = state
        
        # Create feature and target arrays
        X_temp = []
        y_temp = []
        X_humidity = []
        y_humidity = []
        
        prediction_seconds = self.prediction_horizon * 60
        
        for i in range(len(sensor_rows) - 1):
            current = sensor_rows[i]
            current_time = current['timestamp']
            
            # Find sensor reading closest to prediction_horizon in the future
            future_idx = None
            for j in range(i + 1, len(sensor_rows)):
                future = sensor_rows[j]
                time_diff = future['timestamp'] - current_time
                if time_diff >= prediction_seconds * 0.8:  # Within 80% of target
                    future_idx = j
                    break
            
            if future_idx is None:
                continue
            
            future = sensor_rows[future_idx]
            
            # Get relay states at current time
            relay_states = {'heater': False, 'humidifier': False, 'dehumidifier': False}
            for ts in sorted([t for t in relay_timeline.keys() if t <= current_time], reverse=True):
                for relay_name, state in relay_timeline[ts].items():
                    if relay_name in relay_states:
                        relay_states[relay_name] = state
                break
            
            # Create time features
            dt = datetime.fromtimestamp(current_time)
            time_features = {
                'hour': dt.hour,
                'minute': dt.minute,
                'day_of_week': dt.weekday()
            }
            
            # Create feature vector
            features = self.create_features(
                {'temperature': current['temperature'], 'humidity': current['humidity']},
                relay_states,
                time_features
            )
            
            # Temperature prediction
            temp_change = future['temperature'] - current['temperature']
            X_temp.append(features)
            y_temp.append(temp_change)
            
            # Humidity prediction
            humidity_change = future['humidity'] - current['humidity']
            X_humidity.append(features)
            y_humidity.append(humidity_change)
        
        return np.array(X_temp), np.array(y_temp), np.array(X_humidity), np.array(y_humidity)
    
    def train_models(self):
        """Train the prediction models using historical data"""
        print("Training ML climate models...")
        
        X_temp, y_temp, X_humidity, y_humidity = self.prepare_training_data()
        
        if X_temp is None or len(X_temp) < self.min_training_samples:
            print(f"Not enough training data (need {self.min_training_samples}, have {len(X_temp) if X_temp is not None else 0})")
            return False
        
        print(f"Training with {len(X_temp)} samples...")
        
        # Scale features
        X_temp_scaled = self.temp_scaler.fit_transform(X_temp)
        X_humidity_scaled = self.humidity_scaler.fit_transform(X_humidity)
        
        # Train temperature model
        self.temp_model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.temp_model.fit(X_temp_scaled, y_temp)
        
        # Train humidity model
        self.humidity_model = RandomForestRegressor(
            n_estimators=50,
            max_depth=10,
            min_samples_split=5,
            random_state=42,
            n_jobs=-1
        )
        self.humidity_model.fit(X_humidity_scaled, y_humidity)
        
        # Save models
        self.save_models()
        
        self.last_train_time = time.time()
        print("ML models trained successfully!")
        
        return True
    
    def predict(self, current_data: Dict[str, float], relay_states: Dict[str, bool]) -> Dict[str, float]:
        """
        Predict temperature and humidity change over the next prediction_horizon minutes
        Returns predicted changes
        """
        if self.temp_model is None or self.humidity_model is None:
            return None
        
        # Create feature vector
        features = self.create_features(current_data, relay_states)
        features_reshaped = features.reshape(1, -1)
        
        # Scale features
        temp_features_scaled = self.temp_scaler.transform(features_reshaped)
        humidity_features_scaled = self.humidity_scaler.transform(features_reshaped)
        
        # Make predictions
        temp_change = self.temp_model.predict(temp_features_scaled)[0]
        humidity_change = self.humidity_model.predict(humidity_features_scaled)[0]
        
        return {
            'temp_change': temp_change,
            'humidity_change': humidity_change,
            'predicted_temp': current_data['temperature'] + temp_change,
            'predicted_humidity': current_data['humidity'] + humidity_change
        }
    
    def should_retrain(self) -> bool:
        """Check if models should be retrained"""
        if self.temp_model is None or self.humidity_model is None:
            return True
        
        return (time.time() - self.last_train_time) > self.retrain_interval
    
    def save_models(self):
        """Save trained models to disk"""
        try:
            with open(os.path.join(self.model_dir, 'temp_model.pkl'), 'wb') as f:
                pickle.dump(self.temp_model, f)
            
            with open(os.path.join(self.model_dir, 'humidity_model.pkl'), 'wb') as f:
                pickle.dump(self.humidity_model, f)
            
            with open(os.path.join(self.model_dir, 'temp_scaler.pkl'), 'wb') as f:
                pickle.dump(self.temp_scaler, f)
            
            with open(os.path.join(self.model_dir, 'humidity_scaler.pkl'), 'wb') as f:
                pickle.dump(self.humidity_scaler, f)
            
            print("Models saved successfully")
        except Exception as e:
            print(f"Error saving models: {e}")
    
    def load_models(self):
        """Load trained models from disk"""
        try:
            temp_model_path = os.path.join(self.model_dir, 'temp_model.pkl')
            humidity_model_path = os.path.join(self.model_dir, 'humidity_model.pkl')
            
            if not os.path.exists(temp_model_path) or not os.path.exists(humidity_model_path):
                print("No saved models found")
                return False
            
            with open(temp_model_path, 'rb') as f:
                self.temp_model = pickle.load(f)
            
            with open(humidity_model_path, 'rb') as f:
                self.humidity_model = pickle.load(f)
            
            with open(os.path.join(self.model_dir, 'temp_scaler.pkl'), 'rb') as f:
                self.temp_scaler = pickle.load(f)
            
            with open(os.path.join(self.model_dir, 'humidity_scaler.pkl'), 'rb') as f:
                self.humidity_scaler = pickle.load(f)
            
            print("Models loaded successfully")
            return True
            
        except Exception as e:
            print(f"Error loading models: {e}")
            return False
    
    def reset_models(self):
        """Clear all trained models and saved files"""
        try:
            # Clear in-memory models
            self.temp_model = None
            self.humidity_model = None
            self.temp_scaler = StandardScaler()
            self.humidity_scaler = StandardScaler()
            self.last_train_time = 0
            
            # Delete saved model files
            model_files = [
                'temp_model.pkl',
                'humidity_model.pkl',
                'temp_scaler.pkl',
                'humidity_scaler.pkl'
            ]
            
            for filename in model_files:
                filepath = os.path.join(self.model_dir, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Deleted {filename}")
            
            print("ML models reset successfully")
            return True
            
        except Exception as e:
            print(f"Error resetting models: {e}")
            return False
    
    def get_feature_importance(self) -> Dict[str, Any]:
        """Get feature importance scores from the models"""
        if self.temp_model is None or self.humidity_model is None:
            return None
        
        feature_names = [
            'current_temp',
            'current_humidity',
            'heater_state',
            'humidifier_state',
            'dehumidifier_state',
            'hour',
            'minute',
            'day_of_week'
        ]
        
        return {
            'temperature': dict(zip(feature_names, self.temp_model.feature_importances_)),
            'humidity': dict(zip(feature_names, self.humidity_model.feature_importances_))
        }
