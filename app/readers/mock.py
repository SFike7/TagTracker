"""Simulated UHF reader so you can build and test the screens before hardware arrives.

Eight fake tags drift in signal strength; now and then one "walks away" for a
while so you can watch the testing screen flag it as missing.
"""
from __future__ import annotations

import random
import time

from .base import Reader, TagRead


class _FakeTag:
    def __init__(self, epc: str):
        self.epc = epc
        self.base = random.uniform(-72, -48)
        self.rssi = self.base
        self.away_until = 0.0


class MockReader(Reader):
    name = "mock"

    def __init__(self, n_tags: int = 8, cycle_s: float = 0.3):
        self.cycle_s = cycle_s
        self.power = 20.0
        self.tags = [_FakeTag(f"E2801170000002{0x0A3F10 + i * 0x111:06X}{i:04X}") for i in range(n_tags)]

    def open(self) -> None:
        pass

    def inventory(self) -> list[TagRead]:
        time.sleep(self.cycle_s)
        now = time.time()
        reads = []
        for t in self.tags:
            if t.away_until > now:
                continue
            if random.random() < 0.004:  # ~ once every couple of minutes per tag
                t.away_until = now + random.uniform(8, 20)
                continue
            t.rssi += random.uniform(-2.5, 2.5) + (t.base - t.rssi) * 0.15
            rssi = t.rssi + (self.power - 20.0)
            if random.random() < 0.85:  # real readers miss tags on some rounds
                reads.append(TagRead(epc=t.epc, rssi=round(rssi, 1), ts=now))
        return reads

    def set_power(self, dbm: float) -> None:
        self.power = float(dbm)

    def info(self) -> str:
        return f"Simulated reader ({len(self.tags)} fake tags)"
