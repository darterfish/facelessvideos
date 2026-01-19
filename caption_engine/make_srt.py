# caption_engine/make_srt.py
import json
import subprocess
import argparse
from pathlib import Path
from typing import List, Tuple


def get_audio_duration(audio_path: Path) -> float:
    """Get duration of audio file in seconds"""
    probe = subprocess.run(
        ["ffprobe", "-i", str(audio_path), "-show_entries", 
         "format=duration", "-v", "quiet", "-of", "csv=p=0"],
        capture_output=True, text=True, check=True
    )
    return float(probe.stdout.strip())

def create_srt_from_text(text: str, duration: float, out_srt: Path) -> None:
    """Create SRT file from text using line breaks as caption boundaries, 
    with timing based on word count per line"""
    out_srt.parent.mkdir(parents=True, exist_ok=True)
    
    # Split on line breaks - each line is a caption
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Remove periods from captions
    lines = [line.rstrip('.') for line in lines]
    
    # Calculate word count for each line
    word_counts = [len(line.split()) for line in lines]
    total_words = sum(word_counts)
    
    if total_words == 0:
        return
    
    # Calculate time per word
    time_per_word = duration / total_words
    
    srt_content = []
    current_time = 0.0
    
    for i, (line, word_count) in enumerate(zip(lines, word_counts), start=1):
        start_time = current_time
        line_duration = word_count * time_per_word
        end_time = current_time + line_duration
        current_time = end_time
        
        # Format timestamps
        start_ts = format_timestamp(start_time)
        end_ts = format_timestamp(end_time)
        
        # SRT format: index, timestamp, text, blank line
        srt_content.append(f"{i}")
        srt_content.append(f"{start_ts} --> {end_ts}")
        srt_content.append(line)
        srt_content.append("")  # blank line
    
    out_srt.write_text('\n'.join(srt_content), encoding='utf-8')

def format_timestamp(seconds: float) -> str:
    """Convert seconds to SRT timestamp format: HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="", help="Path to shorts JSON to use")
    args = parser.parse_args()

    # Determine which JSON file to use
    if args.input:
        json_path = Path(args.input)
        if not json_path.exists():
            raise FileNotFoundError(f"--input file not found: {json_path}")
    else:
        json_files = sorted(Path("data/temp").glob("shorts_*.json"), key=lambda p: p.stat().st_mtime)
        if not json_files:
            raise FileNotFoundError("No data/temp/shorts_*.json found. Run generate_scripts.py first.")
        json_path = json_files[-1]

    print(f"📂 Using shorts file: {json_path}")

    # Read shorts JSON to get the original scripts
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    date_str = payload.get("date", "unknown-date")
    audio_dir = Path("output") / date_str / "audio"
    srt_dir = Path("output") / date_str / "captions"
    srt_dir.mkdir(parents=True, exist_ok=True)

    for short in payload.get("shorts", []):
        sid = short["id"]
        script = short["voice_script"].strip()

        audio_file = audio_dir / f"{sid}.wav"
        srt_file = srt_dir / f"{sid}.srt"

        if not audio_file.exists():
            print(f"⚠️  Audio not found: {audio_file}")
            continue

        # Get audio duration
        duration = get_audio_duration(audio_file)

        # Create SRT from original script text
        create_srt_from_text(script, duration, srt_file)

        print(f"✅ {sid}: {srt_file} ({duration:.2f}s, {len(script.split())} words)")


if __name__ == "__main__":
    main()