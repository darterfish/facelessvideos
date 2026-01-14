import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import List, Dict


DATA_DIR = Path("data")
DEFAULT_MAX_CHARS = 1600          # per snippet; tune later
DEFAULT_MIN_CHARS = 300           # skip tiny fragments


def list_sources() -> List[Path]:
    exts = (".txt", ".md")
    files = sorted([p for p in DATA_DIR.glob("*") if p.suffix.lower() in exts])
    return files


def choose_source_interactive(files: List[Path]) -> Path:
    print("\nAvailable source files in /data:\n")
    for i, p in enumerate(files, start=1):
        print(f"  [{i}] {p.name}")
    choice = input("\nSelect file number: ").strip()
    idx = int(choice) - 1
    return files[idx]


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_into_snippets(text: str, max_chars: int, min_chars: int) -> List[str]:
    text = _clean(text)

    # First split on paragraph boundaries
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]

    snippets: List[str] = []
    buf = ""

    def flush():
        nonlocal buf
        if len(buf) >= min_chars:
            snippets.append(buf.strip())
        buf = ""

    for p in paras:
        # If a single paragraph is huge, hard-split it
        if len(p) > max_chars:
            flush()
            start = 0
            while start < len(p):
                chunk = p[start:start + max_chars].strip()
                if len(chunk) >= min_chars:
                    snippets.append(chunk)
                start += max_chars
            continue

        # Normal packing
        if not buf:
            buf = p
        elif len(buf) + 2 + len(p) <= max_chars:
            buf = buf + "\n\n" + p
        else:
            flush()
            buf = p

    flush()
    return snippets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="", help="Source filename inside /data (e.g., source.txt). If omitted, prompts you.")
    ap.add_argument("--max_chars", type=int, default=DEFAULT_MAX_CHARS)
    ap.add_argument("--min_chars", type=int, default=DEFAULT_MIN_CHARS)
    args = ap.parse_args()

    files = list_sources()
    if not files:
        raise FileNotFoundError("No .txt or .md files found in ./data")

    if args.source:
        src_path = DATA_DIR / args.source
        if not src_path.exists():
            raise FileNotFoundError(f"Not found: {src_path}")
    else:
        src_path = choose_source_interactive(files)

    raw = src_path.read_text(encoding="utf-8")
    snippets = split_into_snippets(raw, max_chars=args.max_chars, min_chars=args.min_chars)

    out = {
        "date": str(date.today()),
        "source_file": src_path.name,
        "max_chars": args.max_chars,
        "min_chars": args.min_chars,
        "snippets": [{"id": f"N{i:03d}", "text": s} for i, s in enumerate(snippets, start=1)]
    }

    out_path = DATA_DIR / f"snippets_{out['date']}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Wrote: {out_path}")
    print(f"✅ Snippets: {len(out['snippets'])}")
    print(f"✅ Source: {src_path.name}")


if __name__ == "__main__":
    main()
