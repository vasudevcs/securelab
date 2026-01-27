#!/bin/bash

set -e

echo "🧹 SecureLab Agent Uninstaller"
echo "------------------------------"

if [[ $EUID -ne 0 ]]; then
   echo "❌ Please run as root (sudo bash uninstall.sh)"
   exit 1
fi

echo "[+] Stopping SecureLab agent (if running)"
systemctl stop securelab-agent 2>/dev/null || true

echo "[+] Disabling SecureLab agent"
systemctl disable securelab-agent 2>/dev/null || true

echo "[+] Removing systemd service file"
rm -f /etc/systemd/system/securelab-agent.service

echo "[+] Reloading systemd"
systemctl daemon-reload

echo "[+] Removing SecureLab directory"
rm -rf /opt/securelab

echo "--------------------------------"
echo "✅ SecureLab Agent removed successfully"
echo ""
echo "ℹ️ Dashboard server is NOT affected"
