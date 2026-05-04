import re
import json
import sys

LOG_FILE = "/var/log/ollama.log"

def parse_logs():
    current_request = None
    
    # Regex patterns
    start_pattern = re.compile(r'time=.* level=INFO source=routes.go:.* msg="vram-based default context"')
    config_pattern = re.compile(r'time=.* level=INFO source=types.go:42 msg="inference compute" id=(.*) library=(.*) compute=(.*) name=(.*) total="(.*)" available="(.*)"')
    request_pattern = re.compile(r'level=TRACE source=bytepairencoding.go:287 msg=encoded string=".*" ids="\[(.*)\]"')
    gin_pattern = re.compile(r'\[GIN\].*\| 200 \| \s*(.*) \|.*POST\s*"/api/generate"')

    print("=== OLLAMA SYSTEM STARTUP / CONFIG ===")
    
    try:
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            
            for i, line in enumerate(lines):
                # Detect Config/Hardware Info
                config_match = config_pattern.search(line)
                if config_match:
                    gpu_id, lib, compute, name, total, avail = config_match.groups()
                    print(f"Hardware: {name} ({lib} {compute})")
                    print(f"VRAM: {avail} / {total}")
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
                        
                # Detect Performance Stats (from GIN log or surrounding DEBUG logs)
                if "/api/generate" in line and "[GIN]" in line:
                    parts = line.split("|")
                    if len(parts) > 2:
                        duration = parts[2].strip()
                        print(f"Total Latency: {duration}")
                        print("=" * 40)

    except FileNotFoundError:
        print(f"Error: {LOG_FILE} not found.")
    except Exception as e:
        print(f"Error parsing logs: {e}")

if __name__ == "__main__":
    parse_logs()
