from .base import Reader, TagRead


def make_reader(cfg: dict) -> Reader:
    kind = cfg.get("reader", "mock")
    if kind == "mock":
        from .mock import MockReader
        return MockReader()
    if kind == "m100":
        from .m100 import M100Reader
        return M100Reader(port=cfg.get("serial_port", "/dev/ttyUSB0"), baud=int(cfg.get("baud", 115200)))
    raise ValueError(f"Unknown reader type {kind!r} (use 'mock' or 'm100')")


__all__ = ["Reader", "TagRead", "make_reader"]
