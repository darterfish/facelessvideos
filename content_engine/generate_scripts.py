# content_engine/generate_scripts.py

import json
print("🔥 generate_scripts.py LOADED:", __file__)
from datetime import date
from typing import Any, Dict, List
import ollama
import argparse
from pathlib import Path




MODEL = "llama3:latest"
CHANNEL = "High-Performance Sales"
SHORTS_PER_RUN = 1

SYSTEM_PROMPT = """You are an expert YouTube Shorts scriptwriter for a channel called "High-Performance Sales".
Tone: calm authority, confident, concise, practical. No hype. No profanity.
Audience: working professionals (B2B sales, founders, consultants).

Output MUST be valid JSON ONLY (no markdown, no backticks, no commentary).
"""

USER_PROMPT_TEMPLATE = """Create {n} YouTube Shorts concepts based on this source material.

SOURCE MATERIAL:
{source}

Constraints:
- Each short: 35–60 seconds when read aloud (roughly 90-150 words).
- The voice_script should fully cover the key points from the source material.
- Do NOT make the script significantly shorter than the source material unless the source is very verbose.
- Start with a strong hook in the first 1–2 sentences.
- Avoid vague motivational lines. Use specific, actionable language.
- Include 2–4 on-screen text beats (short phrases) that match the spoken script.
- Include simple visual cues (e.g., "show phone icon", "highlight keyword", "fade in bullet list").
- End with a crisp takeaway (no "like and subscribe" line).
- No claims about specific clients unless explicitly present in the source.

Return JSON with this schema EXACTLY:
{{
  "date": "YYYY-MM-DD",
  "channel": "High-Performance Sales",
  "shorts": [
    {{
      "id": "S001",
      "hook": "...",
      "voice_script": "...",
      "on_screen_text": ["...", "..."],
      "visual_cues": ["...", "..."],
      "title": "...",
      "description": "...",
      "hashtags": ["#sales", "#b2b", "..."]
    }}
  ]
}}
"""

def format_voice_script(script: str) -> str:
    """Format voice script with line breaks after sentences for caption splitting"""
    import re
    
    # Remove any existing line breaks first to normalize
    script = script.replace('\n', ' ').replace('\r', ' ')
    
    # Remove extra spaces
    script = re.sub(r'\s+', ' ', script).strip()
    
    # Split on sentence endings: period/question/exclamation followed by space
    # Look for: [.!?] followed by one or more spaces, followed by capital letter or quote
    script = re.sub(r'([.!?])\s+([A-Z"\'])', r'\1\n\2', script)
    
    return script

def _extract_json(text: str) -> Dict[str, Any]:
    """
    Robustly extract the first JSON object from a model response,
    even if there is extra text before/after or multiple JSON objects.
    """
    text = text.strip()
    decoder = json.JSONDecoder()

    first = text.find("{")
    if first == -1:
        raise ValueError("No JSON object found in model output (no '{').")

    candidate = text[first:]
    obj, _end = decoder.raw_decode(candidate)
    if not isinstance(obj, dict):
        raise ValueError("Top-level JSON must be an object.")
    return obj


def _validate_payload(data: Dict[str, Any], n_expected: int) -> None:
    shorts = data.get("shorts")
    if not isinstance(shorts, list) or len(shorts) != n_expected:
        got = 0 if shorts is None else (len(shorts) if isinstance(shorts, list) else "non-list")
        raise ValueError(f"Invalid 'shorts'. Expected {n_expected} items, got {got}.")

    required = {"id", "hook", "voice_script", "on_screen_text", "visual_cues", "title", "description", "hashtags"}

    for i, s in enumerate(shorts, start=1):
        if not isinstance(s, dict):
            raise ValueError(f"Short #{i} is not an object.")
        missing = required - set(s.keys())
        if missing:
            raise ValueError(f"Short #{i} missing keys: {sorted(missing)}")
        if not str(s["voice_script"]).strip():
            raise ValueError(f"Short #{i} has empty voice_script.")
        if not isinstance(s["on_screen_text"], list) or not s["on_screen_text"]:
            raise ValueError(f"Short #{i} on_screen_text must be a non-empty list.")
        if not isinstance(s["visual_cues"], list) or not s["visual_cues"]:
            raise ValueError(f"Short #{i} visual_cues must be a non-empty list.")


def _call_model(user_prompt: str) -> str:
    resp = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        options={"temperature": 0.6, "num_predict": 1600},
    )
    return resp["message"]["content"]


def generate_shorts(source: str, n: int = SHORTS_PER_RUN) -> Dict[str, Any]:
    prompt = USER_PROMPT_TEMPLATE.format(n=n, source=source)

    # Attempt 1
    try:
        content = _call_model(prompt)
        with open("data/_last_model_output.txt", "w", encoding="utf-8") as f:
            f.write(content)

        data = _extract_json(content)

        # Never trust model for date; force today's date
        data["date"] = str(date.today())
        data["channel"] = CHANNEL

        # Ensure IDs exist
        shorts: List[Dict[str, Any]] = data.get("shorts", [])
        for i, s in enumerate(shorts, start=1):
            if isinstance(s, dict):
                s.setdefault("id", f"S{i:03d}")

        _validate_payload(data, n)
        return data
        
    except Exception as e:
        print(f"   ⚠️  Attempt 1 failed: {e}")
        print(f"   🔄 Retrying with stricter prompt...")
        
        # Attempt 2 (strict retry)
        strict_prompt = (
            prompt
            + "\n\nIMPORTANT:\n"
              f"- Output ONLY valid JSON. No extra text.\n"
              f"- shorts MUST contain exactly {n} items.\n"
              f"- Every short MUST include every required key.\n"
              f"- Use proper JSON formatting with double quotes.\n"
        )
        content2 = _call_model(strict_prompt)
        with open("data/_last_model_output_retry.txt", "w", encoding="utf-8") as f:
            f.write(content2)

        data2 = _extract_json(content2)
        data2["date"] = str(date.today())
        data2["channel"] = CHANNEL

        shorts2: List[Dict[str, Any]] = data2.get("shorts", [])
        for i, s in enumerate(shorts2, start=1):
            if isinstance(s, dict):
                s.setdefault("id", f"S{i:03d}")

        _validate_payload(data2, n)
        return data2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snippets", default="", help="Path to data/snippets_YYYY-MM-DD.json (if omitted, uses latest)")
    ap.add_argument("--max_shorts", type=int, default=9999, help="Safety cap (we can tune later)")
    args = ap.parse_args()

    # Pick snippets file
    if args.snippets:
        snip_path = Path(args.snippets)
    else:
        snip_files = sorted(Path("data").glob("snippets_*.json"))
        if not snip_files:
            raise FileNotFoundError("No data/snippets_*.json found. Run content_engine/make_snippets.py first.")
        snip_path = snip_files[-1]

    # ✅ ALWAYS load snippets (regardless of how snip_path was chosen)
    snip_payload = json.loads(snip_path.read_text(encoding="utf-8"))
    snippets = snip_payload.get("snippets", [])
    if not snippets:
        raise ValueError(f"No snippets found in {snip_path}")

    print(f"🔎 Using snippets file: {snip_path}")
    print(f"🔎 Source file in snippets: {snip_payload.get('source_file')}")
    print(f"🔎 Snippet count: {len(snippets)}")

    shorts_out: List[Dict[str, Any]] = []
    for sn in snippets:
        if len(shorts_out) >= args.max_shorts:
            break

        source = sn["text"].strip()
        print(f"🤖 Generating short {len(shorts_out)+1}/{min(len(snippets), args.max_shorts)}...")
        one = generate_shorts(source=source, n=1)  # 1 short per snippet
        if one.get("shorts"):
            s = one["shorts"][0]
            s["id"] = f"S{len(shorts_out)+1:03d}"
            s["source_snippet_id"] = sn["id"]
            # Copy background_video from snippet to short
            s["background_video"] = sn.get("background_video", "ocean.mp4")
            s["speech_speed"] = sn.get("speech_speed", "1.0")
            
            # Format voice_script with line breaks for captions
            original = s["voice_script"]
            formatted = format_voice_script(original)
            print(f"   🔍 Original has {original.count(chr(10))} line breaks")
            print(f"   🔍 Formatted has {formatted.count(chr(10))} line breaks")
            print(f"   🔍 First 100 chars: {formatted[:100]}...")
            s["voice_script"] = formatted
            
            shorts_out.append(s)
            print(f"   ✅ Short {s['id']} generated: {s['title'][:50]}...")

    out = {
        "date": str(date.today()),
        "channel": "High-Performance Sales",
        "source_file": snip_payload.get("source_file", ""),
        "snippets_file": snip_path.name,
        "shorts": shorts_out,
    }

    # Use source file name in output to avoid overwrites
    source_name = snip_payload.get("source_file", "").replace(".txt", "").replace(".md", "")
    # Save to temp directory
    temp_dir = Path("data/temp")
    temp_dir.mkdir(exist_ok=True)
    
    out_path = temp_dir / f"shorts_{out['date']}_{source_name}.json"
    tmp_path = out_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(out_path)

    print(f"Wrote: {out_path}")
    print(f"✅ Shorts generated: {len(shorts_out)}")

if __name__ == "__main__":
    main()