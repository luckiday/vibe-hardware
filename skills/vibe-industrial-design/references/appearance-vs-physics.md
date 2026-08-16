# The constraints that already decided the form

Appearance work fails in two ways that no amount of rendering catches: the form was
already fixed by a document nobody re-read, or a beautiful surface blocks the thing that
has to cross it. Both are cheap to check before the first look image and expensive after
tooling.

## 0. Requirement archaeology, before the first image

The brief is rarely the whole constraint set. Part of the form has usually been decided
elsewhere, by people solving a different problem:

- an **algorithm spec** that assumed a mounting height and pose, then derived every
  threshold from it;
- an **ADR** picking a module that needs an antenna keep-out, a 5 V rail, or a cable to
  somewhere specific;
- a **human-machine contract** naming which control does what — and which two must never
  be confusable;
- a **board contract** fixing where the connectors are, and which indicator the MCU
  *cannot* turn off.

Read them and write the extracted constraints down *before* the first look image, in the
report's §0. Then the picture is judged against them instead of against taste.

**Worked failure.** A perception spec derived its detection thresholds from "wall-mounted
at 1.5 m, lens horizontal, landscape" — the numbers separating *sitting* from *lying on
the floor* were three sensor rows apart, all computed from that height. The appearance
work started from a reference photo of a desktop cube and produced a lovely desktop cube
with feet. Nothing in the render looked wrong. It just quietly invalidated every threshold
in an algorithm that already had regression tests, and none of that surfaces until someone
asks why the two documents disagree.

Symptom of skipping this step: **the review argues about the button colour while the form
is wrong.**

## 1. Does the physics actually pass through your surface?

Every opening is a promise that something crosses the boundary. Check the band, not the
look:

| what crosses | the trap |
|---|---|
| **LWIR** (8–14 µm thermal array) | ordinary plastic, glass and acrylic are **opaque**. A "dark filter-looking panel" over the sensor is a blind device that renders beautifully. Real options: open aperture (dust, insects), silicon window (cost), thin polyethylene film (cheap; costs transmission, and see §4) |
| **NIR** (proximity, ambient light) | the opposite trap — plastics that look solid black can be NIR-transparent, so "it must be blocked, it's black" is wrong in both directions. Ask for the transmission curve |
| **RF** (2.4 GHz, sub-GHz) | metallised paint, EMI coating and foil-backed fabric detune or blind an antenna. The keep-out is a **volume**, not an area on the PCB |
| **sound in** (MEMS mic) | a decorative mesh with no acoustic path behind it; a mic port that shares a cavity with the speaker (it will hear the speaker, not the person) |
| **sound out** | loudness is set by the amplifier rail *and* the back volume. A thin wall-hugging body and "must be audible in the yard" are in direct conflict — decide which one is real, in writing |
| **heat** | see §3 |

Put the answer in the CMF table as a material row, not as a note: the window is a part
with a supplier, not a graphic.

## 2. A recessed window eats the field of view

Sink a window `t` mm behind the outer surface and the shell itself starts clipping the
edges of the field. The clear opening must be at least

```
width  ≥ sensor aperture + 2·t·tan(FOV_h / 2)
height ≥ sensor aperture + 2·t·tan(FOV_v / 2)
```

Worked: a 110° × 75° sensor, sunk 5 mm → ≥ 14.3 mm horizontally and ≥ 7.7 mm vertically,
**plus** the sensor's own aperture. Design the opening from the sink depth; don't sink to
whatever depth looks right and hope.

Symptom when it's wrong: nothing looks broken. The device simply never sees anything near
the edges of the room, and the algorithm gets blamed.

## 3. The enclosure is a thermal environment

A sensor reading absolute temperature reports its **own** temperature, not the room's:
one commodity thermal array measured 36.7 °C on-die in a 28 °C room — self-heating plus
the enclosure. Consequences for the shell:

- don't put a temperature-sensitive part above the regulator or the amplifier; warm air
  rises inside the box too;
- give it a baffle and a path for that air to leave;
- treat any threshold written against "ambient" as suspect if it is actually reading the
  device's own die.

## 4. A window that attenuates is a calibration item

If a window cuts the signal and firmware compensates with a per-unit constant, the window
is **part of the calibrated system**. Three consequences the ID owns:

- **replacing it in the field requires recalibration** — so don't style it as a
  user-removable cover, and write the cleaning method into the manual (wipeable, not
  peelable);
- **it must be flat, taut and uniform** — one scalar constant is shared by the whole
  field, so a wrinkle or a lifted edge means the compensation is wrong on part of the
  image and the algorithm cannot know;
- **it must sit at the temperature the compensation assumes** (usually room temperature),
  which means no heat source behind it and no direct sun or lamp on it.

## 5. The indicator you cannot turn off

Boards often carry a hard-wired power LED the MCU cannot control. It is not a status light
and it will be on all night. In a bedroom that matters: put it on the underside or the
lower edge, diffuse it heavily, or get it changed on the next board spin — but decide,
rather than discovering it at the first home install.

The general form of this one: **enumerate the emitters and openings the firmware does not
own** (power LED, charge LED, a module's own status light, a vent that must exist) and
give each a place, before the form language is settled around the ones you do own.
