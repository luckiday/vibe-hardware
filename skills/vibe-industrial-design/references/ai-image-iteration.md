# Iterating with an image model (the outbound leg of the loop)

The main loop assumes look images arrive **from** the owner. The other direction is worth
automating: send the **current parametric render** to an image model and get the next look
back. The proposal then starts from true proportions instead of the model's imagination,
and the owner reviews a picture of *their* product rather than a mood board.

```
params.js ──► three.js render ──► PNG on disk ──► image model ──► look image(s)
    ▲                              (2 angles)     (as reference)        │
    └──────── measure ◄──────── owner picks a direction ◄───────────────┘
```

## 0. Get the render out of the browser without a human in the middle

`scripts/serve.py` already takes `POST /save?name=` → `out/`. From the page:

```js
cam.set(view); requestAnimationFrame(() => requestAnimationFrame(() => {
  canvas.toBlob(b => fetch('/save?name=draft-45.png', {method:'POST', body:b}), 'image/png');
}));
```

Two nested `requestAnimationFrame`s after moving the camera, or you capture the *previous*
view — the same one-frame lag as the contact sheet. Send **two angles** (a 3/4 and a
straight-on front). From one view the model has to guess the depth, and it guesses
generously: a 38 mm slab comes back 80 mm deep.

Any page can do this, not just the scene — a `<canvas>`, a captured tab, a photo of a
mock-up. What matters is that the bytes reach disk without someone dragging a file.

## 1. `edit` vs `generate` — the decision that costs a round

- **`edit`, current render as reference** — refine *within* the form: add a control,
  restate a proportion, try a CMF, recess something. Proportions and existing features
  survive because the model is looking at them.
- **`generate`, text only** — deliberately *leave* the form.

**Reaching for `edit` when you actually needed a new form is the expensive mistake.** The
reference drags the old silhouette along; you get the same box with a different button,
and it reads as "we explored three options" in review when nothing was explored. If the
brief moved — new mounting, new posture, new user, new hand — drop the reference image and
describe the product from the requirements instead.

## 2. Three prompts, not three samples

`-n 3` returns three samples of *one* prompt: small random differences nobody can choose
between. A review needs **directions**. Write one prompt per direction, sharing a literal
`BASE` and `STYLE` string, and vary only the middle:

```
BASE    every feature that must survive, enumerated, with where it sits
NEW     the one thing this direction changes
STYLE   camera, light, backdrop, material feel — and the exclusions
```

Same `BASE`/`STYLE` across the set = a controlled comparison. The owner is then choosing
between ideas rather than between lighting accidents, and the set can go in the report
side by side.

## 3. Enumerate what must survive, or lose it

An image model **simplifies silently**. Anything not named in `BASE` may quietly vanish or
drift: the vent field, the feet, the port row, the indicator line on a knob. Name each one
*and its position* ("on the right third", "at the top edge", "a row below the vents").
What you don't name is not preserved — it is re-imagined.

The same applies to the thing you're actually changing: give it a size in mm, a colour, a
surface, and how it meets the surrounding surface (flush / proud / in a recess, and the
gap). "A big emergency button" gets you a different button every run.

## 4. Always exclude text

Image models write. Without an explicit *"no text, no letters, no numbers, no logos, no
brand names, no screens"* you get plausible lettering, invented brand marks, and a display
on a device that has none. Every one of those then has to be argued away in review, and
one of them will survive into a slide deck.

## 5. The output is a proposal with unchecked physics

The model will happily put a thermal sensor behind a glossy dark panel, a mic where the
speaker's back volume is, and an antenna inside a metallised bezel. It is drawing what
those things *look like*, not what they do. Run every adopted direction past
`references/appearance-vs-physics.md` before it reaches `params.js` — that check is
cheap on an image and expensive on a mould.

## 6. Keep the prompt with the picture

Save each generated image as `refs/NN-<version>-<direction>.png` and put the prompt in the
report's version log next to it. **A picture without its prompt cannot be iterated, only
replaced** — and six weeks later "make it a bit warmer than that one" is unanswerable.

Also keep the losing directions. The version log's job is to record what was rejected and
why; a direction that was dropped for a reason that later stops applying is the cheapest
idea you will ever have.
