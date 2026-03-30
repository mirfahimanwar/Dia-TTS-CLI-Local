"""
dia_tts.py -- CLI for Dia TTS (github.com/nari-labs/dia)

QUICK START:
  python dia_tts.py "[S1] Hello world, this is a test."
  python dia_tts.py "[S1] Hey, did you hear about that? [S2] No, tell me more!" --play
  python dia_tts.py --interactive
  python dia_tts.py "[S1] Hello." --audio-prompt voice.wav --prompt-text "[S1] transcript of voice.wav"

FULL USAGE:
  python dia_tts.py <text>        [--out FILE] [--play] [--temp T]
                                  [--cfg-scale F] [--top-p F] [--seed N] [--cpu] [--dtype float16|bfloat16|float32]
  python dia_tts.py --interactive [--temp T] [--cfg-scale F]
  python dia_tts.py <text>        --audio-prompt AUDIO --prompt-text TEXT

DIALOGUE FORMAT (required):
  Always start with [S1]. Alternate speakers with [S2].
  Example: "[S1] Hello! [S2] Hey, how are you? [S1] Doing great, thanks!"
  If you omit [S1], it is added automatically.

NON-VERBAL TOKENS:
  (laughs)  (clears throat)  (sighs)  (coughs)  (sniffs)
  Use sparingly -- overuse causes audio artifacts.

VOICE CLONING:
  --audio-prompt  path to a 5-10s reference WAV
  --prompt-text   transcript of that audio (with [S1]/[S2] tags)
  The reference audio + transcript prefix the generation text automatically.

TEMPERATURE:
  --temp          sampling temperature (default 1.8)
  --cfg-scale     classifier-free guidance scale (default 3.0)
  --top-p         nucleus sampling (default 0.90)
  --cfg-filter-k  top-k filter on CFG logits (default 50, RobertAgee fork param)
"""

import argparse
import os
import sys
import time

import numpy as np
import soundfile as sf

# ── Optional playback ────────────────────────────────────────────────────────
try:
    import sounddevice as sd
    _HAS_SOUNDDEVICE = True
except ImportError:
    _HAS_SOUNDDEVICE = False

# ── Dia lives in the dia/ subdirectory (cloned repo) ─────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_DIA_DIR = os.path.join(_HERE, "dia")
if _DIA_DIR not in sys.path:
    sys.path.insert(0, _DIA_DIR)

SAMPLE_RATE = 44100
REPO_ID = "nari-labs/Dia-1.6B-0626"

_model = None


def _load_model(cpu: bool = False, dtype: str = "float16") -> object:
    global _model
    if _model is not None:
        return _model
    import torch
    from dia.model import Dia
    device = "cpu" if cpu else ("cuda" if torch.cuda.is_available() else "cpu")
    compute_dtype = "float32" if device == "cpu" else dtype
    print(f"Loading Dia model on {device} with {compute_dtype} (first run downloads ~3 GB to ~/.cache/huggingface/)...")
    _model = Dia.from_pretrained(REPO_ID, compute_dtype=compute_dtype, device=device)
    return _model


def _ensure_speaker_tag(text: str) -> str:
    """Prefix [S1] if the text doesn't already start with a speaker tag."""
    stripped = text.strip()
    if not stripped.startswith("[S1]") and not stripped.startswith("[S2]"):
        return "[S1] " + stripped
    return stripped


def _generate(
    text: str,
    audio_prompt: str | None,
    prompt_text: str | None,
    temp: float,
    cfg_scale: float,
    top_p: float,
    cfg_filter_top_k: int,
    max_tokens: int | None,
    seed: int | None,
    cpu: bool,
    use_compile: bool = False,
    dtype: str = "float16",
) -> np.ndarray:
    import torch
    if seed is not None:
        import random
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

    model = _load_model(cpu=cpu, dtype=dtype)

    # Build full prompt text when voice cloning.
    # When cloning, the generation text is a CONTINUATION of the prompt transcript --
    # do NOT add a speaker tag to it. Adding [S1] to both produces [S1]...[S1]...
    # which Dia treats as invalid and falls back to its default voice.
    if audio_prompt and prompt_text:
        full_text = _ensure_speaker_tag(prompt_text).rstrip() + " " + text.strip()
    else:
        full_text = _ensure_speaker_tag(text)
        # Append a trailing speaker tag to prevent audio cutoff/degradation at the end.
        # Only for non-cloning: when cloning, a dangling speaker tag causes abrupt cutoff.
        if not full_text.rstrip().endswith(("[S1]", "[S2]")):
            last_s1 = full_text.rfind("[S1]")
            last_s2 = full_text.rfind("[S2]")
            last_tag = "[S1]" if last_s1 >= last_s2 else "[S2]"
            full_text = full_text.rstrip() + " " + last_tag

    try:
        audio = model.generate(
            text=full_text,
            audio_prompt=audio_prompt,
            max_tokens=max_tokens,
            cfg_scale=cfg_scale,
            temperature=temp,
            top_p=top_p,
            cfg_filter_top_k=cfg_filter_top_k,
            use_torch_compile=use_compile,
            verbose=True,
        )
    except Exception as e:
        if use_compile and ("cl is not found" in str(e) or "Compiler" in str(e) or "BackendCompilerFailed" in type(e).__name__):
            print("  Warning: --compile requires MSVC (cl.exe) on PATH. Falling back to eager mode.")
            print("  To fix: add cl.exe to PATH or run from 'Developer PowerShell for VS 2022'.")
            audio = model.generate(
                text=full_text,
                audio_prompt=audio_prompt,
                max_tokens=max_tokens,
                cfg_scale=cfg_scale,
                temperature=temp,
                top_p=top_p,
                cfg_filter_top_k=cfg_filter_top_k,
                use_torch_compile=False,
                verbose=True,
            )
        else:
            raise
    if audio is None or (hasattr(audio, "__len__") and len(audio) == 0):
        raise RuntimeError(
            "Model returned empty audio. This usually means cfg_scale is too high "
            "(try <= 3.5) or temperature is too low (try >= 1.2) -- the model ran to "
            "max_tokens without finding EOS."
        )
    return audio


def _save(audio: np.ndarray, out_path: str | None) -> str:
    if out_path is None:
        session = int(time.time())
        out_dir = os.path.join(_HERE, "output", f"session_{session}")
        os.makedirs(out_dir, exist_ok=True)
        existing = [f for f in os.listdir(out_dir) if f.endswith(".wav")]
        idx = len(existing) + 1
        out_path = os.path.join(out_dir, f"{idx:03d}.wav")
    else:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    sf.write(out_path, audio, SAMPLE_RATE)
    duration = len(audio) / SAMPLE_RATE
    print(f"  Saved -> {out_path}  ({duration:.2f}s)")
    return out_path


def _play(audio: np.ndarray) -> None:
    if not _HAS_SOUNDDEVICE:
        print("  (install sounddevice for --play support:  pip install sounddevice)")
        return
    sd.play(audio, SAMPLE_RATE)
    sd.wait()


def _run_once(args) -> None:
    t0 = time.time()
    audio = _generate(
        text=args.text,
        audio_prompt=getattr(args, "audio_prompt", None),
        prompt_text=getattr(args, "prompt_text", None),
        temp=args.temp,
        cfg_scale=args.cfg_scale,
        top_p=args.top_p,
        cfg_filter_top_k=args.cfg_filter_top_k,
        max_tokens=args.max_tokens,
        seed=args.seed,
        cpu=args.cpu,
        use_compile=args.compile,
        dtype=args.dtype,
    )
    _save(audio, args.out)
    print(f"  Generated in {time.time() - t0:.1f}s")
    if args.play:
        _play(audio)


def _run_interactive(args) -> None:
    print("Dia TTS -- interactive mode")
    print("  Speaker tags: [S1] speaker one   [S2] speaker two")
    print("  Non-verbals:  (laughs) (sighs) (coughs) (clears throat)")
    print("  Commands:  /temp <value>   /cfg <value>   /top-p <value>  /cfg-filter-k <n>")
    print("             /seed <n>       /noseed         /play  /noplay")
    print("             /prompt <path>  /noprompt       /quit")
    print()

    temp = args.temp
    cfg_scale = args.cfg_scale
    top_p = args.top_p
    cfg_filter_top_k = args.cfg_filter_top_k
    seed = args.seed
    play = args.play
    audio_prompt = getattr(args, "audio_prompt", None)
    prompt_text = getattr(args, "prompt_text", None)
    session = int(time.time())
    out_dir = os.path.join(_HERE, "output", f"session_{session}")
    os.makedirs(out_dir, exist_ok=True)
    counter = 0

    while True:
        try:
            line = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not line:
            continue

        if line.startswith("/"):
            parts = line.split(None, 1)
            cmd = parts[0].lower()
            val = parts[1] if len(parts) > 1 else ""
            if cmd in ("/quit", "/exit", "/q"):
                print("Bye!")
                break
            elif cmd == "/temp":
                try:
                    temp = float(val)
                    print(f"  temp = {temp}")
                except ValueError:
                    print("  Usage: /temp <float>")
            elif cmd == "/cfg":
                try:
                    cfg_scale = float(val)
                    print(f"  cfg_scale = {cfg_scale}")
                except ValueError:
                    print("  Usage: /cfg <float>")
            elif cmd == "/cfg-filter-k":
                try:
                    cfg_filter_top_k = int(val)
                    print(f"  cfg_filter_top_k = {cfg_filter_top_k}")
                except ValueError:
                    print("  Usage: /cfg-filter-k <int>")
            elif cmd == "/top-p":
                try:
                    top_p = float(val)
                    print(f"  top_p = {top_p}")
                except ValueError:
                    print("  Usage: /top-p <float>")
            elif cmd == "/seed":
                try:
                    seed = int(val)
                    print(f"  seed = {seed}")
                except ValueError:
                    print("  Usage: /seed <int>")
            elif cmd == "/noseed":
                seed = None
                print("  seed = random")
            elif cmd == "/play":
                play = True
                print("  playback on")
            elif cmd == "/noplay":
                play = False
                print("  playback off")
            elif cmd == "/prompt":
                if val and os.path.exists(val):
                    audio_prompt = val
                    print(f"  audio_prompt = {val}")
                    print("  Set prompt transcript with:  /prompt-text [S1] your transcript here")
                else:
                    print(f"  File not found: {val}")
            elif cmd == "/prompt-text":
                prompt_text = val
                print(f"  prompt_text = {val}")
            elif cmd == "/noprompt":
                audio_prompt = None
                prompt_text = None
                print("  audio_prompt cleared")
            else:
                print(f"  Unknown command: {cmd}")
            continue

        counter += 1
        out_path = os.path.join(out_dir, f"{counter:03d}.wav")
        t0 = time.time()
        try:
            audio = _generate(
                text=line,
                audio_prompt=audio_prompt,
                prompt_text=prompt_text,
                temp=temp,
                cfg_scale=cfg_scale,
                top_p=top_p,
                cfg_filter_top_k=cfg_filter_top_k,
                max_tokens=args.max_tokens,
                seed=seed,
                cpu=args.cpu,
                use_compile=args.compile,
                dtype=args.dtype,
            )
            _save(audio, out_path)
            print(f"  Generated in {time.time() - t0:.1f}s")
            if play:
                _play(audio)
        except Exception as e:
            print(f"  Error: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dia TTS CLI -- dialogue-aware text-to-speech",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("text", nargs="?", help="Text to synthesize (use [S1]/[S2] speaker tags)")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive prompt loop")
    parser.add_argument("--out", "-o", metavar="FILE", help="Output WAV path (default: output/session_<t>/NNN.wav)")
    parser.add_argument("--play", action="store_true", help="Play audio immediately after generation")
    parser.add_argument("--audio-prompt", metavar="WAV", help="Reference audio for voice cloning (5-10s WAV)")
    parser.add_argument("--prompt-text", metavar="TEXT", help="Transcript of --audio-prompt (with [S1]/[S2] tags)")
    parser.add_argument("--temp", type=float, default=1.8, metavar="T", help="Sampling temperature (default: 1.8)")
    parser.add_argument("--cfg-scale", type=float, default=3.0, metavar="F", help="CFG scale (default: 3.0)")
    parser.add_argument("--top-p", type=float, default=0.90, metavar="F", help="Nucleus sampling (default: 0.90)")
    parser.add_argument("--cfg-filter-top-k", type=int, default=50, metavar="K", dest="cfg_filter_top_k", help="CFG top-k filter (default: 50)")
    # DAC (Descript Audio Codec) runs at ~86 audio tokens per second of output audio.
    # max_tokens ÷ 86 ≈ max audio duration. Examples: 512≈6s, 1024≈12s, 2048≈24s, 3072≈35s.
    # Lower values cap long generations early and reduce KV-cache slowdown on long clips.
    parser.add_argument("--max-tokens", type=int, default=3072, metavar="N", dest="max_tokens", help="Max audio tokens to generate (default: 3072, ~35s)")
    parser.add_argument("--seed", type=int, default=None, metavar="N", help="Random seed for reproducibility")
    parser.add_argument("--cpu", action="store_true", help="Force CPU inference (slow)")
    parser.add_argument("--compile", action="store_true", help="Enable torch.compile (first run ~60s slower, subsequent runs faster)")
    parser.add_argument("--dtype", choices=["float16", "bfloat16", "float32"], default="float16", metavar="DTYPE", help="Model compute dtype: float16 (default), bfloat16, float32")

    args = parser.parse_args()

    if not args.interactive and not args.text:
        parser.print_help()
        sys.exit(1)

    if args.interactive:
        _run_interactive(args)
    else:
        _run_once(args)


if __name__ == "__main__":
    main()
