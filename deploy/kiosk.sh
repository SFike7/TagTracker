#!/usr/bin/env bash
# Opens the TagTrack screens full-screen on the Pi touchscreen.
# Started automatically at login by the desktop's autostart (see install.sh).
URL="http://localhost:8080/?kiosk=1"

# wait (up to 60 s) for the app server to come up
for _ in $(seq 60); do
  (exec 3<>/dev/tcp/127.0.0.1/8080) 2>/dev/null && break
  sleep 1
done

BROWSER="$(command -v chromium || command -v chromium-browser)"
exec "$BROWSER" --kiosk --incognito --noerrdialogs --disable-infobars --no-first-run \
  --disable-session-crashed-bubble --disable-features=Translate --overscroll-history-navigation=0 \
  --disable-pinch --password-store=basic "$URL"
