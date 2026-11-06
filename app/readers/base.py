"""Common reader interface. Every driver returns TagRead objects so the rest of
the app never cares which hardware is attached."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TagRead:
    epc: str      # tag ID as upper-case hex, e.g. "E28011700000020F5A2B3C4D"
    rssi: float   # received signal strength in dBm (closer to 0 = stronger)
    ts: float     # time.time() when the read happened


class Reader:
    """Interface for a UHF reader driver."""

    name = "base"

    def open(self) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass

    def inventory(self) -> list[TagRead]:
        """Run one inventory cycle (a fraction of a second) and return every tag read."""
        raise NotImplementedError

    def set_power(self, dbm: float) -> None:
        """Set transmit power. Lower power = shorter range."""

    def set_region(self, region: str) -> None:
        """Set the frequency region (US / EU / ...). Must match your country's rules."""

    def info(self) -> str:
        return self.name
