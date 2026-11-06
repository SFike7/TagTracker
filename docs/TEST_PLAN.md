# Prototype test plan

The goal of the first builds isn't "does the app work" (the simulated reader proves that). It's
**can a UHF reader tell "in the bag" apart from "left behind" reliably enough that people would
trust it?** Two failure types matter, and they are not equally bad:

| Failure | Example | Cost |
|---|---|---|
| **False "present"** | Skates on the hallway floor read as present | **Severe.** The product's whole promise fails silently, and you leave without them |
| False "missing" | Helmet in the bag but blocked by wet pads | Annoying. Users start ignoring alerts |

Prioritise driving false "present" to zero, then reduce false "missing".

Before each run: Settings → *Clear read history*, and note the power, threshold and antenna position.

## Tests

**T1: Open-air range per tag type.** Tag in free air, facing the antenna. At power 15 / 20 / 26 dBm,
find the farthest distance where it stays PRESENT for 30 s. Repeat for each tag type: inlay,
on-metal, laundry.
*Tells you:* the baseline range, and which tags are worth using.

**T2: Full bag, closed.** Every item in the bag, bag zipped, device in its intended spot. Watch the
Checklist for 60 s and count the items that ever drop to MISSING or WEAK. Repeat 5×, re-packing the
bag differently each time.
*Pass:* every item PRESENT within 10 s, with no dropouts.

**T3: Left-behind detection (the critical test).** Remove one item and place it 0.5 m, 1 m, 2 m and
3 m from the bag (floor, a chair, the other side of a wall). Record its state and RSSI. Repeat for
the item whose tag is weakest in the bag.
*Pass:* MISSING or WEAK at ≥ 1 m, and the in-bag RSSI of every other item stays above the threshold.

**T4: Hard materials.** Golf: tags on heads, shafts and grips, clubs bunched together in the bag.
Hockey: gear damp after a session. School: tag inside a metal water bottle vs. on the outside.
*Tells you:* placement rules per item.

**T5: Body and handling.** Bag worn or carried while you stand next to the device. Bodies absorb UHF.

**T6: Neighbouring tags.** Two tagged bags side by side, e.g. siblings' school bags. Check that
items from the other bag show under *Other tags in range* only, and never in this bag's checklist.

**T7: Power and runtime** (portable builds). Run from a power bank with the app scanning
continuously, and record the hours until shutdown.

## Results sheet (copy per prototype)

| Test | Unit | Antenna / position | Power dBm | Threshold dBm | Tag type | Result (state, RSSI, distance) | Notes |
|---|---|---|---|---|---|---|---|
| T1 | tagtrack-1 | patch, 0 cm | 20 | -75 | inlay | | |
| T2 | | | | | | | |
| T3 | | | | | | | |

## Open questions these tests should answer

1. Do in-bag and out-of-bag RSSI ranges separate cleanly at some power level? If they overlap, a
   single reader in the bag can't do the job, and the product may need a **door/car-mounted "exit
   check"** instead: items read passing the door = taken.
2. Which tag types survive a season of sweat, washing and club impacts?
3. Where does the device live, and how is it powered day to day? This drives the enclosure,
   battery size, and whether a Pi is overkill for the final product (a microcontroller plus the same
   UHF module draws much less power).
