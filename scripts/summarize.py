#!/usr/bin/env python3
import sys
import json
import urllib.request
import argparse

# Default fast model
DEFAULT_MODEL = "qwen2.5:0.5b"
OLLAMA_API = "http://127.0.0.1:11435/api/generate"

def call_ollama(prompt, model=DEFAULT_MODEL, system=""):
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 128
        }
    }
    if system:
        data["system"] = system
        
    try:
        req = urllib.request.Request(
            OLLAMA_API,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode('utf-8'))
            return res.get("response", "").strip()
    except Exception as e:
        return f"Error: {e}"

def main():
    parser = argparse.ArgumentParser(description="Blast-fast summary and title generation.")
    parser.add_argument("text", nargs="?", help="Text to process. If omitted, reads from stdin.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model to use (default: {DEFAULT_MODEL})")
    parser.add_argument("--title", action="store_true", help="Generate a title instead of a summary")
    
    args = parser.parse_args()
    
    text = args.text
    if not text:
        if sys.stdin.isatty():
            parser.print_help()
            return
        text = sys.stdin.read()
        
    if not text.strip():
        print("No input text provided.")
        return

    if args.title:
        system = "You are a professional editor. Generate a concise, catchy title (max 6 words) for the provided text. Output ONLY the title."
        prompt = f"Text:\n{text}\n\nTitle:"
    else:
        system = "You are a summarization assistant. Provide a blast-fast, one-sentence summary of the following text."
        prompt = f"Text:\n{text}\n\nSummary:"
        
    result = call_ollama(prompt, model=args.model, system=system)
    print(result)

if __name__ == "__main__":
    main()
