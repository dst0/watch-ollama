import re
import os

LOG_FILE = "/var/log/ollama.log"

def get_report():
    if not os.path.exists(LOG_FILE):
        return "Log file not found."

    with open(LOG_FILE, "r", errors="replace") as f:
        content = f.read()

    print("=== OLLAMA SYSTEM STATUS & CONFIG ===")
    
    # 1. Hardware Detection
    gpu_matches = re.finditer(r'msg="inference compute".*name=(.*) libdirs=.*total="(.*)" available="(.*)"', content)
    for m in gpu_matches:
        print(f"GPU: {m.group(1).strip()} | Memory: {m.group(3)} / {m.group(2)}")
    
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
        # The GIN log usually appears within the next few lines.
        latency = "N/A"
        latency_match = re.search(r'\[GIN\].*\| 200 \| \s*(.*) \|', section)
        if latency_match:
            latency = latency_match.group(1).strip()

        print(f"--- CONVERSATION (Latency: {latency}) ---")
        print(clean_text)
        print("-" * 60)

if __name__ == "__main__":
    get_report()
