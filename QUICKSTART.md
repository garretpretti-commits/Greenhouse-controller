# Quick Start Guide

## 🚀 Installation & Testing

### Step 1: Install Dependencies

Run the installation script:

```bash
cd /home/pi/websitephotos
./install.sh
```

This will:
- Install Python dependencies
- Create virtual environment
- Set up systemd service
- Add user to dialout group

**Important:** After installation, logout and login again for group changes to take effect.

### Step 2: Upload Code to RP2040 Board 1

1. **Install CircuitPython:**
   - Download from: https://circuitpython.org/board/raspberry_pi_pico/
   - Hold BOOT button on RP2040-Zero and plug in USB
   - Copy .UF2 file to RPI-RP2 drive
   - Board will reboot as CIRCUITPY

2. **Install Libraries:**
   ```bash
   # Download CircuitPython Library Bundle from:
   # https://circuitpython.org/libraries
   
   # Extract and copy adafruit_dht to CIRCUITPY/lib/
   ```

3. **Upload Code:**
   ```bash
   cp /home/pi/websitephotos/rp2040_board1/code.py /media/pi/CIRCUITPY/
   ```

### Step 3: Test RP2040 Connection

```bash
cd /home/pi/websitephotos
source venv/bin/activate
python3 backend/rp2040_interface.py
```

You should see:
```
Connected to Board1 on /dev/ttyACM0
=== Testing Board 1 ===
Sensor Data:
{
  "temperature": 22.5,
  "humidity": 65.0,
  "soil_moisture": {...},
  "timestamp": 1234567890.123
}
```

### Step 4: Start the Server

**Option A: Manual Start (for testing)**
```bash
cd /home/pi/websitephotos
source venv/bin/activate
python3 backend/app.py
```

**Option B: Start as Service**
```bash
sudo systemctl start greenhouse.service
sudo systemctl status greenhouse.service
```

### Step 5: Access the Dashboard

Open your web browser:
- Local: http://localhost:8000
- Network: http://<raspberry-pi-ip>:8000
- Tailscale: http://garretsrpi.tailf0f567.ts.net:8000

---

## 🧪 Testing Checklist

### ✅ Basic Functionality

- [ ] Dashboard loads without errors
- [ ] Connection status shows "Connected" (green)
- [ ] Temperature reading displays
- [ ] Humidity reading displays
- [ ] All 4 soil moisture sensors show values
- [ ] Relay states are visible

### ✅ Manual Control

- [ ] Toggle humidifier ON/OFF
- [ ] Toggle dehumidifier ON/OFF
- [ ] Toggle heater ON/OFF
- [ ] Toggle light ON/OFF
- [ ] Relay states update in real-time

### ✅ Auto Climate Control

- [ ] Switch to "Auto" mode
- [ ] Set target temperature (e.g., 22°C ± 1°C)
- [ ] Set target humidity (e.g., 60% ± 5%)
- [ ] Click "Save Settings"
- [ ] Verify system responds to temperature/humidity changes

### ✅ Light Scheduling

- [ ] Switch to "Schedule" mode
- [ ] Set ON time (e.g., 06:00)
- [ ] Set OFF time (e.g., 22:00)
- [ ] Click "Save Schedule"
- [ ] Verify light turns on/off at scheduled times

### ✅ Data Logging

- [ ] Check that charts populate with data
- [ ] Change time range (1h, 6h, 24h, 3d)
- [ ] Verify historical data is displayed

---

## 🔧 Troubleshooting

### RP2040 Not Detected

```bash
# Check USB device
lsusb | grep 2e8a

# Check serial ports
ls -l /dev/ttyACM*

# Verify CircuitPython
ls /media/pi/CIRCUITPY/

# Check permissions
groups pi  # Should include 'dialout'
```

### Server Won't Start

```bash
# Check logs
sudo journalctl -u greenhouse.service -n 50

# Check port availability
sudo netstat -tulpn | grep 8000

# Test manually
cd /home/pi/websitephotos
source venv/bin/activate
python3 backend/app.py
```

### Dashboard Not Loading

```bash
# Check if Flask is running
ps aux | grep app.py

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp

# Test API directly
curl http://localhost:8000/api/status
```

### Sensors Reading Errors

**DHT22 Issues:**
- Verify wiring: Data → GPIO13, VCC → 3.3V, GND → GND
- Try different GPIO pin if persistent errors
- Add 10kΩ pull-up resistor between Data and VCC

**Soil Sensor Issues:**
- Check transistor switch wiring (GPIO 15, 14, 6, 8)
- Verify sensor power connections
- Calibrate sensors (see rp2040_board1/README.md)

### Relays Not Working

```bash
# Test relay manually via API
curl -X POST http://localhost:8000/api/relays/light \
  -H "Content-Type: application/json" \
  -d '{"state": true}'

# Check relay board power (5V)
# Verify active-low logic: LOW = ON, HIGH = OFF
```

---

## 📊 System Commands

### Service Management

```bash
# Start service
sudo systemctl start greenhouse.service

# Stop service
sudo systemctl stop greenhouse.service

# Restart service
sudo systemctl restart greenhouse.service

# Enable auto-start on boot
sudo systemctl enable greenhouse.service

# Disable auto-start
sudo systemctl disable greenhouse.service

# Check status
sudo systemctl status greenhouse.service

# View logs
sudo journalctl -u greenhouse.service -f
```

### Backup Commands

```bash
# Manual Git backup
/home/pi/git_backup.sh

# Manual USB backup
/home/pi/backup_greenhouse.sh

# View backup log
cat /home/pi/backup.log
```

### Database Management

```bash
# View database
sqlite3 /home/pi/websitephotos/greenhouse.db

# Show tables
.tables

# View recent sensor data
SELECT * FROM sensor_data ORDER BY timestamp DESC LIMIT 10;

# View relay history
SELECT * FROM relay_history ORDER BY timestamp DESC LIMIT 20;

# Exit
.exit
```

---

## 🎯 Next Steps

After successful testing:

1. **Enable Auto-Start:**
   ```bash
   sudo systemctl enable greenhouse.service
   ```

2. **Monitor for 24 Hours:**
   - Check temperature/humidity control
   - Verify light schedule works
   - Ensure no crashes or errors

3. **Fine-Tune Settings:**
   - Adjust target temperature/humidity
   - Calibrate soil sensors
   - Optimize control tolerances

4. **Set Up Monitoring:**
   - Check logs periodically
   - Monitor relay operation
   - Review sensor data trends

5. **Consider Additions:**
   - Email/SMS alerts for critical conditions
   - Camera for visual monitoring
   - Additional sensors (CO2, light intensity)
   - Weather integration

---

## 📝 Default Settings

- **Target Temperature:** 22°C ± 1°C
- **Target Humidity:** 60% ± 5%
- **Light Schedule:** 06:00 - 22:00 (16 hours on)
- **Data Logging:** Every 30 seconds
- **Chart Update:** Every 30 seconds
- **Sensor Poll:** Every 5 seconds

---

## 🔐 Security Recommendations

1. **Change Default Credentials:**
   - Consider adding authentication to web interface
   - Secure Tailscale access with ACLs

2. **Firewall Configuration:**
   ```bash
   sudo ufw enable
   sudo ufw allow 8000/tcp
   sudo ufw allow from 100.0.0.0/8  # Tailscale network
   ```

3. **Regular Backups:**
   - Verify GitHub backups are running
   - Test USB backup restoration
   - Keep offsite backup copy

4. **Update System:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

---

**🌱 Happy Growing! Your greenhouse is now fully automated and monitored.**
