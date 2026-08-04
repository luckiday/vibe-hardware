---
name: vibe-voice
description: >-
  Direct a human through hands-on steps by SPEAKING to them, for when their hands and
  eyes are off the terminal — board bring-up, flashing and wiring, holding a probe on a
  test point, physically verifying a print or an assembled board, lab/on-site work,
  multi-machine ops, or a long build the user walks away from. Use when written
  instructions will not be read at the moment they matter, when a step has to be timed
  ("hold reset for five seconds"), when the agent is BLOCKED waiting on a human action,
  or when the user asks to be guided or notified by voice. Key facts this skill encodes:
  SPLIT THE CHANNELS — speak the action verb, the timing, and "I need you"; print the
  commands, hex IDs, paths, and expected output as text (if hearing it would make someone
  ask "say that again?", it does not belong in speech). PREFLIGHT the channel once per
  machine per language (`scripts/speak.py --check`) — a text-to-speech command that exits
  0 has promised nothing: an English voice fed Chinese text exits 0 and emits 0.4 s of
  noise where 2.3 s of speech should be, and a spoken procedure on a mute channel stalls
  in silence. speak() BLOCKS, so chained calls pace themselves — but never use speech rate
  as a clock, sleep explicitly. Prefer a machine-observable signal (a serial-log line, a
  file appearing) over "did you press it?", and always CAP the wait with a turn-end
  fallback. NEVER speak secrets or long strings. macOS is implemented and verified;
  Linux/Windows backends are honest skeletons — implement on first use
  (references/platforms.md). Stdlib-only; no extra dependencies.
---

# Voice-guided procedures (the agent talks; the user's hands stay on the hardware)

Text instructions fail in one specific situation: **the user's hands and eyes are
not on the terminal.** Someone holding a probe on a test point, pressing a button
on a board, watching an LED, or walking back from the printer is not reading
your scrollback. The instruction was written; it was never received.

Speech fixes the channel mismatch. It is also worse than text at almost
everything else — you cannot re-read it, skim it, or copy from it. So the two
channels split the work, and this skill is mostly about that split.

## Where this fits in vibe-hardware

The other four skills are *domains* (a manifest, firmware, a board, a shell). This
one is a *channel*, and it turns on at exactly the moments the domain loops hand
control back to a human:

| Moment | Skill it belongs to | Why speech |
|---|---|---|
| Flash + monitor, bring up one peripheral at a time | [`vibe-firmware`](../vibe-firmware/) | hands on the USB cable and the reset button, eyes on the LED |
| Bench-verify a fabricated board — continuity, probing a test point, first power-up | [`vibe-pcb`](../vibe-pcb/) | one hand per probe; nothing left for the keyboard |
| Test-fit a print, check a port lines up with its cutout, seat the board in the shell | [`vibe-cad`](../vibe-cad/) | the user is at the printer, not the terminal |
| The release checklist's real-hardware test before an OTA | [`vibe-plm`](../vibe-plm/) | a gate that is only ever passed by a human doing a physical thing |

Prose hand-off only — those skills never call this one's code, and this one never
calls theirs.

## When to speak

Speak only when one of these is true:

1. **The user's attention is away from the screen** — they are handling hardware,
   at another machine, or across the room.
2. **Timing matters** — the instruction has a "now" or a duration in it.
3. **You are blocked on them** — you cannot proceed until a human acts, and they
   need to know you are waiting.

Do not narrate progress. Do not speak what the user is already watching you do.
An agent that talks constantly gets muted, and then rule 3 stops working when it
matters.

## The dual-channel rule

Every hands-on instruction splits in two. This is the center of the skill.

| Speak it | Write it |
|---|---|
| The action verb and its object | Commands to copy and run |
| When to start, when to stop | Hex IDs, URLs, paths, long values |
| Which of several things ("the *left* header") | Exact expected output |
| Success, failure, "I need you" | Error text, logs, diffs |

The test: **if hearing it would make someone ask "say that again?", it does not
belong in speech.** Say "flash the firmware now, the command is on screen" — not
the command itself.

## The procedure loop

    0. Preflight the channel     once per machine, per language
    1. Announce                  how many steps, what they need in hand
    2. For each step:
         a. Speak the imperative      one action, short
         b. Print the reference       exact commands and values, as text
         c. Wait for confirmation     see references/confirm-channels.md
         d. Verify the effect         if it is observable, check it yourself
    3. Speak the outcome         done / failed / blocked

Step 2d matters more than it looks. "Did you press it?" answered by a human is
weaker evidence than a line appearing in the serial log. Prefer what you can
observe over what you are told.

### 0. Preflight

A text-to-speech command that exits 0 has promised you nothing. An English voice
fed Chinese text exits 0 and emits 0.4 seconds of noise where 2.3 seconds of
speech should be. Start a spoken procedure on a channel like that and the user
hears silence while you wait forever — the worst failure this skill has.

    skills/vibe-voice/scripts/speak.py --check --lang <en|zh|ja|ko>

It renders a sample, measures the audio, and fails loudly if the voice cannot
pronounce the language. Then it speaks aloud and stops: **only the user can
confirm the speaker and volume actually work.** Ask them. If they heard it:

    skills/vibe-voice/scripts/speak.py --confirm-heard --lang <lang>

Cached per machine, per language, under `~/.cache/voice-guided-procedures/` —
it is a no-op after that. Do not re-run it every session; one machine does not
need repeated testing.

### 1–3. Running it

    skills/vibe-voice/scripts/speak.py "Step one. Hold the reset button."

Speaking blocks until the utterance finishes, which is what makes pacing work.
`speak.py` is stdlib-only — nothing to install, and it runs standalone outside
an agent too.

## Timing: the part text cannot do

Because each call blocks, chained utterances are a metronome:

    speak.py "Hold it down"; speak.py "three"; speak.py "two"; speak.py "one"; speak.py "release"

Measured on macOS: 5.4 s for those five utterances through `say`, 5.6 s through
`speak.py` — roughly a second per short word, plus a little per-call overhead.

Which is precisely why you must not use speech rate as a clock. It drifts with
the voice, the language, and the wrapper. **If the duration has to be right,
sleep explicitly:**

    speak.py "Hold it down now"
    python3 -c "import time; time.sleep(5)"
    speak.py "Release"

Note: some agent harnesses block a foreground shell `sleep`. `python3 -c
"time.sleep(n)"` works where `sleep n` is refused.

## Hard rules

- **Never speak secrets.** Speech broadcasts to the whole room and to anyone on
  the call. Tokens, Wi-Fi credentials, API keys, personal data stay in text.
  Always. (Same rule as the repo's: secrets live in a gitignored file, never in
  the transcript — and never in the air either.)
- **Never speak long strings.** Hex IDs, MAC addresses, URLs, base64, stack
  traces. Unreadable aloud, and the user cannot copy them from air.
- **Preflight before the first spoken procedure on a machine.** A mute channel
  fails silently, which is why it is dangerous.
- **Follow the user's language.** Speak the language they are speaking to you in.
  A correct instruction in a language they do not use is a failed instruction.
- **Cap the wait.** When polling for a signal instead of a reply, bound it. A
  user who walked away and did not come back must not leave you spinning.
- **One action per utterance.** Two instructions in one breath means the second
  one gets lost.

## References

- [`references/confirm-channels.md`](references/confirm-channels.md) — how to learn
  a step happened: turn-end vs. signal-polled, bounding the wait, and the fallback.
- [`references/platforms.md`](references/platforms.md) — the backend contract, why
  preflight measures duration, and starting points for Linux/Windows.

macOS is implemented and verified. Linux and Windows are **skeletons only** —
`scripts/speak.py` carries the contract and starting points, but neither has been
run. Implement the backend on first use, then update the status table (a verified
backend left labelled unverified is its own kind of wrong).
