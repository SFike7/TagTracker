"""Driver for low-cost UHF RFID modules built on the M100 / QM100 chip family
(sold as YRM100, JRD-100, R200 and similar "UHF RFID UART/USB module" boards).

They all speak the same simple serial frame protocol:

    0xBB | Type | Command | PL(2 bytes, big-endian) | Params... | Checksum | 0x7E

    Type: 0x00 = command, 0x01 = response, 0x02 = notification (tag read)
    Checksum = low byte of the sum of Type..last param

Vendors sometimes change the defaults (baud rate, region) - check the manual
that ships with your module if `tools/reader_check.py` gets no answer.
"""
from __future__ import annotations

import time

from .base import Reader, TagRead

HEADER = 0xBB
END = 0x7E

TYPE_COMMAND = 0x00
TYPE_RESPONSE = 0x01
TYPE_NOTICE = 0x02

CMD_GET_INFO = 0x03
CMD_SET_REGION = 0x07
CMD_SINGLE_POLL = 0x22
CMD_MULTI_POLL = 0x27
CMD_STOP_POLL = 0x28
CMD_SET_POWER = 0xB6
CMD_ERROR = 0xFF

REGIONS = {"CN900": 0x01, "US": 0x02, "EU": 0x03, "CN800": 0x04, "KR": 0x06}


def build_frame(cmd: int, params: bytes = b"") -> bytes:
    body = bytes([TYPE_COMMAND, cmd]) + len(params).to_bytes(2, "big") + params
    return bytes([HEADER]) + body + bytes([sum(body) & 0xFF, END])


class FrameParser:
    """Turns a raw byte stream into (type, cmd, params) frames, re-syncing on garbage."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[int, int, bytes]]:
        self.buf.extend(data)
        frames = []
        while True:
            start = self.buf.find(bytes([HEADER]))
            if start < 0:
                self.buf.clear()
                break
            if start:
                del self.buf[:start]
            if len(self.buf) < 7:
                break
            pl = int.from_bytes(self.buf[3:5], "big")
            total = 7 + pl
            if pl > 512:  # nonsense length -> drop this header byte and resync
                del self.buf[0]
                continue
            if len(self.buf) < total:
                break
            frame = bytes(self.buf[:total])
            body = frame[1:-2]
            if frame[-1] == END and (sum(body) & 0xFF) == frame[-2]:
                frames.append((frame[1], frame[2], frame[5:5 + pl]))
                del self.buf[:total]
            else:
                del self.buf[0]
        return frames


def parse_tag_notice(params: bytes, ts: float) -> TagRead | None:
    """Notification params: RSSI(1, signed dBm) | PC(2) | EPC(n) | CRC(2)."""
    if len(params) < 5:
        return None
    rssi = params[0] - 256 if params[0] > 127 else params[0]
    pc = int.from_bytes(params[1:3], "big")
    epc_len = (pc >> 11) * 2  # top 5 bits of PC = EPC length in 16-bit words
    epc = params[3:3 + epc_len]
    if epc_len == 0 or len(epc) != epc_len:
        epc = params[3:-2]  # fall back: everything between PC and CRC
    if not epc:
        return None
    return TagRead(epc=epc.hex().upper(), rssi=float(rssi), ts=ts)


class M100Reader(Reader):
    name = "m100"

    def __init__(self, port: str = "/dev/ttyUSB0", baud: int = 115200, cycle_s: float = 0.3):
        self.port = port
        self.baud = baud
        self.cycle_s = cycle_s
        self.ser = None
        self.parser = FrameParser()
        self._info = ""

    # -- low level -------------------------------------------------------
    def _send(self, cmd: int, params: bytes = b"") -> None:
        self.ser.write(build_frame(cmd, params))

    def _read_frames(self, duration: float) -> list[tuple[int, int, bytes]]:
        frames = []
        deadline = time.time() + duration
        while time.time() < deadline:
            data = self.ser.read(self.ser.in_waiting or 1)
            if data:
                frames.extend(self.parser.feed(data))
        return frames

    def _command(self, cmd: int, params: bytes = b"", wait: float = 0.5) -> bytes | None:
        self.ser.reset_input_buffer()
        self.parser = FrameParser()
        self._send(cmd, params)
        deadline = time.time() + wait
        while time.time() < deadline:
            for ftype, fcmd, fparams in self._read_frames(0.05):
                if ftype == TYPE_RESPONSE and fcmd in (cmd, CMD_ERROR):
                    return fparams if fcmd == cmd else None
        return None

    # -- Reader interface ------------------------------------------------
    def open(self) -> None:
        import serial  # imported here so the mock reader works without pyserial

        self.ser = serial.Serial(self.port, self.baud, timeout=0.02)
        time.sleep(0.1)
        self._command(CMD_STOP_POLL)  # in case it was left streaming
        reply = self._command(CMD_GET_INFO, b"\x00")
        if reply is None:
            self.close()
            raise RuntimeError(
                f"No answer from UHF module on {self.port} at {self.baud} baud "
                "(check cable, port name and baud rate)"
            )
        self._info = reply[1:].decode("ascii", "replace").strip()

    def close(self) -> None:
        if self.ser:
            try:
                self._send(CMD_STOP_POLL)
                self.ser.close()
            except Exception:
                pass
            self.ser = None

    def inventory(self) -> list[TagRead]:
        # Multi-poll: 0x22 reserved byte + number of inventory rounds.
        self._send(CMD_MULTI_POLL, b"\x22" + (50).to_bytes(2, "big"))
        reads = []
        for ftype, fcmd, fparams in self._read_frames(self.cycle_s):
            if ftype == TYPE_NOTICE and fcmd == CMD_SINGLE_POLL:
                tag = parse_tag_notice(fparams, time.time())
                if tag:
                    reads.append(tag)
        self._send(CMD_STOP_POLL)
        self._read_frames(0.02)  # swallow the stop acknowledgement
        return reads

    def set_power(self, dbm: float) -> None:
        dbm = max(10.0, min(26.0, float(dbm)))  # typical safe range for these modules
        self._send(CMD_STOP_POLL)
        if self._command(CMD_SET_POWER, int(dbm * 100).to_bytes(2, "big")) is None:
            raise RuntimeError("Module rejected the power setting")

    def set_region(self, region: str) -> None:
        code = REGIONS.get(region.upper())
        if code is None:
            raise ValueError(f"Unknown region {region!r}; choose one of {sorted(REGIONS)}")
        self._send(CMD_STOP_POLL)
        if self._command(CMD_SET_REGION, bytes([code])) is None:
            raise RuntimeError("Module rejected the region setting")

    def info(self) -> str:
        return f"M100 UHF on {self.port} ({self._info or 'unknown firmware'})"
