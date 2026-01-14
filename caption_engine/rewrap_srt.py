from pathlib import Path
import re
import textwrap

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
    day_dir = sorted(Path("output").glob("20??-??-??"))[-1]
    cap_dir = day_dir / "captions"
    for srt in sorted(cap_dir.glob("*.srt")):
        rewrap_srt(srt)
        print("✅ Rewrapped:", srt)

if __name__ == "__main__":
    main()