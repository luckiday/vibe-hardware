# Confirmation channels

After speaking a step you have to learn whether it happened. Two ways, and the
choice matters: it decides whether the user has to come back to the keyboard.

## 1. Turn-end (default)

Speak the step, print the reference detail, then **end your turn**. The user does
the thing and replies in chat when they are ready.

    speak.py "Step two. Power cycle the board, then tell me when it is back up."
    -> print the exact command / what they should see
    -> end turn

Use this when: the action's effect is not observable from where you sit, the step
needs judgement, or you have no log to watch.

Costs one round trip per step, and the user must return to the keyboard. That is
fine for a five-step procedure and painful for a thirty-step one.

**Say that you are waiting.** The user cannot see your turn ended. "Tell me when
it's done" is part of the utterance, not an afterthought.

## 2. Signal-polled

Speak the step, then watch something observable and decide for yourself. The user
never touches the keyboard.

    speak.py "Step two. Press and hold SW3 until you hear the tone."
    -> poll the serial log for the line the firmware prints on SW3 long-press
    -> when it appears: speak.py "Got it. Next step."

Good signals, roughly in order of trustworthiness:

| Signal | Why it is good |
|---|---|
| A line in a device/serial log | The device itself is asserting it, not a human |
| An HTTP endpoint changing state | Same, and easy to poll |
| A file appearing or its mtime moving | Cheap, works for build/flash steps |
| A process exiting | Unambiguous |

Use this when the effect is machine-observable. It is the whole reason this skill
is worth more than a notification beep: a hardware bring-up where the user's
hands never leave the board.

This is also why it pays to make firmware print a line on every human-triggered
event — a bring-up log designed for a human to read is, for free, the signal
channel a spoken procedure polls.

### Bounding the wait

**Always cap it.** The user may have walked away, misheard, or hit a step that
cannot succeed. Unbounded polling means an agent spinning at a dead board.

    deadline = now + timeout        # size it to the step: seconds, not hours
    while now < deadline:
        if signal_present(): break
        wait a beat
    else:
        speak.py "I did not see that go through. What happened?"
        -> fall back to turn-end and let the user tell you

The fallback is the point. A timeout is not a failure of the procedure; it is the
moment to hand control back to the human.

### Do not confuse absence with failure

A signal that has not arrived yet is not the same as a step that failed. Say what
you actually know — "I have not seen it yet" — rather than "it failed". The user
is standing at the hardware and can see things you cannot.

## Choosing

Ask one question: **can I observe the effect myself?**

- Yes -> signal-polled, with a cap and a turn-end fallback.
- No -> turn-end.

Mixing them within one procedure is normal and correct. Poll the steps you can
watch; hand back the ones you cannot.
