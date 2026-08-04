#!/usr/bin/env python3
"""Speak a line, and verify the voice channel can actually be heard.

Two commands:

    speak.py "text" [--lang zh] [--voice NAME]   speak one line, blocking
    speak.py --check [--lang zh] [--force]       preflight the channel

Preflight is cached per machine per language. Run it once on a new machine or
for a new language; after that it is a no-op. Pass --force to re-run.

Why a preflight exists at all: a text-to-speech command that exits 0 has not
promised you anything. On macOS, an English voice fed Chinese text exits 0 and
emits 0.4 seconds of noise instead of 2.3 seconds of speech. If you start a
spoken procedure on a channel like that, the user hears nothing and the
procedure stalls in silence -- the worst failure mode this skill has.

Preflight therefore checks two independent things:

  1. Synthesis (objective, automatic). Render the sample to a WAV file and
     measure its duration. Too short means the voice cannot pronounce this
     language. No human needed.
  2. Audibility (subjective, needs the human). Rendering to a file proves
     nothing about the speaker, the volume, or the output device. Only a
     person can confirm they actually heard it.

Adding a platform: implement a Backend subclass and register it in BACKENDS.
See references/platforms.md for the contract.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

# A sample per language, plus how long real speech of it should last.
# Floors are deliberately loose: we are separating "spoke it" from "emitted a
# blip", not grading pronunciation.
SAMPLES = {
    "en": ("Voice channel check, one two three.", 1.0),
    "zh": ("语音信道检查,一二三。", 1.0),
    "ja": ("音声チャネルの確認、一二三。", 1.0),
    "ko": ("음성 채널 확인, 하나 둘 셋.", 1.0),
}
DEFAULT_SAMPLE = ("Voice channel check, one two three.", 1.0)

CJK = re.compile(r"[　-〿぀-ヿ㐀-䶿一-鿿"
                 r"가-힯豈-﫿＀-￯]")


def detect_lang(text: str) -> str:
    """Best-effort script detection. Only distinguishes what we have samples for."""
    if not CJK.search(text):
        return "en"
    if re.search(r"[぀-ゟ゠-ヿ]", text):
        return "ja"
    if re.search(r"[가-힯]", text):
        return "ko"
    return "zh"


class Backend:
    """Contract for a platform backend.

    speak()  -- say it out loud, block until finished. Blocking is required:
                chained calls are how a spoken procedure paces itself.
    render() -- write the same speech to a mono PCM WAV at wav_path, so the
                caller can measure its duration. If a platform cannot render to
                a file, raise Unsupported and preflight falls back to the
                audible check alone.
    """

    name = "abstract"

    @staticmethod
    def available() -> bool:
        raise NotImplementedError

    def voice_for(self, lang: str) -> str | None:
        """Return a voice name that can pronounce `lang`, or None for the default."""
        raise NotImplementedError

    def speak(self, text: str, voice: str | None) -> None:
        raise NotImplementedError

    def render(self, text: str, voice: str | None, wav_path: Path) -> None:
        raise NotImplementedError


class Unsupported(Exception):
    pass


class MacBackend(Backend):
    """macOS `say`. Verified on macOS 15 (Darwin 24.6)."""

    name = "macos"

    # First installed voice wins. Names come from `say -v '?'`.
    PREFERRED = {
        "zh": ["Tingting", "Meijia", "Sinji"],
        "ja": ["Kyoko", "Otoya"],
        "ko": ["Yuna"],
        "en": [],  # system default already speaks English
    }

    @staticmethod
    def available() -> bool:
        return sys.platform == "darwin" and shutil.which("say") is not None

    def _installed(self) -> set[str]:
        out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout
        return {line.split()[0] for line in out.splitlines() if line.split()}

    def voice_for(self, lang: str) -> str | None:
        candidates = self.PREFERRED.get(lang, [])
        if not candidates:
            return None
        installed = self._installed()
        for v in candidates:
            if v in installed:
                return v
        return None

    def _argv(self, voice: str | None) -> list[str]:
        return ["say"] + (["-v", voice] if voice else [])

    def speak(self, text: str, voice: str | None) -> None:
        subprocess.run(self._argv(voice) + [text], check=True)

    def render(self, text: str, voice: str | None, wav_path: Path) -> None:
        subprocess.run(
            self._argv(voice)
            + ["-o", str(wav_path), "--data-format=LEI16@22050", text],
            check=True,
        )


class LinuxBackend(Backend):
    """NOT IMPLEMENTED -- skeleton only, never run or verified by the author.

    Fill in using whichever of these the machine actually has:
      speech-dispatcher  `spd-say -w -l <lang> <text>`  (-w blocks)
      espeak-ng          `espeak-ng -v <lang> <text>`, render with `-w out.wav`
      pico2wave          renders to WAV only; play it with aplay

    Keep the contract: speak() must block, render() must produce a mono PCM WAV.
    Delete this notice once you have run it on a real machine.
    """

    name = "linux"

    @staticmethod
    def available() -> bool:
        return False

    def voice_for(self, lang: str) -> str | None:
        raise Unsupported(LinuxBackend.__doc__)

    def speak(self, text: str, voice: str | None) -> None:
        raise Unsupported(LinuxBackend.__doc__)

    def render(self, text: str, voice: str | None, wav_path: Path) -> None:
        raise Unsupported(LinuxBackend.__doc__)


class WindowsBackend(Backend):
    """NOT IMPLEMENTED -- skeleton only, never run or verified by the author.

    Starting point is PowerShell's System.Speech:
      Add-Type -AssemblyName System.Speech
      $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
      $s.Speak("text")                      # blocks
      $s.SetOutputToWaveFile("out.wav")     # then Speak() to render

    Voice selection is $s.SelectVoice(<name>); enumerate with $s.GetInstalledVoices().
    Non-English voices are a Windows optional feature and are often absent --
    which is exactly the silent-channel case preflight exists to catch.

    Keep the contract: speak() must block, render() must produce a mono PCM WAV.
    Delete this notice once you have run it on a real machine.
    """

    name = "windows"

    @staticmethod
    def available() -> bool:
        return False

    def voice_for(self, lang: str) -> str | None:
        raise Unsupported(WindowsBackend.__doc__)

    def speak(self, text: str, voice: str | None) -> None:
        raise Unsupported(WindowsBackend.__doc__)

    def render(self, text: str, voice: str | None, wav_path: Path) -> None:
        raise Unsupported(WindowsBackend.__doc__)


BACKENDS = [MacBackend, LinuxBackend, WindowsBackend]


def pick_backend() -> Backend:
    for cls in BACKENDS:
        if cls.available():
            return cls()
    raise Unsupported(
        f"No text-to-speech backend for platform {platform.system()!r}. "
        f"Implement one in {__file__} -- see the Backend docstring for the contract."
    )


def cache_path() -> Path:
    root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = root / "voice-guided-procedures"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"preflight-{socket.gethostname()}.json"


def load_cache() -> dict:
    p = cache_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_cache(cache: dict) -> None:
    cache_path().write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def wav_duration(p: Path) -> float:
    with wave.open(str(p)) as w:
        return w.getnframes() / float(w.getframerate())


def cmd_speak(text: str, lang: str | None, voice: str | None) -> int:
    backend = pick_backend()
    lang = lang or detect_lang(text)
    if voice is None:
        voice = backend.voice_for(lang)
    backend.speak(text, voice)
    return 0


def cmd_check(lang: str | None, force: bool, voice: str | None = None) -> int:
    backend = pick_backend()
    lang = lang or "en"
    cache = load_cache()
    key = f"{backend.name}:{lang}"

    if not force and voice is None and cache.get(key, {}).get("ok"):
        print(f"[preflight] {key}: already verified on this machine, skipping.")
        return 0

    sample, floor = SAMPLES.get(lang, DEFAULT_SAMPLE)
    # An explicit --voice is a throwaway probe of one specific voice. Report it,
    # but never let it overwrite what we know about the channel's real voice.
    probe_only = voice is not None
    if voice is None:
        voice = backend.voice_for(lang)
    print(f"[preflight] backend={backend.name} lang={lang} voice={voice or 'system default'}")

    # 1. Synthesis -- objective, no human needed.
    try:
        with tempfile.TemporaryDirectory() as td:
            wav = Path(td) / "probe.wav"
            backend.render(sample, voice, wav)
            dur = wav_duration(wav)
        if dur < floor:
            print(
                f"[preflight] FAIL: synthesised only {dur:.2f}s, expected >= {floor:.2f}s.\n"
                f"            The selected voice cannot pronounce {lang!r}. "
                f"Install a {lang} voice or pass --voice explicitly.\n"
                f"            Do NOT start a spoken procedure on this channel."
            )
            if not probe_only:
                cache[key] = {"ok": False, "reason": f"synthesis too short ({dur:.2f}s)"}
                save_cache(cache)
            return 1
        print(f"[preflight] synthesis OK ({dur:.2f}s of audio).")
    except Unsupported as e:
        print(f"[preflight] synthesis check skipped: {e.args[0].strip().splitlines()[0]}")

    # 2. Audibility -- only a human can confirm this.
    backend.speak(sample, voice)
    print(
        "[preflight] Spoke the sample aloud. Synthesis is proven; the speaker and "
        "volume are not.\n"
        "            Ask the user whether they heard it. If yes, record it with:\n"
        f"                {sys.argv[0]} --confirm-heard --lang {lang}"
    )
    return 0


def cmd_confirm(lang: str) -> int:
    backend = pick_backend()
    cache = load_cache()
    cache[f"{backend.name}:{lang}"] = {"ok": True, "confirmed_by": "user"}
    save_cache(cache)
    print(f"[preflight] {backend.name}:{lang} confirmed audible. Cached at {cache_path()}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="?", help="line to speak")
    ap.add_argument("--lang", help="language tag: en, zh, ja, ko (default: detect)")
    ap.add_argument("--voice", help="explicit voice name, overrides selection")
    ap.add_argument("--check", action="store_true", help="preflight the channel")
    ap.add_argument("--confirm-heard", action="store_true",
                    help="record that the user confirmed hearing the sample")
    ap.add_argument("--force", action="store_true", help="re-run a cached preflight")
    args = ap.parse_args()

    try:
        if args.confirm_heard:
            return cmd_confirm(args.lang or "en")
        if args.check:
            return cmd_check(args.lang, args.force, args.voice)
        if not args.text:
            ap.error("give text to speak, or --check")
        return cmd_speak(args.text, args.lang, args.voice)
    except Unsupported as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"error: backend command failed: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
