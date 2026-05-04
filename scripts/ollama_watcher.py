import re
import os
import time
import json
import sys
import pathlib

# Resolve paths relative to this script so the tool works for any user/install location
_INSTALL_DIR = pathlib.Path(__file__).resolve().parent.parent
RAW_LOG = "/var/log/ollama.log"
READABLE_LOG = str(_INSTALL_DIR / "ollama_readable.log")

def decode_go_string(s):
    try:
        # Go strings intersperse hex-escaped UTF-8 bytes (\xNN) with literal Unicode characters.
        b = s.encode("utf-8")
        def hex_repl(match):
            return bytes([int(match.group(1), 16)])
        
        # Replace all literal \xNN strings with their actual byte values
        b = re.sub(b"\\\\x([0-9a-fA-F]{2})", hex_repl, b)
        
        # Handle standard Go string escapes
        b = b.replace(b"\\n", b"\n").replace(b"\\t", b"\t").replace(b"\\\"", b"\"").replace(b"\\\\", b"\\")
        
        return b.decode("utf-8", errors="replace")
    except Exception as e:
        # Ultimate fallback
        return s.replace('\\\\"', '"').replace('\\\\n', '\n').replace('\\\\t', '\t').replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')

def format_text(text):
    # Clean up ChatML tokens for readability
    text = text.replace('<|im_start|>system', '\n### SYSTEM')
    text = text.replace('<|im_start|>user', '\n### USER')
    text = text.replace('<|im_start|>assistant', '\n### ASSISTANT')
    text = text.replace('<|im_end|>', '\n')
    text = text.replace('<|endoftext|>', '\n')
    
    # Fix common HTML escapes from Ollama
    text = text.replace('\\u003c', '<').replace('\\u003e', '>')
    
    # Clean up excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def main():
    if not os.path.exists(READABLE_LOG):
        with open(READABLE_LOG, 'a') as f_init:
            f_init.write("--- Ollama Readable Log Started ---\n")
        os.chmod(READABLE_LOG, 0o644)

    try:
        f = open(RAW_LOG, "r", errors="replace")
        f.seek(0, os.SEEK_END)
        
        while True:
            line = f.readline()
            if not line:
                if os.path.getsize(RAW_LOG) < f.tell():
                    f.close()
                    time.sleep(1)
                    f = open(RAW_LOG, "r", errors="replace")
                else:
                    time.sleep(0.05)
                continue
            
            # Match the encoded content (the prompt context)
            if "msg=encoded string=" in line:
                match = re.search(r'msg=encoded string="(.*)" ids=', line)
                if match:
                    prompt = decode_go_string(match.group(1))
                    formatted_prompt = format_text(prompt)
                    timestamp = time.strftime("%H:%M:%S")
                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n==================== {timestamp} [GENERATION STARTED] ====================\n")
                        out.write(formatted_prompt + "\n")
                        out.flush()
            
            # Match decoded generated tokens (the assistant's response)
            if "msg=decoded string=" in line:
                match = re.search(r'msg=decoded string=(.*?)\s+from=\[', line)
                if match:
                    val = match.group(1)
                    if val.startswith('"') and val.endswith('"') and len(val) >= 2:
                        token = decode_go_string(val[1:-1])
                    else:
                        token = decode_go_string(val)
                        
                    with open(READABLE_LOG, "a") as out:
                        out.write(token)
                        out.flush()
            
            # Match the completion log (latency)
            if '[GIN]' in line and 'POST' in line and any(x in line for x in ['/api/generate', '/api/chat', '/v1/chat/completions']):
                latency = "N/A"
                latency_match = re.search(r'\|\s*([0-9ms.µsh]+)\s*\|', line)
                if latency_match:
                    latency = latency_match.group(1).strip()
                
                status_match = re.search(r'\|\s*(\d{3})\s*\|', line)
                status = status_match.group(1) if status_match else "???"

                if status == "200":
                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n\n[GENERATION FINISHED: {latency}]\n")
                        out.write(f"{'-'*80}\n")
                        out.flush()

    except Exception as e:
        try:
            with open(READABLE_LOG, "a") as out:
                out.write(f"\nWATCHER FATAL ERROR: {e}\n")
                out.flush()
        except Exception:
            # If we can't write to the readable log either, emit to stderr so
            # systemd's journal captures it.
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
