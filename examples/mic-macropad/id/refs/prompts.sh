#!/usr/bin/env bash
# v1 look images — three DIRECTIONS, one prompt each (not `-n 3`: three samples of one
# prompt are lighting accidents, three prompts are ideas). BASE and STYLE are literal
# shared strings so the set is a controlled comparison.
#
#   BASE  every feature that must survive, and where it sits (§0 of design-report.md)
#   NEW   the one thing this direction changes — all three answer "what is the rear plateau?"
#   STYLE camera, light, backdrop + the exclusions
set -euo pipefail
GEN="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/skills/image-gen}/scripts/openai_image.py"
OUT="$(cd "$(dirname "$0")" && pwd)"

BASE='A single small desktop macro pad, one product, photographed alone. It is a wide low
slab about 84 mm wide, 64 mm deep and 22 mm tall. Its features, all of which must be
present and in these positions: THREE mechanical keyboard keycaps in ONE single row,
evenly spaced with equal gaps, sitting in the FRONT third of the top face close to the
front edge, left-right centred; the REAR two fifths of the top face is a completely
blank, uninterrupted, flat plateau with nothing on it at all; a USB-C socket centred on
the LEFT side wall but set toward the REAR half of that wall, not in the middle; two
small round recessed bores on the RIGHT side wall, one above the other, toward the rear;
one very small round indicator light at the FRONT-RIGHT corner; a narrow thin slot along
the bottom of the FRONT edge toward the right, a microphone port; four small round feet
lifting the body two millimetres clear of the desk.'

STYLE='Studio product photograph for an industrial design portfolio. Three-quarter view
from slightly above and to the left, so the top face, the front edge and the left side
are all visible. One large soft softbox from the upper left, gentle falloff, a soft
contact shadow under the body. Seamless very light warm grey background. Sharp focus
throughout, neutral accurate colour, crisp machined edges, physically plausible
materials. Absolutely no text, no letters, no numbers, no legends, no logos, no brand
names, no icons, no symbols, no screens, no displays, no knobs, no sliders, no cables,
no hands, no people, no watermark.'

A_NEW='Direction: a machined instrument. The top face is a solid anodised aluminium
plate in warm mid-grey with a fine bead-blasted finish and a crisp chamfered edge, held
down by four visible black hex socket screws, one near each corner. The three keycaps
sit in generously oversized square milled wells cut into the plate, so each key is
surrounded by a deep clean shadow gap. Across the very back of the plate, spanning the
full width, is a separate matte off-white plastic inlay band about 8 mm deep, set
perfectly flush with the aluminium — a deliberate horizontal stripe. The lower body is
matte dark charcoal plastic. Two keycaps are light warm grey and the third, the
rightmost, is bright safety orange.'

B_NEW='Direction: a soft monolith. The entire body is moulded from one single milky
translucent frosted white polycarbonate — top, sides and base all the same material with
no visible split line — with very soft, large, generous corner radii and a gently
pillowed top surface. The three keycaps are frosted translucent white blocks of the same
material, sitting flush inside one shallow soft-cornered tray recess that spans all three.
The blank rear plateau glows faintly and evenly from inside the shell with a soft cool
white light, diffused so no individual light source is visible through the material.'

C_NEW='Direction: a lectern wedge. The body is a wedge that rises toward the back: low
at the front where the three keys sit, noticeably taller at the rear, so the blank rear
plateau becomes a flat panel clearly slanted up and toward the viewer, like a small
lectern or a desk nameplate. The wedge shell is bead-blasted silver aluminium; the base
it sits on is matte warm white plastic; one crisp continuous horizontal split line runs
all the way around the body at the height of the key row, separating the two. The three
keycaps are matte warm white, flush-topped and low profile.'

gen () { python3 "$GEN" generate "$BASE $2 $STYLE" -o "$OUT" --stem "$1" -s landscape -q high; }

gen 10-v1-instrument "$A_NEW" &
gen 11-v1-monolith   "$B_NEW" &
gen 12-v1-lectern    "$C_NEW" &
wait
