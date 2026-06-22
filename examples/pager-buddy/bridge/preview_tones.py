#!/usr/bin/env python3
"""preview_tones.py — audition the pager-buddy alert tones on your Mac before flashing.

Generates the three alert patterns using the exact same synthesis as the firmware:
  · harmonics: fundamental + 2× fundamental (0.72·sin(f) + 0.22·sin(2f))
  · envelope: 8 ms attack, 40 ms decay tail
  · frequencies: equal-temperament notes (A4=440 Hz base)

Outputs three WAV files to /tmp/pager_*.wav and plays them sequentially using afplay.

    python3 preview_tones.py
"""
import math
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


SAMPLE_RATE = 16000  # match firmware's AUDIO_SAMPLE_RATE


def gen_tone(f0, f1, ms):
    """Generate a tone glide f0→f1 (Hz) for `ms` milliseconds.

    Returns a list of int16 samples. Implements the exact harmonic mix
    and envelope from the firmware gen() function.
    """
    total  = SAMPLE_RATE * ms // 1000
    attack = SAMPLE_RATE * 8  // 1000
    decay  = SAMPLE_RATE * 40 // 1000

    samples = []
    phase1 = 0.0
    phase2 = 0.0

    for pos in range(total):
        frac = pos / total
        f = f0 + (f1 - f0) * frac

        phase1 += 2.0 * math.pi * f / SAMPLE_RATE
        phase2 += 2.0 * math.pi * (f * 2.0) / SAMPLE_RATE

        # Keep phases in [0, 2π)
        if phase1 > 2.0 * math.pi:
            phase1 -= 2.0 * math.pi
        if phase2 > 2.0 * math.pi:
            phase2 -= 2.0 * math.pi

        # Asymmetric envelope: 8ms rise, 40ms tail
        if pos < attack:
            env = pos / attack
        elif pos > total - decay:
            env = (total - pos) / decay
        else:
            env = 1.0

        # Harmonic mix: 72% fundamental + 22% 2nd harmonic
        sample = 0.62 * 32767.0 * env * (0.72 * math.sin(phase1) + 0.22 * math.sin(phase2))
        samples.append(int(sample))

    return samples


def write_wav(path, samples):
    """Write samples (list of int16) to a mono WAV file."""
    with open(path, 'wb') as f:
        # RIFF header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + len(samples) * 2))
        f.write(b'WAVE')

        # fmt subchunk
        f.write(b'fmt ')
        f.write(struct.pack('<I', 16))  # subchunk1size
        f.write(struct.pack('<H', 1))   # audio format (PCM)
        f.write(struct.pack('<H', 1))   # num channels
        f.write(struct.pack('<I', SAMPLE_RATE))  # sample rate
        f.write(struct.pack('<I', SAMPLE_RATE * 2))  # byte rate
        f.write(struct.pack('<H', 2))   # block align
        f.write(struct.pack('<H', 16))  # bits per sample

        # data subchunk
        f.write(b'data')
        f.write(struct.pack('<I', len(samples) * 2))
        for sample in samples:
            f.write(struct.pack('<h', sample))


def play_wav(path):
    """Play a WAV file using afplay (macOS)."""
    try:
        subprocess.run(['afplay', str(path)], check=True)
    except FileNotFoundError:
        print(f"warning: afplay not found; skipping playback of {path}", file=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"error: playback failed: {e}", file=sys.stderr)


def main():
    print("pager-buddy tone preview  (generating + playing...)\n")

    # WAITING: A5 (880Hz) 90ms + 55ms gap + E6 (1320Hz) 125ms
    print("1. WAITING (urgent ascending ding-ding)")
    print("   A5 (880 Hz) 90ms → E6 (1320 Hz) 125ms")
    waiting_1 = gen_tone(880, 880, 90)
    waiting_2 = gen_tone(1320, 1320, 125)
    waiting = waiting_1 + [0] * (SAMPLE_RATE * 55 // 1000) + waiting_2

    # ASKING: glide A5 (880Hz) → D6 (1175Hz) over 310ms
    print("2. ASKING (rising question glide)")
    print("   A5 (880 Hz) → D6 (1175 Hz) glide 310ms")
    asking = gen_tone(880, 1175, 310)

    # DONE: C5 (523Hz) 75ms + 25ms gap + E5 (659Hz) 75ms + 25ms gap + A5 (880Hz) 130ms
    print("3. DONE (satisfying major-chord build)")
    print("   C5 (523 Hz) 75ms → E5 (659 Hz) 75ms → A5 (880 Hz) 130ms")
    done_1 = gen_tone(523, 523, 75)
    done_2 = gen_tone(659, 659, 75)
    done_3 = gen_tone(880, 880, 130)
    done = (done_1 + [0] * (SAMPLE_RATE * 25 // 1000) +
            done_2 + [0] * (SAMPLE_RATE * 25 // 1000) +
            done_3)

    # Write WAVs to /tmp
    waiting_path = Path("/tmp/pager_waiting.wav")
    asking_path  = Path("/tmp/pager_asking.wav")
    done_path    = Path("/tmp/pager_done.wav")

    write_wav(waiting_path, waiting)
    write_wav(asking_path, asking)
    write_wav(done_path, done)

    print(f"\nWAV files written to /tmp/pager_*.wav")
    print("\nPlaying tones...\n")

    play_wav(waiting_path)
    play_wav(asking_path)
    play_wav(done_path)

    print("\nDone. Sounds good? Flash the firmware with the updated audio.c")


if __name__ == "__main__":
    main()
