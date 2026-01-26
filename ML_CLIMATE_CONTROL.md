# Machine Learning Climate Control

## Overview
Your greenhouse now uses machine learning to predict temperature and humidity changes 10 minutes into the future, enabling **proactive** climate control instead of just reacting to current conditions.

## How It Works

### Traditional Control (Reactive)
- Waits until temperature drops below target → turns heater ON
- Waits until humidity is too low → turns humidifier ON
- Results in overshooting and undershooting targets

### ML-Enhanced Control (Predictive)
- Predicts temperature will drop in 10 minutes → turns heater ON early
- Predicts humidity will get too high → turns dehumidifier ON proactively
- Results in tighter control and less energy waste

## Training Data
The ML models learn from:
- **Current temperature and humidity** - baseline conditions
- **Relay states** (heater, humidifier, dehumidifier ON/OFF)
- **Time patterns** (hour of day, day of week) - learns daily cycles
- **Historical changes** - how fast conditions change

### Feature Importance (Your Greenhouse)
From your trained models:

**Temperature Prediction:**
- Current temperature: 93.1% importance (strongest predictor)
- Current humidity: 3.3%
- Minute of hour: 2.6%
- Hour of day: 0.8%
- Heater state: 0.1%

**Humidity Prediction:**
- Current humidity: 31.6% importance
- Current temperature: 49.0% (temp affects humidity!)
- Minute: 17.1% (rapid changes)
- Hour: 2.2%
- Heater: 0.09%

## API Endpoints

### Get ML Status
```bash
curl http://localhost:8000/api/ml/status
```
Shows if ML is enabled, models trained, and feature importance.

### Train Models
```bash
curl -X POST http://localhost:8000/api/ml/train
```
Retrains models with latest data (runs in background).

### Get Current Prediction
```bash
curl http://localhost:8000/api/ml/predict
```
Shows predicted temperature and humidity 10 minutes from now.

### Enable/Disable ML
```bash
curl -X POST http://localhost:8000/api/ml/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

## Automatic Behavior
- Models **automatically retrain every hour** with new data
- Learns your greenhouse's patterns over time
- Adapts to seasonal changes automatically
- If prediction fails, falls back to basic control

## Requirements
- Minimum **100 sensor readings** to train (about 50 minutes of data)
- Models use **1 week of historical data** by default
- Retrains periodically to stay current

## Benefits
1. **Tighter climate control** - stays closer to target
2. **Energy efficiency** - less ON/OFF cycling
3. **Learns patterns** - anticipates daily temperature swings
4. **Self-improving** - gets better with more data

## Current Status
✅ ML system installed and running
✅ Models trained with your historical data
✅ Predictions enabled for heater, humidifier, dehumidifier
✅ Auto-retraining enabled (every hour)

Your greenhouse is now learning!
