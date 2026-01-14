#cd ~/Desktop/New_Python/high_performance_sales
#source .venv/bin/activate
#python3 run_pipeline
import subprocess
import sys
import webbrowser
from pathlib import Path
from datetime import date

def main():
    print("\n🌐 Opening content editor in your browser...")
    print("📝 Load a file or enter text manually, then click Process\n")
    
    # Just launch the Flask server and open browser
    # No file selection in terminal anymore
    import review_snippets
    
    # Open browser
    webbrowser.open('http://127.0.0.1:5001')
    
    # Run Flask (this will block until user stops server)
    try:
        review_snippets.app.run(debug=False, port=5001, host='127.0.0.1')
    except KeyboardInterrupt:
        print("\n✅ Server stopped")

if __name__ == "__main__":
    main()