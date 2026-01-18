from flask import Flask, render_template, request, jsonify, send_file
from pathlib import Path
import json
import subprocess
import sys
from datetime import date
import shutil
import os
import requests

app = Flask(__name__)
DATA_DIR = Path("data")
BACKGROUNDS_DIR = Path("assets/backgrounds")
ORIGINAL_SOURCE_FILE = "manual_entry"  # Track original source filename

# Clear old snippets at startup
def clear_old_snippets():
    for snippets_file in DATA_DIR.glob("snippets_*.json"):
        try:
            snippets_file.unlink()
            print(f"🗑️  Cleared old snippet file: {snippets_file.name}")
        except Exception as e:
            print(f"Failed to delete {snippets_file.name}: {e}")

clear_old_snippets()

def get_available_backgrounds():
    """Scan backgrounds folder and return list of video files"""
    if not BACKGROUNDS_DIR.exists():
        return []
    
    video_files = []
    for ext in ['.mp4', '.mov', '.avi', '.webm']:
        video_files.extend(BACKGROUNDS_DIR.glob(f'*{ext}'))
    
    return sorted([f.name for f in video_files])



def get_available_voices():
    """Scan both piper_voice and user_voices folders and return list of voice models"""
    voice_files = []
    
    # Scan default voices
    default_voice_dir = Path("assets/piper_voice")
    if default_voice_dir.exists():
        for onnx_file in default_voice_dir.glob("*.onnx"):
            voice_name = onnx_file.stem
            voice_files.append({
                "filename": onnx_file.name,
                "display_name": voice_name
            })
    
    # Scan user-uploaded voices
    user_voice_dir = Path("assets/user_voices")
    if user_voice_dir.exists():
        for onnx_file in user_voice_dir.glob("*.onnx"):
            voice_name = onnx_file.stem
            voice_files.append({
                "filename": onnx_file.name,
                "display_name": f"{voice_name} (custom)"
            })
    
    return sorted(voice_files, key=lambda x: x['display_name'])

def enhance_with_openai(blocks, api_key):
    """Enhance snippets using OpenAI API"""
    import requests
    
    enhanced_blocks = []
    
    system_prompt = """You are an expert YouTube Shorts scriptwriter for a channel called "High-Performance Sales".
Tone: calm authority, confident, concise, practical. No hype. No profanity.
Audience: working professionals (B2B sales, founders, consultants).

Your task is to optimize the provided script for a YouTube Short (35-60 seconds when read aloud, roughly 90-150 words).
- Start with a strong hook in the first 1-2 sentences
- Use specific, actionable language
- End with a crisp takeaway
- The script should fully cover the key points from the source material
- Format with line breaks after each sentence for caption timing
"""
    
    for i, block in enumerate(blocks, start=1):
        user_prompt = f"""Optimize this script for a YouTube Short:

{block['text']}

Return ONLY the optimized script with line breaks after each sentence. No additional commentary."""
        
        try:
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'gpt-4',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.7,
                    'max_tokens': 500
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"OpenAI API returned {response.status_code}")
            
            result = response.json()
            enhanced_text = result['choices'][0]['message']['content'].strip()
            
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": enhanced_text,
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
            
            print(f"✅ Enhanced block {i}/{len(blocks)} with OpenAI")
            
        except Exception as e:
            print(f"Error enhancing block {i}: {e}")
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": block['text'],
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
    
    return enhanced_blocks


def enhance_with_claude(blocks, api_key):
    """Enhance snippets using Anthropic Claude API"""
    import requests
    
    enhanced_blocks = []
    
    system_prompt = """You are an expert YouTube Shorts scriptwriter for a channel called "High-Performance Sales".
Tone: calm authority, confident, concise, practical. No hype. No profanity.
Audience: working professionals (B2B sales, founders, consultants).

Your task is to optimize the provided script for a YouTube Short (35-60 seconds when read aloud, roughly 90-150 words).
- Start with a strong hook in the first 1-2 sentences
- Use specific, actionable language
- End with a crisp takeaway
- The script should fully cover the key points from the source material
- Format with line breaks after each sentence for caption timing
"""
    
    for i, block in enumerate(blocks, start=1):
        user_prompt = f"""Optimize this script for a YouTube Short:

{block['text']}

Return ONLY the optimized script with line breaks after each sentence. No additional commentary."""
        
        try:
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json'
                },
                json={
                    'model': 'claude-sonnet-4-20250514',
                    'max_tokens': 1024,
                    'system': system_prompt,
                    'messages': [
                        {'role': 'user', 'content': user_prompt}
                    ]
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Claude API error: {response.status_code} - {response.text}")
                raise Exception(f"Claude API returned {response.status_code}")
            
            result = response.json()
            enhanced_text = result['content'][0]['text'].strip()
            
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": enhanced_text,
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
            
            print(f"✅ Enhanced block {i}/{len(blocks)} with Claude")
            
        except Exception as e:
            print(f"Error enhancing block {i}: {e}")
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": block['text'],
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
    
    return enhanced_blocks


def enhance_with_perplexity(blocks, api_key):
    """Enhance snippets using Perplexity API"""
    import requests
    
    enhanced_blocks = []
    
    system_prompt = """You are an expert YouTube Shorts scriptwriter for a channel called "High-Performance Sales".
Tone: calm authority, confident, concise, practical. No hype. No profanity.
Audience: working professionals (B2B sales, founders, consultants).

Your task is to optimize the provided script for a YouTube Short (35-60 seconds when read aloud, roughly 90-150 words).
- Start with a strong hook in the first 1-2 sentences
- Use specific, actionable language
- End with a crisp takeaway
- The script should fully cover the key points from the source material
- Format with line breaks after each sentence for caption timing
"""
    
    for i, block in enumerate(blocks, start=1):
        user_prompt = f"""Optimize this script for a YouTube Short:

{block['text']}

Return ONLY the optimized script with line breaks after each sentence. No additional commentary."""
        
        try:
            response = requests.post(
                'https://api.perplexity.ai/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.1-sonar-small-128k-online',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ]
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Perplexity API error: {response.status_code} - {response.text}")
                raise Exception(f"Perplexity API returned {response.status_code}")
            
            result = response.json()
            enhanced_text = result['choices'][0]['message']['content'].strip()
            
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": enhanced_text,
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
            
            print(f"✅ Enhanced block {i}/{len(blocks)} with Perplexity")
            
        except Exception as e:
            print(f"Error enhancing block {i}: {e}")
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": block['text'],
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
    
    return enhanced_blocks


def enhance_with_grok(blocks, api_key):
    """Enhance snippets using Grok (xAI) API"""
    import requests
    
    enhanced_blocks = []
    
    system_prompt = """You are an expert YouTube Shorts scriptwriter for a channel called "High-Performance Sales".
Tone: calm authority, confident, concise, practical. No hype. No profanity.
Audience: working professionals (B2B sales, founders, consultants).

Your task is to optimize the provided script for a YouTube Short (35-60 seconds when read aloud, roughly 90-150 words).
- Start with a strong hook in the first 1-2 sentences
- Use specific, actionable language
- End with a crisp takeaway
- The script should fully cover the key points from the source material
- Format with line breaks after each sentence for caption timing
"""
    
    for i, block in enumerate(blocks, start=1):
        user_prompt = f"""Optimize this script for a YouTube Short:

{block['text']}

Return ONLY the optimized script with line breaks after each sentence. No additional commentary."""
        
        try:
            response = requests.post(
                'https://api.x.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'grok-beta',
                    'messages': [
                        {'role': 'system', 'content': system_prompt},
                        {'role': 'user', 'content': user_prompt}
                    ],
                    'temperature': 0.7
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"Grok API error: {response.status_code} - {response.text}")
                raise Exception(f"Grok API returned {response.status_code}")
            
            result = response.json()
            enhanced_text = result['choices'][0]['message']['content'].strip()
            
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": enhanced_text,
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
            
            print(f"✅ Enhanced block {i}/{len(blocks)} with Grok")
            
        except Exception as e:
            print(f"Error enhancing block {i}: {e}")
            enhanced_blocks.append({
                "id": f"S{i:03d}",
                "text": block['text'],
                "title": f"Short {i}",
                "background_video": block.get('background_video', 'ocean.mp4'),
                "speech_speed": block.get('speech_speed', '1.0'),
                "voice_model": block.get('voice_model', 'default.onnx')
            })
    
    return enhanced_blocks



@app.route('/')
def index():
    backgrounds = get_available_backgrounds()
    voices = get_available_voices()
    
    default_bg = backgrounds[0] if backgrounds else "ocean.mp4"
    default_voice = voices[0]['filename'] if voices else "default.onnx"
    
    # Always start with blank page - snippets only appear after upload
    # Load snippets if they exist (created from recent upload)
    snip_files = sorted(DATA_DIR.glob("snippets_*.json"))
    snippets = []
    source_file = ""
    snippets_file = ""
    
    if snip_files:
        snip_path = snip_files[-1]
        snip_data = json.loads(snip_path.read_text(encoding="utf-8"))
        snippets = snip_data.get("snippets", [])
        source_file = snip_data.get("source_file", "")
        snippets_file = snip_path.name
        
        # Ensure each snippet has required fields
        for snippet in snippets:
            snippet.setdefault('background_video', default_bg)
            snippet.setdefault('voice_model', default_voice)
            snippet.setdefault('speech_speed', '1.0')
            snippet.setdefault('voice_script', snippet.get('text', ''))

    return render_template('content_editor.html', 
                         backgrounds=backgrounds,
                         default_background=default_bg,
                         voices=voices,
                         default_voice=default_voice,
                         snippets=snippets,
                         source_file=source_file,
                         snippets_file=snippets_file,
                         snippet_count=len(snippets))

@app.route('/upload-file', methods=['POST'])
def upload_file():
    """Handle file upload and create snippets"""
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400
    
    if not file.filename.endswith('.txt'):
        return jsonify({"status": "error", "message": "Only .txt files allowed"}), 400
    
    try:
        # Save uploaded file temporarily
        temp_file = DATA_DIR / file.filename
        file.save(temp_file)
        
        # Run make_snippets on it
        subprocess.run([
            sys.executable,
            "content_engine/make_snippets.py",
            "--source", file.filename,
            "--max_chars", "700",
            "--min_chars", "120"
        ], check=True)
        
        # Load the created snippets
        snip_files = sorted(DATA_DIR.glob("snippets_*.json"))
        if not snip_files:
            return jsonify({"status": "error", "message": "Failed to create snippets"}), 500
        
        snip_path = snip_files[-1]
        snip_data = json.loads(snip_path.read_text(encoding="utf-8"))
        snippets = snip_data.get("snippets", [])
        
        # Store original source filename
        global ORIGINAL_SOURCE_FILE
        ORIGINAL_SOURCE_FILE = file.filename.replace('.txt', '').replace('.md', '')
        print(f"🔍 Stored source filename: '{ORIGINAL_SOURCE_FILE}'")
        
        # Get defaults for dropdowns
        backgrounds = get_available_backgrounds()
        voices = get_available_voices()
        default_bg = backgrounds[0] if backgrounds else "ocean.mp4"
        default_voice = voices[0]['filename'] if voices else "default.onnx"
        
        # Add default fields to each snippet
        for snippet in snippets:
            snippet['background_video'] = default_bg
            snippet['voice_model'] = default_voice
            snippet['speech_speed'] = '1.0'
        
        # Return the snippets with defaults
        return jsonify({
            "status": "success",
            "snippets": snippets,
            "source_file": file.filename
        })
        
    except Exception as e:
        print(f"Error processing file: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload-videos', methods=['POST'])
def upload_videos():
    """Handle background video uploads"""
    if 'videos' not in request.files:
        return jsonify({"status": "error", "message": "No videos uploaded"}), 400
    
    files = request.files.getlist('videos')
    if not files:
        return jsonify({"status": "error", "message": "No videos selected"}), 400
    
    uploaded = []
    backgrounds_dir = Path("assets/backgrounds")
    backgrounds_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        for file in files:
            if file.filename == '':
                continue
            
            # Check file extension
            ext = Path(file.filename).suffix.lower()
            if ext not in ['.mp4', '.mov', '.avi', '.webm']:
                continue
            
            # Save file
            save_path = backgrounds_dir / file.filename
            file.save(save_path)
            uploaded.append(file.filename)
        
        if not uploaded:
            return jsonify({"status": "error", "message": "No valid video files uploaded"}), 400
        
        return jsonify({
            "status": "success",
            "uploaded": uploaded,
            "message": f"Uploaded {len(uploaded)} video(s)"
        })
        
    except Exception as e:
        print(f"Error uploading videos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload-voices', methods=['POST'])
def upload_voices():
    """Handle voice model uploads (.onnx and .onnx.json files)"""
    if 'voices' not in request.files:
        return jsonify({"status": "error", "message": "No voice files uploaded"}), 400
    
    files = request.files.getlist('voices')
    if not files:
        return jsonify({"status": "error", "message": "No voice files selected"}), 400
    
    uploaded = []
    voices_dir = Path("assets/user_voices")
    voices_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        for file in files:
            if file.filename == '':
                continue
            
            # Check file extension
            ext = Path(file.filename).suffix.lower()
            if ext not in ['.onnx', '.json']:
                continue
            
            # Save file
            save_path = voices_dir / file.filename
            file.save(save_path)
            uploaded.append(file.filename)
        
        if not uploaded:
            return jsonify({"status": "error", "message": "No valid voice files uploaded (.onnx or .json)"}), 400
        
        return jsonify({
            "status": "success",
            "uploaded": uploaded,
            "message": f"Uploaded {len(uploaded)} voice file(s)"
        })
        
    except Exception as e:
        print(f"Error uploading voice files: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/save', methods=['POST'])
def save():
    """Save snippet edits without running pipeline"""
    snippets = request.json.get('snippets', [])
    
    if not snippets:
        return jsonify({"status": "error", "message": "No snippets to save"}), 400
    
    try:
        # Create snippets data structure
        temp_snippets = {
            "date": str(date.today()),
            "source_file": ORIGINAL_SOURCE_FILE if ORIGINAL_SOURCE_FILE != "manual_entry" else "manual_entry",
            "snippets": []
        }
        
        for snippet in snippets:
            temp_snippets["snippets"].append({
                "id": snippet['id'],
                "text": snippet.get('voice_script', snippet.get('text', '')),
                "background_video": snippet.get('background_video', 'ocean.mp4'),
                "voice_model": snippet.get('voice_model', 'default.onnx'),
                "speech_speed": snippet.get('speech_speed', '1.0')
            })
        
        # Save to data directory
        save_path = DATA_DIR / f"snippets_{date.today().isoformat()}.json"
        save_path.write_text(json.dumps(temp_snippets, ensure_ascii=False, indent=2), encoding="utf-8")
        
        return jsonify({
            "status": "success",
            "message": "Snippets saved successfully"
        })
        
    except Exception as e:
        print(f"Error saving snippets: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

Step 3: Update Backend /ai-enhance Route
File: review_snippets.py
Find the /ai-enhance route (around line 270). Replace the entire function with:
python@app.route('/ai-enhance', methods=['POST'])
def ai_enhance():
    """Run AI enhancement on all blocks using local Ollama or online AI providers"""
    blocks = request.json.get('blocks', [])
    ai_mode = request.json.get('ai_mode', 'local')
    api_key = request.json.get('api_key', '')
    
    if not blocks:
        return jsonify({"status": "error", "message": "No blocks to enhance"}), 400
    
    try:
        # Create temporary snippets file
        temp_snippets = {
            "date": str(date.today()),
            "source_file": ORIGINAL_SOURCE_FILE if ORIGINAL_SOURCE_FILE != "manual_entry" else "manual_entry",
            "snippets": []
        }
        
        for i, block in enumerate(blocks, start=1):
            temp_snippets["snippets"].append({
                "id": f"N{i:03d}",
                "text": block['text']
            })
        
        # Save temp snippets
        temp_snip_path = DATA_DIR / f"snippets_{date.today().isoformat()}.json"
        temp_snip_path.write_text(json.dumps(temp_snippets, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Choose AI enhancement method
        if ai_mode == 'local':
            # Use local Ollama (existing method)
            subprocess.run([
                sys.executable,
                "content_engine/generate_scripts.py",
                "--snippets", str(temp_snip_path)
            ], check=True)
            
            # Load enhanced shorts
            temp_dir = Path("data/temp")
            shorts_files = sorted(temp_dir.glob("shorts_*.json"), key=lambda p: p.stat().st_mtime)
            
            if not shorts_files:
                return jsonify({"status": "error", "message": "AI enhancement failed"}), 500
            
            shorts_data = json.loads(shorts_files[-1].read_text(encoding="utf-8"))
            
            # Get default voice
            voices = get_available_voices()
            default_voice = voices[0]['filename'] if voices else "default.onnx"
            
            enhanced_blocks = []
            for i, short in enumerate(shorts_data.get("shorts", [])):
                original_voice = blocks[i].get("voice_model", default_voice) if i < len(blocks) else default_voice
                
                enhanced_blocks.append({
                    "id": short["id"],
                    "text": short["voice_script"],
                    "title": short.get("title", ""),
                    "background_video": short.get("background_video", blocks[i].get("background_video", "ocean.mp4") if i < len(blocks) else "ocean.mp4"),
                    "speech_speed": short.get("speech_speed", blocks[i].get("speech_speed", "1.0") if i < len(blocks) else "1.0"),
                    "voice_model": short.get("voice_model", original_voice)
                })
        else:
            # Use online AI provider
            if ai_mode == 'openai':
                enhanced_blocks = enhance_with_openai(blocks, api_key)
            elif ai_mode == 'claude':
                enhanced_blocks = enhance_with_claude(blocks, api_key)
            elif ai_mode == 'perplexity':
                enhanced_blocks = enhance_with_perplexity(blocks, api_key)
            elif ai_mode == 'grok':
                enhanced_blocks = enhance_with_grok(blocks, api_key)
            else:
                return jsonify({"status": "error", "message": f"Unknown AI mode: {ai_mode}"}), 400
        
        return jsonify({
            "status": "success",
            "enhanced_blocks": enhanced_blocks
        })
        
    except Exception as e:
        print(f"Error in AI enhance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/continue', methods=['POST'])
@app.route('/process', methods=['POST'])
def process():
    """Process blocks directly to audio/captions/video"""
    print(f"🔍 Raw request.json: {request.json}")
    blocks = request.json.get('blocks', [])
    
    print(f"🔍 Received {len(blocks) if blocks else 0} blocks")
    if blocks:
        print(f"🔍 First block keys: {blocks[0].keys() if blocks else 'none'}")
    
    if not blocks:
        return jsonify({"status": "error", "message": "No blocks to process"}), 400
    
    temp_dir = Path("data/temp")
    shorts_file = None
    
    try:
        # Create shorts JSON directly from blocks
        shorts_data = {
            "date": str(date.today()),
            "channel": "High-Performance Sales",
            "source_file": ORIGINAL_SOURCE_FILE if ORIGINAL_SOURCE_FILE != "manual_entry" else "manual_entry",
            "shorts": []
        }
        
        # Get default voice
        voices = get_available_voices()
        default_voice = voices[0]['filename'] if voices else "default.onnx"

        for i, block in enumerate(blocks, start=1):
            shorts_data["shorts"].append({
                "id": f"S{i:03d}",
                "voice_script": block.get('voice_script', block.get('text', '')),
                "title": block.get('title', f"Short {i}"),
                "background_video": block.get('background_video', 'ocean.mp4'),
                "voice_model": block.get('voice_model', default_voice),
                "speech_speed": block.get('speech_speed', '1.0'),
                "hook": "",
                "on_screen_text": [],
                "visual_cues": [],
                "description": "",
                "hashtags": []
            })    

        # Clear old output directory for today's date to avoid mixing old/new videos
        date_str = str(date.today())
        output_date_dir = Path("output") / date_str
        if output_date_dir.exists():
            print(f"🗑️  Clearing old output directory: {output_date_dir}")
            shutil.rmtree(output_date_dir)
                
        # Save shorts file
        temp_dir.mkdir(exist_ok=True)
        source_name = ORIGINAL_SOURCE_FILE if ORIGINAL_SOURCE_FILE != "manual_entry" else "manual"
        # ADD THIS DEBUG LINE:
        print(f"🔍 Using source name for file: '{source_name}' (ORIGINAL_SOURCE_FILE = '{ORIGINAL_SOURCE_FILE}')")
        shorts_file = temp_dir / f"shorts_{date.today().isoformat()}_{source_name}.json"
        shorts_file.write_text(json.dumps(shorts_data, ensure_ascii=False, indent=2), encoding="utf-8")
        
        
        # Clear temp JSON files
        for json_file in temp_dir.glob("*.json"):
            if json_file != shorts_file:  # Don't delete the one we just created
                json_file.unlink()
        
        # Clear old snippets files
        print(f"🗑️  Cleaning old snippets files")
        for snippets_file in DATA_DIR.glob("snippets_*.json"):
            snippets_file.unlink()
        
        # Run pipeline
        print("\n🎤 Starting audio generation...")
        subprocess.run([sys.executable, "audio_engine/tts.py"], check=True)
        
        print("\n📝 Starting caption generation...")
        subprocess.run([sys.executable, "caption_engine/make_srt.py"], check=True)
        
        print("\n🔄 Rewrapping captions...")
        subprocess.run([sys.executable, "caption_engine/rewrap_srt.py"], check=True)
        
        print("\n🎬 Rendering videos...")
        subprocess.run([sys.executable, "visual_engine/render_short.py"], check=True)
        
        print("\n✅ Pipeline completed!")
        return jsonify({"status": "success", "message": "Videos created successfully!"})
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Pipeline failed: {e}")
        return jsonify({"status": "error", "message": f"Pipeline failed: {str(e)}"}), 500
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Unexpected error: {str(e)}"}), 500
    finally:
        # ALWAYS clean up temp files, even if pipeline fails
        print("\n🗑️  Cleaning up temp files...")
        if temp_dir.exists():
            for json_file in temp_dir.glob("*.json"):
                try:
                    json_file.unlink()
                    print(f"   Deleted: {json_file.name}")
                except Exception as e:
                    print(f"   Failed to delete {json_file.name}: {e}")
        
        # Clean up model debug files
        for debug_file in DATA_DIR.glob("_last_model_output*.txt"):
            try:
                debug_file.unlink()
                print(f"   Deleted: {debug_file.name}")
            except Exception as e:
                print(f"   Failed to delete {debug_file.name}: {e}")
                
@app.route('/download-videos', methods=['GET'])
def download_videos():
    """Create a ZIP file of all generated videos and send to user"""
    import zipfile
    from io import BytesIO
    
    try:
        # Find the most recent output directory
        output_dirs = sorted(Path("output").glob("20??-??-??"), reverse=True)
        if not output_dirs:
            return jsonify({"status": "error", "message": "No videos found"}), 404
        
        latest_dir = output_dirs[0]
        video_dir = latest_dir / "video"
        
        if not video_dir.exists():
            return jsonify({"status": "error", "message": "No videos found"}), 404
        
        # Get all video files
        video_files = list(video_dir.glob("*.mp4"))
        if not video_files:
            return jsonify({"status": "error", "message": "No videos found"}), 404
        
        # Create ZIP file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for video_file in video_files:
                zip_file.write(video_file, arcname=video_file.name)
        
        zip_buffer.seek(0)
        
        # Send ZIP file
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'videos_{latest_dir.name}.zip'
        )
        
    except Exception as e:
        print(f"Error creating ZIP: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500



# if __name__ == "__main__":
#     app.run(debug=False, port=5001, host='127.0.0.1')



if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=False, host="0.0.0.0", port=port)