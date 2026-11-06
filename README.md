# TagTrack: UHF RFID "is everything in the bag?" prototype

A Raspberry Pi 4B with a touchscreen and a UHF RFID reader. You stick a passive UHF tag on every
item (skates, golf clubs, a lunch box), group the items into a **bag**, and the **Check a bag**
screen shows which items are present, weak, or missing, live.

```
 [UHF tags on items]  ))) radio )))  [UHF antenna + reader module] --USB--> [Pi 4B] --DSI--> [7" touchscreen]
                                                                           Flask app + Chromium kiosk
```

> **Read this first: the main limitation.** UHF radio goes straight through bag fabric. The reader
> can't tell "inside the bag" from "on the floor next to the bag". It only knows a tag answered,
> and how strong the reply was. You tune two knobs (**transmit power** and the **weak threshold**)
> so that items more than ~0.5–1 m away stop counting as present. Whether this is reliable enough
> is the main thing these test builds need to prove. See [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

Confidence labels used below: **[Certain]** well established · **[Likely]** reasonable inference,
verify on your hardware · **[Uncertain]** educated guess (mostly prices and vendor details).

---

## Contents
1. [Parts list](#1-parts-list)
2. [Prepare the SD card](#2-prepare-the-sd-card)
3. [Assemble and first boot](#3-assemble-and-first-boot)
4. [Connect the UHF reader](#4-connect-the-uhf-reader)
5. [Install TagTrack](#5-install-tagtrack)
6. [Bench-test the reader](#6-bench-test-the-reader)
7. [Using the screens](#7-using-the-screens)
8. [Tuning for "in the bag"](#8-tuning-for-in-the-bag)
9. [Maintenance and troubleshooting](#9-maintenance-and-troubleshooting)
10. [How the code is organised](#10-how-the-code-is-organised)

---

## 1. Parts list

Per test unit. Prices are rough 2026 street prices **[Uncertain]**.

| Part | Notes | ~Cost |
|---|---|---|
| Raspberry Pi 4 Model B (2 GB or more) | 2 GB is plenty | $45–55 |
| Official Raspberry Pi USB-C power supply (5.1 V 3 A) | Under-powered supplies cause random USB resets of the reader **[Likely]** | $8–12 |
| microSD card, 32 GB, A1/A2 class | | $8–12 |
| Raspberry Pi touchscreen (original 7" 800×480, or Touch Display 2) | Connects by DSI ribbon. The UI is laid out for 800×480 and scales to other sizes | $60–80 |
| **UHF RFID reader module, M100/QM100 chipset, with USB** | Sold as "UHF RFID module 860–960 MHz UART/USB", "YRM100", "JRD-100" or "R200". **Before buying, confirm the listing or manual shows the `0xBB … 0x7E` frame protocol**: that is what the included driver speaks **[Likely]**. Prefer a board with an SMA/u.FL connector for an external antenna | $25–70 |
| External UHF antenna, 5–6 dBi, circular polarisation, 902–928 MHz (US) or 865–868 MHz (EU) | Small onboard antennas often read only ~10–30 cm **[Uncertain]**; a patch antenna is the biggest range upgrade. Circular polarisation reads tags in any orientation | $25–60 |
| UHF EPC Gen2 tags, assorted | See *Choosing tags* below | $20–60 for a mixed pack |
| (portable tests) USB-C power bank, 5 V 3 A | For in-the-car / at-the-door tests | $25 |

**Upgrade path:** if the cheap module's range or multi-tag reliability isn't good enough, the
SparkFun *Simultaneous RFID Reader* (ThingMagic/JADAK M6E Nano / M7E) is a well-documented step up
(~$200–300 **[Uncertain]**). It needs a second driver in `app/readers/` (not included yet). The rest of
the app doesn't change.

### Choosing tags
Tag choice matters more than the reader **[Likely]**. Standard UHF tags detune and stop working when
stuck directly on metal, or on things that hold water (wet gear, bodies) **[Certain]**.

| Item type | Tag to try |
|---|---|
| Fabric / plastic (school bag items, helmets, pads, lunch boxes) | Standard paper/PET inlay sticker (Impinj Monza / M700-series, NXP UCODE 8/9) |
| Golf club heads and steel shafts, metal water bottles, laptops | **On-metal (anti-metal) tags**: thicker foam-backed tags designed to sit on metal |
| Clothing and gear that gets wet or washed (jerseys, socks, gloves) | **Laundry / textile tags**: flexible, washable, sewn or heat-sealed |
| Skates, sticks | On-metal tag near the blade holder, or a standard tag on the plastic boot/shaft away from tape |

For each prototype, buy a few of every type and compare them with the Signal screen.

### Radio rules
UHF readers transmit, so they are regulated. Set the **Region** to your country (US = FCC 902–928 MHz,
EU = ETSI 865–868 MHz) **[Certain]**, keep power at or below 26 dBm with a ≤ 6 dBi antenna, and buy
a module listed for your region. These are prototypes, not certified products.

---

## 2. Prepare the SD card

1. On your computer, install **Raspberry Pi Imager** from raspberrypi.com/software.
2. **Device:** Raspberry Pi 4. **OS:** *Raspberry Pi OS (64-bit)*, the desktop version (not Lite;
   the kiosk needs the desktop). **Storage:** your microSD card.
3. When it offers OS customisation, choose **Edit settings** and set:
   - Hostname: `tagtrack-1` (use `-2`, `-3` for the other units)
   - Username/password: e.g. `pi` / something you'll remember
   - Wi-Fi network and country (the country also sets the Wi-Fi radio rules)
   - Locale/time zone
   - **Services → Enable SSH** (password authentication)
4. Write the card.

## 3. Assemble and first boot

1. Fit the touchscreen. Connect the DSI ribbon to the Pi's **DISPLAY** connector (not CAMERA) and
   power the screen as its guide describes (pogo pins, or 5 V/GND jumpers to pins 2/4 and 6).
2. Insert the SD card. Power on with the official supply. The first boot takes a few minutes.
3. **Touch Display 2 only:** it is natively portrait. Open *Preferences → Screen Configuration*,
   rotate the DSI screen to landscape, and apply.
4. From your computer, connect over SSH (or open a terminal on the Pi):

```bash
ssh pi@tagtrack-1.local
```

5. Update everything and reboot:

```bash
sudo apt update && sudo apt full-upgrade -y && sudo reboot
```

6. Turn off screen blanking so the screen stays on during tests: `sudo raspi-config` →
   *Display Options* → *Screen Blanking* → *No*.

## 4. Connect the UHF reader

### Option A: USB (recommended)
Screw the antenna on **before** powering the module; transmitting with no antenna can damage
some modules **[Likely]**. Plug the module into a **blue USB 3 port** or a black USB 2 port, then:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

You should see something like `/dev/ttyUSB0`. If nothing shows up, run `dmesg | tail -20` and look for
`cp210x`, `ch341` or `ftdi` lines. The module's USB-serial chip needs to be recognised; all three
work out of the box on Raspberry Pi OS **[Likely]**.

### Option B: GPIO UART (bare module, no USB board)
1. `sudo raspi-config` → *Interface Options* → *Serial Port* → login shell over serial: **No**,
   serial port hardware: **Yes** → reboot.
2. Wire it up. **Check your module's datasheet first:** most take 3.3 V logic, but some need 5 V
   power and some need 3.3 V power.
   - Module TX → Pi GPIO15 / RXD (physical pin 10)
   - Module RX → Pi GPIO14 / TXD (physical pin 8)
   - GND → pin 6
   - VCC → pin 2 (5 V) or pin 1 (3.3 V), per the datasheet
3. Use `/dev/serial0` as the port in step 5.

## 5. Install TagTrack

On the Pi (Pi Connect remote shell or SSH), install git if needed, then download the project into
`~/tagtrack`:

```bash
sudo apt install -y git
```

```bash
git clone https://github.com/SFike7/TagTracker.git ~/tagtrack
```

Then run the installer:

```bash
cd ~/tagtrack && bash deploy/install.sh
```

To get code updates later:

```bash
cd ~/tagtrack && git pull && sudo systemctl restart tagtrack
```

The installer:
- installs Python dependencies into `~/tagtrack/.venv`
- adds your user to the `dialout` group so it can use the serial port
- creates `config.json`, using the **simulated reader** if no USB reader is plugged in
- installs a `tagtrack` systemd service that starts the app at boot
- adds a kiosk launcher so Chromium opens the app full-screen on the touchscreen at login

Check `config.json`, then reboot:

```json
{
  "reader": "m100",
  "serial_port": "/dev/ttyUSB0",
  "baud": 115200,
  "host": "127.0.0.1",
  "port": 8080
}
```

```bash
sudo reboot
```

- `"reader": "mock"` runs the whole UI against 8 fake tags that occasionally "walk away". Use it to
  try the screens before the hardware arrives.
- `"host": "0.0.0.0"` also lets you open the screens from a phone at `http://tagtrack-1.local:8080`.
  There is no login, so do this only on a network you trust.

## 6. Bench-test the reader

Before relying on the app, confirm the module talks and reads tags. Stop the app first so it
releases the serial port:

```bash
sudo systemctl stop tagtrack
```

```bash
cd ~/tagtrack && .venv/bin/python tools/reader_check.py --port /dev/ttyUSB0 --region US --power 20
```

```bash
sudo systemctl start tagtrack
```

Expected output: `OK: M100 UHF on /dev/ttyUSB0 (…firmware…)`, then a line per tag read with its EPC and RSSI.

| Symptom | Likely fix |
|---|---|
| `No answer from UHF module` | Wrong port, or wrong baud rate (try `--baud 57600` or `9600`), TX/RX swapped (UART option), or the module uses a different protocol |
| `Permission denied: /dev/ttyUSB0` | You haven't logged in again since the installer added you to `dialout`. Reboot |
| Opens OK but reads no tags | Antenna not attached or not facing the tag; region mismatch; tag stuck on metal; raise `--power` |
| Reader disconnects at high power | Power supply too weak. Use the official 3 A supply, or a powered USB hub |

## 7. Using the screens

The app starts on the **menu**: *Check a bag*, *Items*, *Bags*, *Settings*. A status pill at the
top right shows `UHF · running` (or `SIM · running` for the simulated reader). It turns red if the
reader drops out, and the app reconnects automatically when it's plugged back in.

**Bags** (start here). Create a bag such as "Hockey bag", "Golf bag" or "Emma's school bag". A bag is a
checklist: every item assigned to it must be detected.

**Items → ＋ Add item** (registering a tag):
1. Hold **one** new tag close to the antenna. The box turns blue and shows its EPC and signal. If
   other unregistered tags are in range, it picks the strongest and tells you how many others it
   sees. Move them away, or lower the power.
2. Tap **Use this tag** (the box turns green).
3. Type a name with the on-screen keyboard, or open **Quick names** (hockey, golf and school presets).
4. Choose the bag, and optionally add notes (e.g. "on-metal tag under grip"), which help when you compare
   tag placements later.
5. Tap **Save**, or **Save & add another** to register a whole bag quickly.

Already-registered tags are ignored while scanning, so you can't register the same tag twice. Tap
any item in the list to rename it, move it to another bag, or delete it.

**Check a bag** (the testing screen), for the selected bag:
- **Checklist tab:** a card per item. Green **PRESENT** = read recently with good signal. Amber
  **WEAK** = read, but weaker than the threshold (maybe outside the bag). Red **MISSING** = no
  read for *Missing after* seconds. The banner sums it up: "✓ All 7 items present" or
  "2 missing: Skates, Helmet".
- **Signal tab:** per-item RSSI plot of the last 30 s, with the weak threshold as a dashed line, and
  reads per second. Below that, **Other tags in range** lists tags from other bags and unregistered
  tags, each with a **Register** shortcut. Use this tab while tuning.

**Settings:** transmit power, weak threshold, missing-after timeout, smoothing and region. These
apply immediately, with no restart. *Clear read history* resets the signal plots between test runs.

To leave the kiosk: plug in a keyboard and press `Alt+F4`, or run `pkill chromium` over SSH.

## 8. Tuning for "in the bag"

The defaults are 20 dBm power, -75 dBm weak threshold, and 5 s until missing. Then for each bag:

1. Put every item in the bag, with the antenna where the device will live (inside the bag facing in,
   or a fixed spot at the door). Everything should show **PRESENT** on the Checklist tab. If an item
   flickers to missing, raise the power or move or replace its tag.
2. Take one item out and put it on the floor about 1 m away. On the Signal tab, see where its RSSI
   lands compared with the items in the bag.
3. Lower the **power** until out-of-bag items drop off or fall below the line, while in-bag items
   stay above it. Then fine-tune the **weak threshold** between the two groups.
4. If the in-bag and out-of-bag RSSI ranges overlap, no setting will separate them reliably. That is
   a real finding: try a different antenna position, lower power, or a "check at the door" setup
   instead.

[docs/TEST_PLAN.md](docs/TEST_PLAN.md) has a structured set of tests and a results sheet for
comparing your prototypes.

## 9. Maintenance and troubleshooting

- App logs:

```bash
journalctl -u tagtrack -f
```

- Restart the app (e.g. after editing `config.json`):

```bash
sudo systemctl restart tagtrack
```

- Data lives in `~/tagtrack/tagtrack.db` (SQLite). Copy it to back up, or delete it to start over.
- Run the self-tests (protocol parser, presence logic, every screen):

```bash
cd ~/tagtrack && .venv/bin/pip install pytest && .venv/bin/python -m pytest -q tests
```

- Kiosk shows "can't reach the app server": the service isn't running. Check `journalctl -u tagtrack`.
- Black screen with no kiosk: if `chromium` was renamed on your OS image, edit `deploy/kiosk.sh`.
  On a desktop that isn't labwc (older images used Wayfire), check that the installer added the autostart entry.

## 10. How the code is organised

```
tagtrack/
├── app/
│   ├── app.py          Flask routes: menu, items, bags, tracking, settings, JSON API
│   ├── scanner.py      background thread: runs inventory, keeps per-tag RSSI history, decides present/weak/missing
│   ├── db.py           SQLite: kits (bags), items, settings
│   ├── config.py       loads config.json (reader type, port), env overrides TAGTRACK_*
│   ├── readers/
│   │   ├── base.py     Reader interface (open / inventory / set_power / set_region)
│   │   ├── m100.py     driver for M100/QM100 UHF modules (0xBB…0x7E serial protocol)
│   │   └── mock.py     simulated reader with 8 fake tags
│   ├── templates/      the screens (Jinja HTML)
│   └── static/         style.css, app.js (live polling, plots, on-screen keyboard)
├── tools/reader_check.py   stand-alone reader bench test
├── deploy/install.sh       installer (venv, systemd service, kiosk autostart)
├── deploy/kiosk.sh         launches Chromium full-screen
├── tests/test_core.py
└── docs/TEST_PLAN.md
```

To add a different reader (e.g. M6E Nano, or BLE for comparison): subclass `Reader` in
`app/readers/`, return `TagRead(epc, rssi, ts)` from `inventory()`, and register it in
`readers/__init__.py`. The screens and presence logic don't change.

To try it on a laptop without a Pi:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
cd app && TAGTRACK_READER=mock ../.venv/bin/python app.py
```

Then open http://localhost:8080 (add `?kiosk=1` to see the on-screen keyboard).
