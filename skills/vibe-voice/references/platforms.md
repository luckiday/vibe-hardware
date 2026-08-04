# Platform backends

`scripts/speak.py` dispatches to a backend per platform. One is implemented; the
other two are deliberately left as skeletons.

| Platform | Status |
|---|---|
| macOS | **Implemented and verified** on macOS 15 (Darwin 24.6), `say` |
| Linux | **Skeleton only.** Never written, never run. Implement on first use |
| Windows | **Skeleton only.** Never written, never run. Implement on first use |

The skeletons are honest placeholders, not broken code: they report themselves
unavailable and raise `Unsupported` with the contract and a starting point in the
message. Nothing silently half-works.

## The contract

Subclass `Backend` and register it in `BACKENDS`. Four methods:

    available() -> bool
        True only if this platform's engine is actually installed. Checked at
        import time to pick a backend, so keep it cheap.

    voice_for(lang) -> str | None
        A voice that can pronounce `lang`, or None to accept the system default.
        Returning a voice that cannot speak the language is the failure this
        whole skill guards against - prefer None over a wrong guess.

    speak(text, voice) -> None
        Say it aloud. MUST BLOCK until the utterance finishes. Chained calls are
        how a spoken procedure paces itself; a non-blocking speak() turns a
        countdown into five words on top of each other.

    render(text, voice, wav_path) -> None
        Write the same speech to a mono PCM WAV so preflight can measure it.
        If the engine genuinely cannot render to a file, raise `Unsupported` -
        preflight degrades to the audible check alone rather than failing.

Standard library only. `speak.py` must stay dependency-free so it runs on a bench
machine with nothing installed — it is not in `requirements.txt` and should not be.

## Why preflight measures duration

Every engine here exits 0 when handed text its voice cannot pronounce. Measured
on macOS, same sentence, same command, exit 0 both times:

    say -v Alex     -o out.wav  "语音信道检查,一二三。"   ->  0.41 s
    say -v Tingting -o out.wav  "语音信道检查,一二三。"   ->  2.41 s

The first is not speech. Nothing in the exit status distinguishes them, which is
why the check renders and measures instead of trusting the return code. Any
backend you add will have the same property - assume it, do not test for it.

Rendering proves synthesis. It says nothing about the speaker, the volume, or
which output device is selected, so preflight also speaks aloud and stops for a
human to confirm. That confirmation is cached per machine per language (under
`~/.cache/voice-guided-procedures/`, keyed by hostname); it is not meant to be
re-run.

## Starting points

### Linux

Whichever is present - check in this order:

    spd-say -w -l zh "text"          # speech-dispatcher; -w blocks
    espeak-ng -v zh "text"           # render with -w out.wav
    pico2wave -l zh-CN -w out.wav "text" && aplay out.wav

`spd-say` without `-w` returns immediately - that breaks the blocking contract
and silently destroys pacing. Voice availability varies wildly by distro and by
which voice packages are installed; this is exactly what `voice_for` must check
rather than assume.

A headless bench box or a CI runner usually has no audio device at all. Treat the
channel as unavailable and fall back to text rather than pretending it spoke.

### Windows

PowerShell's `System.Speech`:

    Add-Type -AssemblyName System.Speech
    $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
    $s.Speak("text")                      # blocks
    $s.SetOutputToWaveFile("out.wav")     # then Speak() to render
    $s.GetInstalledVoices()               # enumerate for voice_for()
    $s.SelectVoice("Microsoft Huihua")

Non-English voices ship as optional Windows features and are frequently absent -
the mute-channel case preflight exists to catch. Under WSL there is usually no
audio device at all; shell out to `powershell.exe` on the host, or treat the
channel as unavailable and fall back to text.

## After you implement one

Delete the "never run" notice from the backend's docstring and update the table
at the top of this file. Leaving a verified backend labelled unverified is its
own kind of wrong - the labels are only useful while they are accurate. This is
the repo's living-docs rule: fold the lesson back and commit it *with* the work.
