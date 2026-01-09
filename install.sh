#!/bin/bash

# Greenhouse Controller Installation Script

echo "╔════════════════════════════════════════════════╗"
echo "║   Greenhouse Controller - Installation         ║"
echo "╚════════════════════════════════════════════════╝"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then 
   echo "Please do not run as root (don't use sudo)"
   exit 1
fi

# Set project directory
PROJECT_DIR="/home/pi/websitephotos"

echo "Step 1: Installing system dependencies..."
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev

echo ""
echo "Step 2: Creating Python virtual environment..."
cd "$PROJECT_DIR"
python3 -m venv venv

echo ""
echo "Step 3: Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Step 4: Setting up systemd service..."
sudo cp greenhouse.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable greenhouse.service

echo ""
echo "Step 5: Adding user to dialout group (for serial communication)..."
sudo usermod -a -G dialout pi

echo ""
echo "╔════════════════════════════════════════════════╗"
echo "║   Installation Complete!                       ║"
echo "╚════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Upload code to RP2040 boards (see rp2040_board1/README.md)"
echo ""
echo "2. Start the service:"
echo "   sudo systemctl start greenhouse.service"
echo ""
echo "3. Check status:"
echo "   sudo systemctl status greenhouse.service"
echo ""
echo "4. View logs:"
echo "   sudo journalctl -u greenhouse.service -f"
echo ""
echo "5. Access dashboard at:"
echo "   http://localhost:8000"
echo "   http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Note: You may need to logout and login for group changes to take effect."
echo ""
