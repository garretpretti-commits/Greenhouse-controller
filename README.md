# 🌱 Greenhouse Monitoring & Control System

Automated greenhouse climate control system using Raspberry Pi 4 and RP2040-Zero microcontrollers with machine learning capabilities.

## 🎯 Features

- **Real-time Monitoring**
  - Temperature & Humidity (DHT22 sensor)
  - 4x Soil Moisture sensors (capacitive)
  - Live web dashboard with graphs

- **Automated Climate Control**
  - ML-based temperature & humidity regulation
  - Controls humidifier, dehumidifier, and heater
  - Manual or automatic modes

- **Light Management**
  - Programmable light cycles
  - Schedule-based or manual control
  - Customizable on/off times

- **Web Dashboard**
  - Real-time sensor readings
  - Historical data visualization
  - Remote control via web interface
  - Accessible via Tailscale VPN

- **Data Logging**
  - SQLite database for sensor history
  - Relay control logging
  - Settings persistence

## 🔧 Hardware Requirements

### Main Controller
- Raspberry Pi 4 (running Raspberry Pi OS)
- SD Card (16GB+ recommended)
- Power supply

### Microcontroller Board 1 (Sensors & Climate Control)
- RP2040-Zero
- DHT22 Temperature/Humidity sensor
- 4x Capacitive Soil Moisture Sensor v2.0
- 4-channel 5V Relay board
- Transistor switching circuit for soil sensor multiplexing

### Controlled Equipment
- Humidifier
- Dehumidifier
- Heater
- Grow light

### Wiring (Board 1)
See [rp2040_board1/README.md](rp2040_board1/README.md) for detailed wiring diagram.

## 📦 Installation

### 1. Install Dependencies on Raspberry Pi

```bash
cd /home/pi/websitephotos

# Install Python dependencies
sudo apt update
sudo apt install python3-pip python3-venv -y

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2. Set Up RP2040 Boards

Follow the instructions in [rp2040_board1/README.md](rp2040_board1/README.md) to:
1. Install CircuitPython on RP2040-Zero
2. Install required libraries
3. Upload the code.py file

### 3. Configure the System

```bash
# Test RP2040 connection
python3 backend/rp2040_interface.py

# If successful, you should see sensor readings
```

### 4. Run the Server

```bash
cd /home/pi/websitephotos
source venv/bin/activate
python3 backend/app.py
```

The server will start on port 8000. Access the dashboard at:
- Local: `http://localhost:8000`
- Network: `http://<raspberry-pi-ip>:8000`
- Tailscale: `http://garretsrpi.tailf0f567.ts.net:8000`

## 🚀 Auto-Start on Boot

Create a systemd service to run the greenhouse controller automatically:

```bash
sudo nano /etc/systemd/system/greenhouse.service
```

Add the following content:

```ini
[Unit]
Description=Greenhouse Controller
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/websitephotos
Environment="PATH=/home/pi/websitephotos/venv/bin"
ExecStart=/home/pi/websitephotos/venv/bin/python3 /home/pi/websitephotos/backend/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl enable greenhouse.service
sudo systemctl start greenhouse.service

# Check status
sudo systemctl status greenhouse.service

# View logs
sudo journalctl -u greenhouse.service -f
```

## 📊 System Architecture

```
┌─────────────────────────────────────────────┐
│         Raspberry Pi 4                      │
│  ┌────────────────────────────────────┐    │
│  │  Flask Web Server (Port 8000)      │    │
│  │  - API Endpoints                   │    │
│  │  - Dashboard UI                    │    │
│  └─────────────┬──────────────────────┘    │
│                │                             │
│  ┌─────────────▼──────────────────────┐    │
│  │  Climate Controller                │    │
│  │  - ML-based control logic          │    │
│  │  - Target temp/humidity            │    │
│  └─────────────┬──────────────────────┘    │
│                │                             │
│  ┌─────────────▼──────────────────────┐    │
│  │  RP2040 Interface                  │    │
│  │  - USB Serial Communication        │    │
│  └─────────────┬──────────────────────┘    │
└────────────────┼──────────────────────────┘
                 │ USB
    ┌────────────▼────────────┐
    │  RP2040-Zero Board 1    │
    │  - DHT22 Sensor         │
    │  - 4x Soil Sensors      │
    │  - 4x Relays            │
    └─────────────────────────┘
```

## 🎮 Usage

### Manual Control
1. Access the web dashboard
2. Ensure climate control is in "Manual" mode
3. Toggle individual devices (humidifier, dehumidifier, heater)

### Automatic Climate Control
1. Click "Auto" mode button
2. Set target temperature and tolerance
3. Set target humidity and tolerance
4. Click "Save Settings"
5. System will automatically maintain conditions

### Light Scheduling
1. Click "Schedule" mode for light control
2. Set ON time (e.g., 06:00)
3. Set OFF time (e.g., 22:00)
4. Click "Save Schedule"

## 🔄 Backup System

Automatic backups are configured:

**Git + GitHub Backup:**
- Runs every 4 hours
- Pushes code to: https://github.com/garretpretti-commits/Greenhouse-controller

**USB Backup:**
- Runs daily at 2:00 AM
- Saves to `/media/usb_backup/`

**Manual Backup Commands:**
```bash
# Push to GitHub
/home/pi/git_backup.sh

# Backup to USB
/home/pi/backup_greenhouse.sh
```

## 📝 API Endpoints

### Sensors
- `GET /api/sensors/current` - Current sensor readings
- `GET /api/sensors/history?hours=24` - Historical data

### Relays
- `GET /api/relays` - Get relay states
- `POST /api/relays/<name>` - Control relay

### Climate Control
- `GET/POST /api/climate/mode` - Get/set mode (manual/auto)
- `GET/POST /api/climate/settings` - Get/update settings

### Light Control
- `GET/POST /api/light/mode` - Get/set mode (manual/schedule)
- `GET/POST /api/light/schedule` - Get/update schedule

### System
- `GET /api/status` - System status

## 🐛 Troubleshooting

### RP2040 Not Detected
```bash
# Check USB connection
lsusb | grep 2e8a

# Check serial port
ls /dev/ttyACM*

# Add user to dialout group
sudo usermod -a -G dialout pi
# Logout and login again
```

### Sensor Read Errors
- Check DHT22 wiring (Data to GPIO13)
- Verify 3.3V power connection
- Ensure proper grounding

### Relays Not Responding
- Verify 5V power to relay board
- Check active-low logic (LOW = ON)
- Test relays manually

### Web Dashboard Not Accessible
```bash
# Check if server is running
sudo systemctl status greenhouse.service

# Check firewall
sudo ufw allow 8000/tcp

# View logs
sudo journalctl -u greenhouse.service -f
```

## 📚 Project Structure

```
websitephotos/
├── backend/
│   ├── app.py                  # Flask server
│   ├── rp2040_interface.py     # RP2040 communication
│   ├── climate_controller.py   # ML climate control
│   └── database.py             # Database operations
├── frontend/
│   ├── templates/
│   │   └── index.html          # Main dashboard
│   └── static/
│       ├── css/
│       │   └── style.css       # Styles
│       └── js/
│           └── dashboard.js    # Dashboard logic
├── rp2040_board1/
│   ├── code.py                 # CircuitPython code
│   └── README.md               # Setup instructions
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🔐 Security Notes

- The web interface runs without authentication
- For production use, consider adding authentication
- Use Tailscale VPN for secure remote access
- Keep backup systems updated

## 📄 License

This project is for personal use. Modify as needed for your greenhouse setup.

## 🤝 Contributing

This is a personal project, but feel free to fork and adapt for your own greenhouse!

## 📞 Support

For issues with this specific installation, check the logs:
```bash
sudo journalctl -u greenhouse.service -f
```

---

**Built with ❤️ for automated greenhouse management**
