#!/usr/bin/env python3
"""Bench test for the UHF module, without the app.

    python tools/reader_check.py                 # /dev/ttyUSB0, 115200 baud
    python tools/reader_check.py --port /dev/serial0 --power 18 --region US

Prints firmware info, then every tag read (EPC + RSSI) for --seconds.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
from readers.m100 import M100Reader  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--port", default="/dev/ttyUSB0")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--power", type=float, default=20)
    p.add_argument("--region", default="US")
    p.add_argument("--seconds", type=float, default=15)
    a = p.parse_args()

    r = M100Reader(a.port, a.baud)
    print(f"Opening {a.port} @ {a.baud}…")
    r.open()
    print("OK:", r.info())
    r.set_region(a.region)
    r.set_power(a.power)
    print(f"Region {a.region}, power {a.power} dBm. Reading for {a.seconds:.0f} s (Ctrl+C to stop)…\n")
    seen = {}
    end = time.time() + a.seconds
    try:
        while time.time() < end:
            for t in r.inventory():
                s = seen.setdefault(t.epc, [0, -999.0])
                s[0] += 1
                s[1] = max(s[1], t.rssi)
                print(f"{time.strftime('%H:%M:%S')}  {t.epc}  {t.rssi:6.1f} dBm")
    except KeyboardInterrupt:
        pass
    finally:
        r.close()
    print(f"\n{len(seen)} unique tag(s):")
    for epc, (n, best) in sorted(seen.items(), key=lambda kv: -kv[1][1]):
        print(f"  {epc}  reads={n:4d}  best={best:.0f} dBm")


if __name__ == "__main__":
    main()
