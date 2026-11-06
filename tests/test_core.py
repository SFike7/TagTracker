import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from readers.base import Reader, TagRead  # noqa: E402
from readers.m100 import FrameParser, build_frame, parse_tag_notice  # noqa: E402
from scanner import Scanner  # noqa: E402

# Sample tag notification from the M100 protocol manual.
SAMPLE = bytes.fromhex("BB0222001 1C934003075 1FEB705C5904E3D50D703A76EF7E".replace(" ", ""))


def test_build_frames():
    assert build_frame(0x22) == bytes.fromhex("BB00220000227E")                # single poll
    assert build_frame(0x27, bytes.fromhex("222710")) == bytes.fromhex("BB0027000322271083 7E".replace(" ", ""))
    assert build_frame(0x28) == bytes.fromhex("BB00280000287E")                # stop


def test_parse_notice_with_noise_and_split_chunks():
    p = FrameParser()
    stream = b"\x00\x13garbage" + SAMPLE + SAMPLE
    frames = []
    for i in range(0, len(stream), 5):  # serial data arrives in pieces
        frames += p.feed(stream[i:i + 5])
    assert len(frames) == 2
    ftype, cmd, params = frames[0]
    assert (ftype, cmd) == (0x02, 0x22)
    tag = parse_tag_notice(params, 0)
    assert tag.epc == "30751FEB705C5904E3D50D70"
    assert tag.rssi == -55


def test_bad_checksum_rejected():
    bad = bytearray(SAMPLE)
    bad[-2] ^= 0xFF
    assert FrameParser().feed(bytes(bad)) == []


class FakeReader(Reader):
    def __init__(self):
        self.script = [[TagRead("AA", -50, time.time()), TagRead("BB", -85, time.time())]]

    def open(self):
        pass

    def inventory(self):
        time.sleep(0.02)
        return self.script.pop(0) if self.script else []


def test_scanner_states():
    settings = {"presence_timeout": 0.5, "min_rssi": -75.0, "smoothing": 3, "tx_power": 20.0, "region": "US"}
    s = Scanner(FakeReader, lambda: settings)
    s.start()
    time.sleep(0.15)
    snap = s.snapshot()
    assert s.status == "running"
    assert snap["AA"]["state"] == "present"
    assert snap["BB"]["state"] == "weak"
    time.sleep(0.6)
    assert s.snapshot()["AA"]["state"] == "missing"
    s.stop()


def test_app_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("TAGTRACK_DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("TAGTRACK_READER", "mock")
    import importlib
    import app as appmod
    importlib.reload(appmod)
    c = appmod.app.test_client()
    assert c.get("/").status_code == 200
    c.post("/kits", data={"name": "Hockey bag"})
    kit_id = appmod.db.kits()[0]["id"]
    r = c.post("/items/add", data={"name": "Skates", "epc": "e2801170aa", "kit_id": kit_id})
    assert r.status_code == 302
    dup = c.post("/items/add", data={"name": "Other", "epc": "E2801170AA", "kit_id": kit_id}, follow_redirects=True)
    assert "already registered" in dup.get_data(as_text=True)
    data = c.get(f"/api/track?kit={kit_id}").get_json()
    assert data["items"][0]["name"] == "Skates" and data["items"][0]["state"] == "missing"
    for path in ["/items", "/items/add", "/kits", f"/track?kit={kit_id}", "/settings", "/api/nearest"]:
        assert c.get(path).status_code == 200, path
