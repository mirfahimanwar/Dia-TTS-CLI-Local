# DiaTTS CLI

A clean one-click CLI wrapper for [Dia TTS](https://github.com/nari-labs/dia) by Nari Labs.

Dia is a 1.6B parameter dialogue-focused TTS model. It generates highly realistic multi-speaker
audio from `[S1]` / `[S2]` tagged transcripts and supports voice cloning via an audio prompt.

---

## Features

- One-click Windows setup (`setup.ps1`)
- Single-line and interactive modes
- Auto-saves outputs to `output/session_<timestamp>/NNN.wav`
- Optional immediate playback (`--play`)
- Voice cloning via `--audio-prompt` + `--prompt-text`
- Configurable temperature, CFG scale, top-p, and seed
- Auto-adds `[S1]` tag if you forget it

---

## Quick Examples

```powershell
# Basic
python dia_tts.py "[S1] Hello world, this is Dia TTS." --play

# Two speakers
python dia_tts.py "[S1] Hey! [S2] Hey yourself! [S1] (laughs) How are you?" --play

# Voice clone — single line
# Use spaces between flag and value, not = signs
python dia_tts.py "[S1] Hello, how are you?" --audio-prompt "D:\path\to\voice.wav" --prompt-text "[S1] Transcript of what is said in the reference clip." --play

# Voice clone — interactive, pre-loaded at startup
python dia_tts.py --interactive --play --audio-prompt "D:\path\to\voice.wav" --prompt-text "[S1] Transcript of the reference clip."

# Interactive — set voice inside the session
python dia_tts.py --interactive --play
# >>> /prompt D:\path\to\voice.wav
# >>> /prompt-text [S1] Transcript of what is said in the reference clip.
# >>> [S1] Now type whatever you want to generate.
```

> **Flag syntax:** always use a space between the flag and value — `--audio-prompt "file.wav"` not `--audio-prompt="file.wav"`
> **Script name:** `dia_tts.py` — always call it with `python dia_tts.py`, not `diatts.py`

---

## Requirements

- Python 3.10+
- Git
- NVIDIA GPU with CUDA 12.4 (CPU works but is very slow)
- ~3 GB disk space for the model (downloaded automatically on first run)

---

## Setup (Windows)

```powershell
git clone <this-repo> DiaTTS
cd DiaTTS
.\setup.ps1
.\venv\Scripts\Activate.ps1
```

`setup.ps1` will:
1. Clone [RobertAgee/dia](https://github.com/RobertAgee/dia) (optimized fork, ~40% less VRAM) into `dia/`
2. Create a Python virtual environment
3. Install PyTorch 2.6 with CUDA 12.4
4. Install Dia and all dependencies
5. Install `sounddevice` for `--play` support

---

## Usage

### Single line

```powershell
python dia_tts.py "[S1] Hello world, this is Dia TTS."
python dia_tts.py "[S1] Hey! [S2] Hey yourself! [S1] (laughs) How are you?" --play
python dia_tts.py "[S1] That was incredible." --out my_output.wav --seed 42
```

### Interactive mode

```powershell
python dia_tts.py --interactive
```

Commands available in interactive mode:

| Command | Description |
|---|---|
| `/temp <value>` | Set sampling temperature |
| `/cfg <value>` | Set CFG scale |
| `/top-p <value>` | Set nucleus sampling probability |
| `/seed <n>` | Fix random seed |
| `/noseed` | Return to random seed |
| `/play` / `/noplay` | Toggle immediate playback |
| `/prompt <path>` | Set voice cloning audio file |
| `/prompt-text <text>` | Set transcript for voice cloning file |
| `/noprompt` | Clear voice cloning |
| `/quit` | Exit |

### Voice cloning

```powershell
python dia_tts.py "[S1] This is the generated speech." \
  --audio-prompt reference.wav \
  --prompt-text "[S1] Transcript of the reference audio."
```

Reference audio should be 5-10 seconds. The transcript must use `[S1]`/`[S2]` tags correctly.

---

## Dialogue Format

Dia is designed for dialogue. Always use speaker tags:

```
[S1] First speaker says this. [S2] Second speaker responds. [S1] Back to first speaker.
```

- Always start with `[S1]` (added automatically if omitted)
- Alternate between `[S1]` and `[S2]` — do not repeat the same speaker consecutively
- Keep input length to roughly 5-20 seconds equivalent (very short or very long inputs sound unnatural)
- End with a speaker tag (e.g. `[S2]`) to improve audio quality at the end

### Non-verbal tokens

| Token | Effect |
|---|---|
| `(laughs)` | Laughter |
| `(sighs)` | Sigh |
| `(gasps)` | Gasp |
| `(coughs)` | Cough |
| `(sniffs)` | Sniff |
| `(clears throat)` | Throat clearing |
| `(mumbles)` | Mumbling |
| `(sings)` | Singing (alt) - closer to doodling |
| `(singing)` | Singing - closer to humming |
| `(groans)` | Groan |
| `(beep)` | Beep sound |

### Other Non-verbal tokens - these don't work that well for voice cloning

| `(humming)` | Humming |
| `(whistles)` | Whistling |
| `(chuckle)` | Soft chuckle |
| `(sneezes)` | Sneeze |
| `(inhales)` | Audible inhale |
| `(exhales)` | Audible exhale |
| `(screams)` | Scream |
| `(claps)` | Clapping - closer to a thud|
| `(applause)` | Applause |
| `(burps)` | Burp |




Use sparingly — overusing or using unlisted non-verbals can cause audio artifacts.

---

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--temp` | `1.8` | Sampling temperature. Lower = more stable, higher = more expressive (min ~1.2) |
| `--cfg-scale` | `3.0` | Classifier-free guidance scale (keep ≤ 3.5) |
| `--top-p` | `0.90` | Nucleus sampling probability |
| `--cfg-filter-top-k` | `50` | CFG top-k filter (RobertAgee fork param) |
| `--max-tokens` | `3072` | Max audio tokens to generate (~35s) |
| `--seed` | random | Fix seed for reproducible output |
| `--play` | off | Play audio immediately after generation |
| `--out` | auto | Custom output path |
| `--compile` | off | Enable torch.compile for faster generation (requires MSVC on Windows) |
| `--cpu` | off | Force CPU inference (slow) |

---

## Troubleshooting

**CUDA out of memory**
Dia-1.6B requires ~4 GB VRAM. Close other GPU applications or use `--cpu`.

**Model download fails**
The model downloads from Hugging Face (~3 GB). Ensure you have a stable connection.
It caches to `~/.cache/huggingface/` and only downloads once.

**Audio sounds unnatural / too fast**
Input is too long. Aim for text that would take 5-20 seconds to speak.

**Weird artifacts or noises**
Overused or unlisted non-verbal tokens. Stick to the supported list above.

**`[S1]`/`[S2]` same speaker in a row**
Dia expects speakers to alternate. Avoid `[S1] ... [S1] ...` patterns.

---

## Credits

- [Dia TTS](https://github.com/nari-labs/dia) by [Nari Labs](https://github.com/nari-labs)
- Model: [nari-labs/Dia-1.6B-0626](https://huggingface.co/nari-labs/Dia-1.6B-0626) on Hugging Face
