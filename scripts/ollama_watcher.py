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

SPECIAL_TOKENS_RE = re.compile(r"<\|(?:im_start|im_end|endoftext)\|>")
BARE_IM_START_RE = re.compile(r"<\|im_start\|>(?!system|user|assistant)")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

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
    text = text.replace('\\u003c', '<').replace('\\u003e', '>')
    text = text.replace('\r', '')
    text = text.replace('<|im_start|>system', '\n### SYSTEM')
    text = text.replace('<|im_start|>user', '\n### USER')
    text = text.replace('<|im_start|>assistant', '\n### ASSISTANT')
    text = text.replace('<|im_end|>', '\n')
    text = text.replace('<|endoftext|>', '\n')
    text = SPECIAL_TOKENS_RE.sub('', text)
    text = BARE_IM_START_RE.sub('', text)
    text = CONTROL_CHARS_RE.sub('', text)
    text = re.sub(r'\n(### (?:SYSTEM|USER|ASSISTANT))(?=\S)', r'\n\1\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip("\n")

def sanitize_decoded_text(text):
    text = text.replace('\\u003c', '<').replace('\\u003e', '>')
    text = text.replace('\r', '')
    text = text.replace('<|im_end|>', '').replace('<|endoftext|>', '')
    text = BARE_IM_START_RE.sub('', text)
    return CONTROL_CHARS_RE.sub('', text)

def prompt_ends_with_assistant_marker(formatted_prompt):
    lines = [line.strip() for line in formatted_prompt.splitlines() if line.strip()]
    return bool(lines and lines[-1] in {"### ASSISTANT", "ASSISTANT:"})

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
        last_prompt_raw = ""
        
        # Log-based metrics
        log_metrics = {
            'prompt_eval_count': 0,
            'prompt_eval_duration': 0.0,
            'eval_count': 0,
            'eval_duration': 0.0
        }
        
        while True:
            line = f.readline()
            if not line:
                if os.path.getsize(RAW_LOG) < f.tell():
                    f.close()
                    time.sleep(1)
                    f = open(RAW_LOG, "r", errors="replace")
                else:
                    time.sleep(0.25)
                continue
            
            # --- PARSE LOG METRICS ---
            if 'msg="request complete"' in line:
                m_pec = re.search(r'prompt_eval_count=(\d+)', line)
                m_ped = re.search(r'prompt_eval_duration=([0-9a-zA-Z.µμ]+)', line)
                m_ec = re.search(r'\beval_count=(\d+)', line)
                m_ed = re.search(r'\beval_duration=([0-9a-zA-Z.µμ]+)', line)
                
                if m_pec: log_metrics['prompt_eval_count'] = int(m_pec.group(1))
                if m_ped: log_metrics['prompt_eval_duration'] = parse_duration(m_ped.group(1))
                if m_ec: log_metrics['eval_count'] = int(m_ec.group(1))
                if m_ed: log_metrics['eval_duration'] = parse_duration(m_ed.group(1))

            # --- START PROMPT ---
            if "msg=encoded string=" in line:
                match = re.search(r'msg=encoded string="(.*)" ids=', line)
                if match:
                    raw_prompt = match.group(1)
                    # If this is exactly the same raw prompt as the one we just started,
                    # it's likely just a duplicate log entry from Ollama's pipeline.
                    if in_generation and raw_prompt == last_prompt_raw:
                        continue
                    
                    # If we were already in generation, it means we missed the finish signal
                    # for the previous prompt. Force close it now.
                    if in_generation:
                        with open(READABLE_LOG, "a") as out:
                            out.write(f"\n\n[GENERATION INTERRUPTED BY NEW PROMPT]\n")
                            out.write(f"{'-'*80}\n")
                            out.flush()
                        in_generation = False

                    last_prompt_raw = raw_prompt
                    
                    # Reset log metrics for new prompt
                    log_metrics = {k: 0 for k in log_metrics}
                    log_metrics['prompt_eval_duration'] = 0.0
                    log_metrics['eval_duration'] = 0.0

                    prompt = decode_go_string(raw_prompt)
                    formatted_prompt = format_text(prompt)
                    timestamp = time.strftime("%H:%M:%S")
                    
                    # Look for prompt token count if available in the same line or next
                    ids_match = re.search(r'ids="?\[(.*?)"?\]', line)
                    if ids_match:
                        prompt_eval_count = len(ids_match.group(1).split())
                    else:
                        prompt_eval_count = 0
                    
                    # Distinguish automated follow-up suggestion requests from Open WebUI
                    if "Suggest 3-5 relevant follow-up questions" in formatted_prompt:
                        header = f"\n\n\n{'='*100}\n{timestamp} [FOLLOW-UP SUGGESTIONS]\n{'='*100}\n\n"
                    else:
                        header = f"\n\n\n{'='*100}\n{timestamp} [NEW PROMPT - GENERATION STARTED]\n{'='*100}\n\n"

                    prompt_start_time = time.time()
                    eval_count = 0
                    in_generation = True
                    needs_assistant_marker = not prompt_ends_with_assistant_marker(formatted_prompt)

                    with open(READABLE_LOG, "a") as out:
                        out.write(header)
                        out.write(formatted_prompt + "\n")
                        if needs_assistant_marker:
                            out.write("### ASSISTANT\n")
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
                    token = sanitize_decoded_text(token)
                        
                    with open(READABLE_LOG, "a") as out:
                        out.write(token)
                        out.flush()
            
            # --- STOPPED / ERROR ---
            if in_generation and ('msg="llama runner terminated"' in line or 'msg="context cancelled"' in line or 'msg="context for request finished"' in line):
                in_generation = False
                timestamp = time.strftime("%H:%M:%S")
                with open(READABLE_LOG, "a") as out:
                    out.write(f"\n\n[GENERATION STOPPED] {timestamp} - {line.strip()}\n")
                    out.write(f"{'-'*80}\n")
                    out.flush()

            # --- FINISHED / API METRICS ---
            if in_generation and '[GIN]' in line and 'POST' in line and any(x in line for x in ['/api/generate', '/api/chat', '/v1/chat/completions', '/v1/completions', '/v1/responses']):
                in_generation = False
                # Add a brief cooldown to prevent immediate triggers from rapid requests
                time.sleep(0.2)
                
                latency = "N/A"
                latency_match = re.search(r'\|\s*([0-9ms.µsh]+)\s*\|', line)
                if latency_match:
                    latency = latency_match.group(1).strip()
                
                status_match = re.search(r'\|\s*(\d{3})\s*\|', line)
                status = status_match.group(1) if status_match else "???"

                if status.startswith('2'):
                    stats_str = f"[LATENCY: {latency}]"
                    
                    # Use log-based metrics if available, otherwise fall back to manual
                    if log_metrics['eval_count'] > 0 and log_metrics['eval_duration'] > 0:
                        eval_c = log_metrics['eval_count']
                        tps = eval_c / log_metrics['eval_duration']
                        stats_str += f" [GEN: {eval_c} tokens | {tps:.2f} t/s]"
                    elif eval_count > 0 and generation_start_time > 0:
                        gen_duration = time.time() - generation_start_time
                        tps = eval_count / gen_duration if gen_duration > 0 else 0
                        stats_str += f" [GEN: {eval_count} tokens | {tps:.2f} t/s]"
                        
                    if log_metrics['prompt_eval_count'] > 0 and log_metrics['prompt_eval_duration'] > 0:
                        prompt_c = log_metrics['prompt_eval_count']
                        pps = prompt_c / log_metrics['prompt_eval_duration']
                        stats_str += f" [PP: {prompt_c} tokens | {pps:.2f} pp/s]"
                    elif prompt_eval_count > 0 and prompt_start_time > 0 and generation_start_time > 0:
                        pp_duration = generation_start_time - prompt_start_time
                        pps = prompt_eval_count / pp_duration if pp_duration > 0 else 0
                        stats_str += f" [PP: {prompt_eval_count} tokens | {pps:.2f} pp/s]"

                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n\n[GENERATION FINISHED] {stats_str}\n")
                        out.write(f"{'-'*80}\n")
                        out.flush()
                else:
                    # Log non-2xx status as a stop
                    with open(READABLE_LOG, "a") as out:
                        out.write(f"\n\n[GENERATION STOPPED] {timestamp} - Status: {status}\n")
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
