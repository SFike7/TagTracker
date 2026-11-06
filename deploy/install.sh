#!/usr/bin/env bash
# One-time installer for TagTrack on Raspberry Pi OS (64-bit, desktop).
# Run as your normal user (not root) from inside the project folder:
#     bash deploy/install.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="$(id -un)"
if [ "$USER_NAME" = "root" ]; then echo "Run this as your normal user, not with sudo."; exit 1; fi

echo "==> Installing system packages"
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip

echo "==> Allowing $USER_NAME to use serial ports (USB reader)"
sudo usermod -aG dialout "$USER_NAME"

echo "==> Creating Python virtual environment"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/config.json" ]; then
  cp "$APP_DIR/config.example.json" "$APP_DIR/config.json"
  if ! ls /dev/ttyUSB* /dev/ttyACM* >/dev/null 2>&1; then
    sed -i 's/"reader": "m100"/"reader": "mock"/' "$APP_DIR/config.json"
    echo "    No USB reader detected -> config.json set to the SIMULATED reader."
    echo "    Edit config.json (\"reader\": \"m100\") once the UHF module is plugged in."
  fi
fi

echo "==> Installing systemd service (starts the app at boot)"
sudo tee /etc/systemd/system/tagtrack.service >/dev/null <<EOF
[Unit]
Description=TagTrack RFID app
After=network.target

[Service]
User=$USER_NAME
SupplementaryGroups=dialout
WorkingDirectory=$APP_DIR/app
ExecStart=$APP_DIR/.venv/bin/python app.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now tagtrack.service

echo "==> Setting up full-screen kiosk on the touchscreen"
chmod +x "$APP_DIR/deploy/kiosk.sh"
LINE="$APP_DIR/deploy/kiosk.sh &"
# labwc is the desktop on current Raspberry Pi OS releases
mkdir -p "$HOME/.config/labwc"
touch "$HOME/.config/labwc/autostart"
grep -qF "$APP_DIR/deploy/kiosk.sh" "$HOME/.config/labwc/autostart" || echo "$LINE" >> "$HOME/.config/labwc/autostart"
# older Bookworm images used Wayfire
if [ -f "$HOME/.config/wayfire.ini" ] && ! grep -qF "kiosk.sh" "$HOME/.config/wayfire.ini"; then
  grep -q '^\[autostart\]' "$HOME/.config/wayfire.ini" || printf '\n[autostart]\n' >> "$HOME/.config/wayfire.ini"
  sed -i "/^\[autostart\]/a tagtrack = $APP_DIR/deploy/kiosk.sh" "$HOME/.config/wayfire.ini"
fi

echo
echo "Done. Reboot to start the kiosk:  sudo reboot"
echo "App logs:                         journalctl -u tagtrack -f"
