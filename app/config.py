"""Hardware/deployment config (things that need a restart). Tuning values that you
change while testing (power, thresholds) live in the Settings screen instead."""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

DEFAULTS = {
    "reader": "mock",              # "mock" (simulated) or "m100" (real UHF module)
    "serial_port": "/dev/ttyUSB0", # USB reader. GPIO UART is /dev/serial0
    "baud": 115200,
    "host": "127.0.0.1",           # use "0.0.0.0" to also open the screens from a phone
    "port": 8080,
    "db_path": os.path.join(ROOT, "tagtrack.db"),
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    path = os.environ.get("TAGTRACK_CONFIG", os.path.join(ROOT, "config.json"))
    if os.path.exists(path):
        with open(path) as f:
            cfg.update(json.load(f))
    for key in DEFAULTS:  # env vars win, e.g. TAGTRACK_READER=mock
        env = os.environ.get("TAGTRACK_" + key.upper())
        if env:
            cfg[key] = type(DEFAULTS[key])(env)
    return cfg
