from pathlib import Path
import re
import textwrap
import argparse
import json
from datetime import date

MAX_CHARS = 24   # For 52pt font with margins - keeps 2-3 words per line max

def rewrap(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return ""
    # Wrap text but DON'T truncate - return ALL lines
    lines = textwrap.wrap(text, width=MAX_CHARS, break_long_words=False, break_on_hyphens=False)
    return "\n".join(lines)

def rewrap_srt(path: Path) -> None:
    raw = path.read_text(encoding="utf-8").strip()
    blocks = raw.split("\n\n")
    out_blocks = []

    for b in blocks:
        lines = b.splitlines()
        if len(lines) < 3:
            out_blocks.append(b)
            continue

        idx = lines[0]
        timing = lines[1]
        text = "\n".join(lines[2:])
        out_blocks.append("\n".join([idx, timing, rewrap(text)]))

    path.write_text("\n\n".join(out_blocks) + "\n", encoding="utf-8")

def main():


    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, default="", help="Path to shorts JSON (used only to detect date)")
    args = parser.parse_args()

    # Determine date_str (either from --input JSON or fallback to today)
    if args.input:
        json_path = Path(args.input)
        if not json_path.exists():
            raise FileNotFoundError(f"--input file not found: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        date_str = payload.get("date", "unknown-date")
    else:
        date_str = str(date.today())

    srt_dir = Path("output") / date_str / "captions"
    if not srt_dir.exists():
        raise FileNotFoundError(f"No captions directory found: {srt_dir}")

    srt_files = sorted(srt_dir.glob("*.srt"))
    if not srt_files:
        raise FileNotFoundError(f"No .srt files found in: {srt_dir}")

    print(f"🧾 Rewrapping {len(srt_files)} captions in: {srt_dir}")

    for srt_file in srt_files:
        rewrap_srt(srt_file)
        print(f"✅ Rewrapped: {srt_file.name}")


if __name__ == "__main__":
    main()