import re
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

def get_report():
    if not os.path.exists(LOG_FILE):
        return "Log file not found."

    with open(LOG_FILE, "r", errors="replace") as f:
        content = f.read()

    print("=== OLLAMA SYSTEM STATUS & CONFIG ===")
    
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

    # 1. Hardware Detection
    gpu_matches = re.finditer(r'msg="inference compute".*name=(.*) libdirs=.*total="(.*)" available="(.*)"', content)
    for m in gpu_matches:
        t_str, a_str = m.group(2), m.group(3)
        total_b, avail_b = parse_size(t_str), parse_size(a_str)
        used_b = max(0, total_b - avail_b)
        print(f"GPU: {m.group(1).strip()} | VRAM: {format_size(used_b)}/{format_size(total_b)}GiB")
    
    # 2. Model Loading
    model_match = re.search(r'msg="loaded runners" count=(\d+)', content)
    if model_match:
        print(f"Active Model Runners: {model_match.group(1)}")

    offload_match = re.search(r'msg="offloaded (\d+)/(\d+) layers to GPU"', content)
    if offload_match:
        print(f"GPU Offloading: {offload_match.group(1)} / {offload_match.group(2)} layers")

    print("\n" + "="*60 + "\n")

    # 3. Conversations (Searching for TRACE output and GIN performance)
    # We look for the most recent conversation first
    sections = content.split("msg=encoded string=")
    
    # Skip the first split as it's the preamble
    for section in sections[1:]:
        # Extract content
        content_end = section.find('" ids="')
        if content_end == -1: continue
        
        raw_text = section[:content_end]
        clean_text = raw_text.replace('\\"', '"').replace('\\n', '\n').replace('\\u003c', '<').replace('\\u003e', '>')
        
        # Look for the GIN log immediately following this content in the log file
        latency = "N/A"
        latency_match = re.search(r'\[GIN\].*\| 200 \| \s*(.*) \|', section)
        if latency_match:
            latency = latency_match.group(1).strip()

        # Look for metrics in "request complete"
        metrics_str = ""
        m_pec = re.search(r'prompt_eval_count=(\d+)', section)
        m_ped = re.search(r'prompt_eval_duration=([0-9a-zA-Z.µμ]+)', section)
        m_ec = re.search(r'\beval_count=(\d+)', section)
        m_ed = re.search(r'\beval_duration=([0-9a-zA-Z.µμ]+)', section)
        
        if m_pec and m_ped and m_ec and m_ed:
            pec = int(m_pec.group(1))
            ped = parse_duration(m_ped.group(1))
            ec = int(m_ec.group(1))
            ed = parse_duration(m_ed.group(1))
            pps = pec / ped if ped > 0 else 0
            tps = ec / ed if ed > 0 else 0
            metrics_str = f" | PP: {pps:.1f} t/s | GEN: {tps:.1f} t/s"

        print(f"--- CONVERSATION (Latency: {latency}{metrics_str}) ---")
        print(clean_text)
        print("-" * 60)

if __name__ == "__main__":
    get_report()
