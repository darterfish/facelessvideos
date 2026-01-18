import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Any

VOICE_DIR = Path("assets/piper_voice")

def find_voice_model() -> Path:
    onnx_files = sorted(VOICE_DIR.glob("*.onnx"))
    if not onnx_files:
        raise FileNotFoundError(
            "No .onnx voice model found in assets/piper_voice/. "
            "Download a Piper voice (.onnx + .onnx.json) into that folder."
        )
    return onnx_files[0]

def tts_to_wav(text: str, out_wav: Path, voice_model: str, speech_speed: float = 1.0) -> None:
    """Generate TTS audio using specified voice model"""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    
    # Build path to voice model
    model_path = Path("assets/piper_voice") / voice_model
    
    if not model_path.exists():
        raise FileNotFoundError(f"Voice model not found: {model_path}")
        
    # length_scale is inversely related to speed
    length_scale = 1.0 / speech_speed
    
    cmd = [
        "piper",
        "--model", str(model_path),
        "--output_file", str(out_wav),
        "--sentence_silence", "0.3",
        "--length_scale", str(length_scale),
    ]
    result = subprocess.run(cmd, input=text.encode("utf-8"), check=True, 
                           capture_output=True)
    
    # Debug: print if there were any warnings
    if result.stderr:
        stderr_text = result.stderr.decode('utf-8', errors='ignore')
        print(f"  Piper stderr for {out_wav.name}: {stderr_text[:200]}")

def main():
    # Reads from temp directory
    json_files = sorted(Path("data/temp").glob("shorts_*.json"), key=lambda p: p.stat().st_mtime)
    if not json_files:
        raise FileNotFoundError("No data/temp/shorts_*.json found. Run generate_scripts.py first.")
    json_path = json_files[-1]
    
    print(f"📂 Reading shorts from: {json_path}")
    
    with open(json_path, "r", encoding="utf-8") as f:
        payload: Dict[str, Any] = json.load(f)

    date_str = payload.get("date", "unknown-date")
    out_dir = Path("output") / date_str / "audio"

    # ADD THIS: Clean audio directory before generating new files
    if out_dir.exists():
        import shutil
        print(f"🗑️  Cleaning old audio files from {out_dir}")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    shorts = payload.get("shorts", [])
    if not shorts:
        raise ValueError(f"No shorts found in {json_path}. Re-run generate_scripts.py and confirm it outputs shorts.")

    for s in shorts:
        sid = s["id"]
        script = s["voice_script"].strip()
        voice_model = s.get("voice_model", find_voice_model().name)  # Get voice from short or use first available
        speech_speed = float(s.get("speech_speed", "1.0"))
        out_wav = out_dir / f"{sid}.wav"
        
        # Debug: print script details
        voice_display = voice_model.replace('.onnx', '')
        print(f"📝 {sid}: {len(script)} chars, ~{len(script.split())} words, voice: {voice_display}, speed: {speech_speed}x")
        
        tts_to_wav(script, out_wav=out_wav, voice_model=voice_model, speech_speed=speech_speed)
        
        # Debug: check output file duration
        probe = subprocess.run(
            ["ffprobe", "-i", str(out_wav), "-show_entries", 
             "format=duration", "-v", "quiet", "-of", "csv=p=0"],
            capture_output=True, text=True
        )
        if probe.returncode == 0:
            duration = float(probe.stdout.strip())
            print(f"✅ {sid}: {out_wav} ({duration:.2f}s)")
        else:
            print(f"✅ {sid}: {out_wav}")

    print(f"\nDone. Audio in: {out_dir}")

if __name__ == "__main__":
    main()