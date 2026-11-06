"""Background thread that keeps the reader running and remembers what it has seen.

The web screens never touch the serial port; they ask the Scanner for a snapshot.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from readers import Reader

HISTORY = 120  # samples kept per tag for the signal graph


class TagState:
    __slots__ = ("epc", "first_seen", "last_seen", "rssi_hist", "read_times")

    def __init__(self, epc: str, ts: float):
        self.epc = epc
        self.first_seen = ts
        self.last_seen = ts
        self.rssi_hist: deque[tuple[float, float]] = deque(maxlen=HISTORY)
        self.read_times: deque[float] = deque(maxlen=400)


class Scanner(threading.Thread):
    def __init__(self, reader_factory, settings_getter):
        super().__init__(daemon=True, name="scanner")
        self.reader_factory = reader_factory
        self.settings_getter = settings_getter
        self.lock = threading.Lock()
        self.tags: dict[str, TagState] = {}
        self.status = "starting"
        self.error = ""
        self.reader_info = ""
        self.cycles = 0
        self._stop = threading.Event()
        self._pending: dict[str, object] = {}

    # -- called from web threads ----------------------------------------
    def request(self, key: str, value) -> None:
        """Queue a reader setting change (power/region); applied by the scanner thread."""
        with self.lock:
            self._pending[key] = value

    def stop(self) -> None:
        self._stop.set()

    def clear(self) -> None:
        with self.lock:
            self.tags.clear()

    def snapshot(self) -> dict[str, dict]:
        """Per-tag summary used by every screen."""
        s = self.settings_getter()
        now = time.time()
        smooth_n = max(1, int(s["smoothing"]))
        out = {}
        with self.lock:
            for epc, t in self.tags.items():
                recent = [r for _, r in list(t.rssi_hist)[-smooth_n:]]
                rssi_avg = sum(recent) / len(recent) if recent else None
                age = now - t.last_seen
                rate = sum(1 for x in t.read_times if now - x <= 2.0) / 2.0
                if age > s["presence_timeout"]:
                    state = "missing"
                elif rssi_avg is not None and rssi_avg < s["min_rssi"]:
                    state = "weak"
                else:
                    state = "present"
                out[epc] = {
                    "epc": epc,
                    "state": state,
                    "rssi": round(rssi_avg, 1) if rssi_avg is not None else None,
                    "rssi_last": t.rssi_hist[-1][1] if t.rssi_hist else None,
                    "age": round(age, 1),
                    "reads_per_s": rate,
                    "history": [[round(ts - now, 1), r] for ts, r in t.rssi_hist],
                }
        return out

    # -- scanner thread -------------------------------------------------
    def _apply_pending(self, reader: Reader) -> None:
        with self.lock:
            pending, self._pending = self._pending, {}
        for key, value in pending.items():
            try:
                if key == "power":
                    reader.set_power(float(value))
                elif key == "region":
                    reader.set_region(str(value))
            except Exception as e:  # keep scanning even if a setting fails
                self.error = f"Could not set {key}: {e}"

    def run(self) -> None:
        while not self._stop.is_set():
            reader = None
            try:
                self.status = "connecting"
                reader = self.reader_factory()
                reader.open()
                s = self.settings_getter()
                self._pending.setdefault("region", s["region"])
                self._pending.setdefault("power", s["tx_power"])
                self.reader_info = reader.info()
                self.status, self.error = "running", ""
                while not self._stop.is_set():
                    self._apply_pending(reader)
                    reads = reader.inventory()
                    self.cycles += 1
                    with self.lock:
                        for r in reads:
                            t = self.tags.get(r.epc)
                            if t is None:
                                t = self.tags[r.epc] = TagState(r.epc, r.ts)
                            t.last_seen = r.ts
                            t.rssi_hist.append((r.ts, r.rssi))
                            t.read_times.append(r.ts)
                        # forget tags not seen for 10 minutes
                        cutoff = time.time() - 600
                        for epc in [e for e, t in self.tags.items() if t.last_seen < cutoff]:
                            del self.tags[epc]
            except Exception as e:
                self.status, self.error = "error", str(e)
                if reader:
                    reader.close()
                self._stop.wait(3)  # retry, e.g. after the USB reader is re-plugged
            else:
                if reader:
                    reader.close()
