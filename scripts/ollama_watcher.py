import re
import os
import time
import json
import sys
import pathlib
from datetime import datetime

# Resolve paths relative to this script so the tool works for any user/install location
_INSTALL_DIR = pathlib.Path(__file__).resolve().parent.parent
RAW_LOG = "/var/log/ollama.log"
READABLE_LOG = str(_INSTALL_DIR / "ollama_readable.log")

def decode_go_string(s):
    try:
        b = s.encode("utf-8")
        def hex_repl(match):
            return bytes([int(match.group(1), 16)])
        b = re.sub(b"\\\\x([0-9a-fA-F]{2})", hex_repl, b)
        b = b.replace(b"\\n", b"\n").replace(b"\\t", b"\t").replace(b"\\\"", b"\"").replace(b"\\\\", b"\\")
        return b.decode("utf-8", errors="replace")
    except Exception:
        return s.replace('\\\\"', '"').replace('\\\\n', '\n').replace('\\\\t', '\t').replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')

def format_text(text):
    text = text.replace('<|im_start|>system', '\n### SYSTEM')
    text = text.replace('<|im_start|>user', '\n### USER')
    text = text.replace('<|im_start|>assistant', '\n### ASSISTANT')
    text = text.replace('<|im_end|>', '\n')
    text = text.replace('<|endoftext|>', '\n')
    text = text.replace('\\u003c', '<').replace('\\u003e', '>')
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_duration(d_str):
    """Parse a Go duration string (e.g. '1.5s', '500ms') into seconds."""
    if not d_str: return 0.0
    if 'ms' in d_str:
        return float(d_str.replace('ms', '')) / 1000.0
    elif 'µs' in d_str or 'us' in d_str:
        return float(re.sub(r'[µu]s', '', d_str)) / 1000000.0
    elif 's' in d_str:
        m = re.match(r'(?:(\d+)m)?([\d.]+)s', d_str)
        if m:
            mins = float(m.group(1) or 0)
            secs = float(m.group(2))
            return mins * 60 + secs
    return 0.0

def main():
    if not os.path.exists(READABLE_LOG):
        try:
            with open(READABLE_LOG, 'a') as f_init:
                f_init.write("--- Ollama Readable Log Started ---\n")
            os.chmod(READABLE_LOG, 0o644)
        except Exception as e:
            print(f"Error initializing readable log at {READABLE_LOG}: {e}", file=sys.stderr)

    try:
        f = open(RAW_LOG, "r", errors="replace")
        f.seek(0, os.SEEK_END)
        
        # State variables for manual speed calculation
        generation_start_time = 0
        prompt_eval_count = 0
        eval_count = 0
        prompt_start_time = 0
        in_generation = False
        
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
            
            # --- START PROMPT ---
            if "msg=encoded string=" in line:
                match = re.search(r'msg=encoded string="(.*)" ids=', line)
                if match:
                    prompt = decode_go_string(match.group(1))
                    formatted_prompt = format_text(prompt)
                    timestamp = time.strftime("%H:%M:%S")
                    
                    # Look for prompt token count if available in the same line or next
                    ids_match = re.search(r'ids=\[(.*?)\]', line)
                    if ids_match:
                        prompt_eval_count = len(ids_match.group(1).split())
                    else:
                        prompt_eval_count = 0
                        
                    prompt_start_time = time.time()
                    eval_count = 0
                    in_generation = True

                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n==================== {timestamp} [GENERATION STARTED] ====================\n")
                        out.write(formatted_prompt + "\n")
                        out.flush()

            # --- PREFILL ---
            if 'level=INFO' in line and 'msg="prefill in progress"' in line:
                match = re.search(r'processed=(\d+)\s+total=(\d+)', line)
                if match:
                    processed, total = match.groups()
                    prompt_eval_count = int(total)
                    if int(processed) > 0 and prompt_start_time > 0:
                        elapsed = time.time() - prompt_start_time
                        pp_speed = int(processed) / elapsed if elapsed > 0 else 0
                        pct = int((int(processed) / int(total)) * 100) if int(total) > 0 else 0
                        with open(READABLE_LOG, "a") as out:
                            out.write(f"[Prefill Progress: {processed}/{total} ({pct}%) - {pp_speed:.1f} PP/s]\n")
                            out.flush()

            # --- TOKENS (GENERATION) ---
            if "msg=decoded string=" in line:
                if eval_count == 0:
                    generation_start_time = time.time() # Mark when first token arrives
                eval_count += 1
                
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
            
            # --- FINISHED / API METRICS ---
            if in_generation and '[GIN]' in line and 'POST' in line and any(x in line for x in ['/api/generate', '/api/chat', '/v1/chat/completions']):
                in_generation = False
                latency = "N/A"
                latency_match = re.search(r'\|\s*([0-9ms.µsh]+)\s*\|', line)
                if latency_match:
                    latency = latency_match.group(1).strip()
                
                status_match = re.search(r'\|\s*(\d{3})\s*\|', line)
                status = status_match.group(1) if status_match else "???"

                if status == "200":
                    # Calculate manual metrics if we have the token counts
                    stats_str = f"[LATENCY: {latency}]"
                    
                    if eval_count > 0 and generation_start_time > 0:
                        gen_duration = time.time() - generation_start_time
                        tps = eval_count / gen_duration if gen_duration > 0 else 0
                        stats_str += f" [GEN: {eval_count} tokens | {tps:.2f} t/s]"
                        
                    if prompt_eval_count > 0 and prompt_start_time > 0 and generation_start_time > 0:
                        pp_duration = generation_start_time - prompt_start_time
                        pps = prompt_eval_count / pp_duration if pp_duration > 0 else 0
                        stats_str += f" [PP: {prompt_eval_count} tokens | {pps:.2f} pp/s]"

                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n\n[GENERATION FINISHED] {stats_str}\n")
                        out.write(f"{'-'*80}\n")
                        out.flush()

    except Exception as e:
        try:
            with open(READABLE_LOG, "a") as out:
                out.write(f"\nWATCHER FATAL ERROR: {e}\n")
                out.flush()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
