from flask import Flask, render_template, request, jsonify
from pathlib import Path
import json
import subprocess
import sys
from datetime import date
import shutil
import os

app = Flask(__name__)
DATA_DIR = Path("data")
BACKGROUNDS_DIR = Path("assets/backgrounds")
ORIGINAL_SOURCE_FILE = "manual_entry"  # Track original source filename

def get_available_backgrounds():
    """Scan backgrounds folder and return list of video files"""
    if not BACKGROUNDS_DIR.exists():
        return []
    
    video_files = []
    for ext in ['.mp4', '.mov', '.avi', '.webm']:
        video_files.extend(BACKGROUNDS_DIR.glob(f'*{ext}'))
    
    return sorted([f.name for f in video_files])



def get_available_voices():
    """Scan piper_voice folder and return list of voice models"""
    voice_dir = Path("assets/piper_voice")
    if not voice_dir.exists():
        return []
    
    # Find all .onnx files (each is a voice model)
    voice_files = []
    for onnx_file in voice_dir.glob("*.onnx"):
        # Extract a friendly name from the filename
        # e.g., "en_US-lessac-medium.onnx" -> "en_US-lessac-medium"
        voice_name = onnx_file.stem
        voice_files.append({
            "filename": onnx_file.name,
            "display_name": voice_name
        })
    
    return sorted(voice_files, key=lambda x: x['display_name'])

@app.route('/')
def index():
    backgrounds = get_available_backgrounds()
    voices = get_available_voices()
    
    default_bg = backgrounds[0] if backgrounds else "ocean.mp4"
    default_voice = voices[0]['filename'] if voices else "default.onnx"
    
    return render_template('content_editor.html', 
                         backgrounds=backgrounds,
                         default_background=default_bg,
                         voices=voices,
                         default_voice=default_voice)



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

        # ADD THIS DEBUG LINE:
        print(f"🔍 Stored source filename: '{ORIGINAL_SOURCE_FILE}'")
        
        # Return the raw snippets
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

@app.route('/ai-enhance', methods=['POST'])
def ai_enhance():
    """Run AI enhancement on all blocks"""
    blocks = request.json.get('blocks', [])
    
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
        
        # Run generate_scripts to enhance
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
        enhanced_blocks = []
        
        # Get default voice
        voices = get_available_voices()
        default_voice = voices[0]['filename'] if voices else "default.onnx"
        
        for i, short in enumerate(shorts_data.get("shorts", [])):
            enhanced_blocks.append({
                "id": short["id"],
                "text": short["voice_script"],
                "title": short.get("title", ""),
                "background_video": short.get("background_video", blocks[i].get("background_video", "ocean.mp4") if i < len(blocks) else "ocean.mp4"),
                "speech_speed": short.get("speech_speed", blocks[i].get("speech_speed", "1.0") if i < len(blocks) else "1.0"),
                "voice_model": blocks[i].get("voice_model", default_voice) if i < len(blocks) else default_voice
            })
        
        return jsonify({
            "status": "success",
            "enhanced_blocks": enhanced_blocks
        })
        
    except Exception as e:
        print(f"Error in AI enhance: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/process', methods=['POST'])
def process():
    """Process blocks directly to audio/captions/video"""
    blocks = request.json.get('blocks', [])
    
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
                "voice_script": block['text'],
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
                
# if __name__ == "__main__":
#     app.run(debug=False, port=5001, host='127.0.0.1')

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", "5001"))
    app.run(debug=False, host="0.0.0.0", port=port)