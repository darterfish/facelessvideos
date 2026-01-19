# visual_engine/render_short.py
import json
import subprocess
from pathlib import Path
import argparse

WIDTH, HEIGHT = 1080, 1920
FPS = 30
BACKGROUNDS_DIR = Path("assets/backgrounds")
DEFAULT_BACKGROUND = "ocean.mp4"

def render_one(day_dir: Path, sid: str, background_video: str, source_file: str, date_str: str) -> Path:
    # Get the background video path
    bg_video_path = BACKGROUNDS_DIR / background_video
    
    audio = day_dir / "audio" / f"{sid}.wav"
    srt = day_dir / "captions" / f"{sid}.srt"
    
    # Build descriptive filename: sourcefile_videoselected_voice_date.mp4
    source_name = source_file.replace(".txt", "").replace(".md", "")
    video_name = background_video.replace(".mp4", "").replace(".mov", "")
    # TODO: Get voice from shorts data, for now use "piper"
    voice_name = "piper"
    
    output_filename = f"{source_name}_{video_name}_{voice_name}_{date_str}_{sid}.mp4"
    out = day_dir / "video" / output_filename
    out.parent.mkdir(parents=True, exist_ok=True)

    if not bg_video_path.exists():
        raise FileNotFoundError(f"Background video not found: {bg_video_path}")
    if not audio.exists():
        raise FileNotFoundError(f"Audio not found: {audio}")
    if not srt.exists():
        raise FileNotFoundError(f"Captions not found: {srt}")

    # Minimal caption style - focus on readability
    force_style = (
        "FontName=Arial,"             
        "FontSize=18,"                
        "PrimaryColour=&HFFFFFF&,"    
        "OutlineColour=&H000000&,"    
        "Outline=2,"                  
        "Alignment=2,"                
        "MarginV=80"
    )

    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"subtitles='{srt.as_posix()}':force_style='{force_style}'"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-stream_loop", "-1",
        "-i", str(bg_video_path),
        "-i", str(audio),
        "-vf", vf,
        "-r", str(FPS),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="", help="Path to shorts JSON to use")
    args = parser.parse_args()

    # Determine date_str / day_dir
    # Prefer the date inside the shorts JSON if provided, otherwise fall back to latest output folder
    if args.input:
        json_path = Path(args.input)
        if not json_path.exists():
            raise FileNotFoundError(f"--input file not found: {json_path}")
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        date_str = payload.get("date", "")
        if not date_str:
            # fallback to latest output folder
            dated = sorted(Path("output").glob("20??-??-??"))
            if not dated:
                raise FileNotFoundError("No output/YYYY-MM-DD folder found. Run TTS/captions first.")
            day_dir = dated[-1]
            date_str = day_dir.name
        else:
            day_dir = Path("output") / date_str
            if not day_dir.exists():
                raise FileNotFoundError(f"Expected output folder not found: {day_dir}. Run TTS/captions first.")
    else:
        dated = sorted(Path("output").glob("20??-??-??"))
        if not dated:
            raise FileNotFoundError("No output/YYYY-MM-DD folder found. Run TTS/captions first.")
        day_dir = dated[-1]
        date_str = day_dir.name  # e.g., "2026-01-11"

        # Read from temp directory (latest)
        json_files = sorted(Path("data/temp").glob("shorts_*.json"), key=lambda p: p.stat().st_mtime)
        if not json_files:
            raise FileNotFoundError("No data/temp/shorts_*.json found. Run generate_scripts.py first.")
        json_path = json_files[-1]
        payload = json.loads(json_path.read_text(encoding="utf-8"))

    source_file = payload.get("source_file", "unknown")

    for s in payload.get("shorts", []):
        sid = s["id"]
        background_video = s.get("background_video", DEFAULT_BACKGROUND)

        print(f"🎬 Rendering {sid} with background: {background_video}")
        out = render_one(day_dir, sid, background_video, source_file, date_str)
        print(f"   ✅ Rendered: {out.name}")


if __name__ == "__main__":
    main()