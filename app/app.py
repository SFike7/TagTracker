"""TagTrack - touchscreen app for registering UHF RFID tags and checking a bag.

Run:  python app.py            (uses config.json / defaults)
      TAGTRACK_READER=mock python app.py   (simulated reader)
"""
from __future__ import annotations

import sqlite3
import time

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, url_for

import config
from db import DB
from readers import make_reader
from scanner import Scanner

CFG = config.load()
db = DB(CFG["db_path"])
scanner = Scanner(lambda: make_reader(CFG), db.settings)

app = Flask(__name__)
app.secret_key = "tagtrack-local-prototype"  # only used for flash messages

QUICK_NAMES = {
    "Hockey": ["Helmet", "Skates", "Gloves", "Shin pads", "Elbow pads", "Shoulder pads",
               "Pants", "Jersey", "Socks", "Jock", "Neck guard", "Mouthguard", "Water bottle", "Tape"],
    "Golf": ["Driver", "3 wood", "5 wood", "Hybrid", "4 iron", "5 iron", "6 iron", "7 iron",
             "8 iron", "9 iron", "PW", "SW", "Putter", "Rangefinder", "Glove"],
    "School": ["Lunch box", "Water bottle", "Pencil case", "Homework folder", "Library book",
               "Gym clothes", "Jacket", "Laptop", "Calculator"],
}


def _kit_id(value):
    return int(value) if value not in (None, "", "none") else None


@app.context_processor
def inject_globals():
    return {"reader_status": scanner.status, "reader_kind": CFG["reader"],
            "text_scale": db.settings()["text_scale"]}


# -- Menu ----------------------------------------------------------------
@app.get("/")
def home():
    return render_template("home.html", kits=db.kits(), n_items=len(db.items()))


# -- Items ---------------------------------------------------------------
@app.get("/items")
def items():
    kit = request.args.get("kit")
    kit_id = _kit_id(kit)
    return render_template("items.html", items=db.items(kit_id), kits=db.kits(), kit_id=kit_id)


@app.get("/items/add")
def item_add():
    return render_template("item_form.html", item=None, kits=db.kits(), quick=QUICK_NAMES,
                           epc=request.args.get("epc", ""), kit_id=_kit_id(request.args.get("kit")))


@app.post("/items/add")
def item_add_post():
    name = request.form.get("name", "").strip()
    epc = request.form.get("epc", "").strip().upper()
    kit_id = _kit_id(request.form.get("kit_id"))
    if not name or not epc:
        flash("Scan a tag and give the item a name.", "error")
        return redirect(url_for("item_add", epc=epc, kit=kit_id or ""))
    try:
        db.add_item(name, epc, kit_id, request.form.get("notes", ""))
    except sqlite3.IntegrityError:
        existing = db.item_by_epc(epc)
        flash(f"That tag is already registered as “{existing['name']}”.", "error")
        return redirect(url_for("item_add", kit=kit_id or ""))
    flash(f"Added “{name}”.", "ok")
    if request.form.get("another"):
        return redirect(url_for("item_add", kit=kit_id or ""))
    return redirect(url_for("items", kit=kit_id or ""))


@app.get("/items/<int:item_id>")
def item_edit(item_id):
    item = db.item(item_id) or abort(404)
    return render_template("item_form.html", item=item, kits=db.kits(), quick=QUICK_NAMES,
                           epc=item["epc"], kit_id=item["kit_id"])


@app.post("/items/<int:item_id>")
def item_edit_post(item_id):
    db.item(item_id) or abort(404)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Name can't be empty.", "error")
        return redirect(url_for("item_edit", item_id=item_id))
    db.update_item(item_id, name, _kit_id(request.form.get("kit_id")), request.form.get("notes", ""))
    flash(f"Saved “{name}”.", "ok")
    return redirect(url_for("items"))


@app.post("/items/<int:item_id>/delete")
def item_delete(item_id):
    item = db.item(item_id) or abort(404)
    db.delete_item(item_id)
    flash(f"Deleted “{item['name']}”.", "ok")
    return redirect(url_for("items"))


# -- Kits (bags) ---------------------------------------------------------
@app.get("/kits")
def kits():
    return render_template("kits.html", kits=db.kits())


@app.post("/kits")
def kit_add():
    name = request.form.get("name", "").strip()
    if name:
        try:
            db.add_kit(name)
            flash(f"Created bag “{name}”.", "ok")
        except sqlite3.IntegrityError:
            flash("A bag with that name already exists.", "error")
    return redirect(url_for("kits"))


@app.post("/kits/<int:kit_id>/rename")
def kit_rename(kit_id):
    name = request.form.get("name", "").strip()
    if name:
        try:
            db.rename_kit(kit_id, name)
        except sqlite3.IntegrityError:
            flash("A bag with that name already exists.", "error")
    return redirect(url_for("kits"))


@app.post("/kits/<int:kit_id>/delete")
def kit_delete(kit_id):
    db.delete_kit(kit_id)
    flash("Bag deleted (its items were kept, now unassigned).", "ok")
    return redirect(url_for("kits"))


# -- Testing / tracking screen ------------------------------------------
@app.get("/track")
def track():
    kits_ = db.kits()
    kit_id = _kit_id(request.args.get("kit"))
    if kit_id is None and kits_:
        kit_id = kits_[0]["id"]
    return render_template("track.html", kits=kits_, kit=db.kit(kit_id) if kit_id else None)


# -- Settings -----------------------------------------------------------
@app.get("/settings")
def settings():
    return render_template("settings.html", s=db.settings(), cfg=CFG,
                           reader_info=scanner.reader_info, error=scanner.error, cycles=scanner.cycles)


@app.post("/settings")
def settings_post():
    current = db.settings()
    for key, default in current.items():
        if key in request.form:
            raw = request.form[key]
            try:
                value = type(default)(raw)
            except ValueError:
                flash(f"Invalid value for {key}.", "error")
                continue
            if key == "text_scale":
                value = round(min(3.0, max(0.8, value)), 2)
            db.save_setting(key, value)
            if key == "tx_power" and value != current[key]:
                scanner.request("power", value)
            if key == "region" and value != current[key]:
                scanner.request("region", value)
    flash("Settings saved.", "ok")
    return redirect(url_for("settings"))


@app.post("/settings/clear")
def settings_clear():
    scanner.clear()
    flash("Cleared read history.", "ok")
    return redirect(url_for("settings"))


# -- JSON API used by the live screens ----------------------------------
@app.get("/api/status")
def api_status():
    return jsonify(status=scanner.status, error=scanner.error, info=scanner.reader_info, cycles=scanner.cycles)


@app.get("/api/nearest")
def api_nearest():
    """Strongest tag seen in the last 2 s that isn't registered yet (for 'Scan tag')."""
    known = db.known_epcs()
    snap = scanner.snapshot()
    fresh = [t for t in snap.values() if t["age"] <= 2.0 and t["rssi"] is not None]
    fresh.sort(key=lambda t: t["rssi"], reverse=True)
    unregistered = [t for t in fresh if t["epc"] not in known]
    return jsonify(
        status=scanner.status,
        nearest=unregistered[0] if unregistered else None,
        others=len(unregistered) - 1 if len(unregistered) > 1 else 0,
        registered_in_range=[{"epc": t["epc"], "name": known[t["epc"]], "rssi": t["rssi"]}
                             for t in fresh if t["epc"] in known][:5],
    )


@app.get("/api/track")
def api_track():
    kit_id = _kit_id(request.args.get("kit"))
    snap = scanner.snapshot()
    rows = []
    for it in db.items(kit_id):
        t = snap.get(it["epc"])
        rows.append({
            "id": it["id"], "name": it["name"], "epc": it["epc"],
            "state": t["state"] if t else "missing",
            "rssi": t["rssi"] if t else None,
            "age": t["age"] if t else None,
            "reads_per_s": t["reads_per_s"] if t else 0,
            "history": t["history"] if t else [],
        })
    order = {"missing": 0, "weak": 1, "present": 2}
    rows.sort(key=lambda r: (order[r["state"]], r["name"].lower()))
    known = db.known_epcs()
    other = [{"epc": t["epc"], "rssi": t["rssi"], "age": t["age"],
              "name": known.get(t["epc"])}
             for t in snap.values() if t["epc"] not in {r["epc"] for r in rows} and t["age"] < 10]
    other.sort(key=lambda t: (t["rssi"] is None, -(t["rssi"] or 0)))
    s = db.settings()
    return jsonify(status=scanner.status, error=scanner.error, items=rows, other=other[:12],
                   min_rssi=s["min_rssi"], now=time.time())


def main():
    scanner.start()
    from waitress import serve
    print(f"TagTrack on http://{CFG['host']}:{CFG['port']}  (reader: {CFG['reader']})")
    serve(app, host=CFG["host"], port=int(CFG["port"]), threads=8)


if __name__ == "__main__":
    main()
