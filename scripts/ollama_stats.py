import re
import json
import sys
import os

LOG_FILE = "/var/log/ollama.log"

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

def parse_size(s):
    if not s: return 0.0
    m = re.search(r'([0-9.]+)\s*([a-zA-Z]+)', s)
    if not m: return 0.0
    val, unit = float(m.group(1)), m.group(2).lower()
    mult = {"gib": 1024**3, "mib": 1024**2, "kib": 1024, "b": 1}.get(unit, 1)
    if mult == 1 and 'gb' in unit: mult = 10**9
    if mult == 1 and 'mb' in unit: mult = 10**6
    return val * mult

def format_size(b):
    return f"{b / 1024**3:.1f}"

def parse_logs():
    # Regex patterns
    config_pattern = re.compile(r'time=.* level=INFO source=types.go:42 msg="inference compute" id=(.*) library=(.*) compute=(.*) name=(.*) total="(.*)" available="(.*)"')

    print("=== OLLAMA SYSTEM STARTUP / CONFIG ===")
    
    try:
        if not os.path.exists(LOG_FILE):
            print(f"Error: {LOG_FILE} not found.")
            return

        with open(LOG_FILE, 'r', errors="replace") as f:
            lines = f.readlines()
            
            last_metrics = None
            for i, line in enumerate(lines):
                # Detect Config/Hardware Info
                config_match = config_pattern.search(line)
                if config_match:
                    gpu_id, lib, compute, name, total_str, avail_str = config_match.groups()
                    total_b = parse_size(total_str)
                    avail_b = parse_size(avail_str)
                    used_b = max(0, total_b - avail_b)
                    print(f"Hardware: {name} ({lib} {compute})")
                    print(f"VRAM: {format_size(used_b)}/{format_size(total_b)}GiB")
                    print("-" * 30)

                # Detect Response Content (TRACE level encoded string)
                if "msg=encoded string=" in line:
                    # Extract the part between encoded string=" and " ids=
                    content_match = re.search(r'msg=encoded string="(.*)" ids=', line)
                    if content_match:
                        raw_content = content_match.group(1)
                        # Unescape double quotes and newlines
                        clean_content = raw_content.replace('\\"', '"').replace('\\n', '\n').replace('\\u003c', '<').replace('\\u003e', '>')
                        
                        print("\n--- CONVERSATION ---")
                        print(clean_content)
                
                # Parse Log Metrics from "request complete"
                if 'msg="request complete"' in line:
                    m_pec = re.search(r'prompt_eval_count=(\d+)', line)
                    m_ped = re.search(r'prompt_eval_duration=([0-9a-zA-Z.µμ]+)', line)
                    m_ec = re.search(r'\beval_count=(\d+)', line)
                    m_ed = re.search(r'\beval_duration=([0-9a-zA-Z.µμ]+)', line)
                    
                    if m_pec and m_ped and m_ec and m_ed:
                        last_metrics = {
                            'pec': int(m_pec.group(1)),
                            'ped': parse_duration(m_ped.group(1)),
                            'ec': int(m_ec.group(1)),
                            'ed': parse_duration(m_ed.group(1))
                        }

                # Detect Performance Stats (from GIN log or surrounding DEBUG logs)
                if "[GIN]" in line and any(x in line for x in ["/api/generate", "/api/chat", "/v1/chat/completions"]):
                    parts = line.split("|")
                    if len(parts) > 2:
                        duration = parts[2].strip()
                        print(f"Total Latency: {duration}")
                        if last_metrics:
                            pps = last_metrics['pec'] / last_metrics['ped'] if last_metrics['ped'] > 0 else 0
                            tps = last_metrics['ec'] / last_metrics['ed'] if last_metrics['ed'] > 0 else 0
                            print(f"Prompt: {last_metrics['pec']} tokens ({pps:.2f} tokens/s)")
                            print(f"Generation: {last_metrics['ec']} tokens ({tps:.2f} tokens/s)")
                            last_metrics = None
                        print("=" * 40)

    except Exception as e:
        print(f"Error parsing logs: {e}")

if __name__ == "__main__":
    parse_logs()
