#!/bin/bash

set -e

echo "🔐 SecureLab Agent Installer"
echo "----------------------------"

if [[ $EUID -ne 0 ]]; then
   echo "❌ Please run as root (sudo bash install.sh)"
   exit 1
fi

read -p "Enter DASHBOARD IP (example: 192.168.1.10): " DASHBOARD_IP

echo "[+] Creating /opt/securelab"
mkdir -p /opt/securelab

echo "[+] Copying agent files"
cp agent.py requirements.txt securelab-agent.service /opt/securelab/

echo "[+] Updating SERVER_URL in agent.py"
sed -i "s|SERVER_URL = .*|SERVER_URL = \"http://${DASHBOARD_IP}:5000/event\"|" /opt/securelab/agent.py

echo "[+] Installing system packages"
apt update
apt install -y python3 python3-venv python3-pip

echo "[+] Creating Python virtual environment"
python3 -m venv /opt/securelab/venv

echo "[+] Installing Python dependencies"
source /opt/securelab/venv/bin/activate
pip install -r /opt/securelab/requirements.txt

echo "[+] Installing systemd service"
cp /opt/securelab/securelab-agent.service /etc/systemd/system/securelab-agent.service
systemctl daemon-reload
systemctl enable securelab-agent

echo "[+] Starting SecureLab agent"
systemctl start securelab-agent

echo "----------------------------------------"
echo "✅ SecureLab Agent Installed Successfully"
echo ""
echo "⚠️ IMPORTANT:"
echo "Run this ONCE to create baseline:"
echo "sudo /opt/securelab/venv/bin/python /opt/securelab/agent.py"
echo ""
echo "Then restart the agent:"
echo "sudo systemctl restart securelab-agent"
