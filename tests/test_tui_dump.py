import sys
import pathlib
import threading
import time
import importlib.machinery
from unittest.mock import MagicMock

ROOT = pathlib.Path(__file__).resolve().parents[1]
TUI = importlib.machinery.SourceFileLoader("watch_ollama_tui", str(ROOT / "scripts" / "watch-ollama")).load_module()
TELEMETRY = importlib.machinery.SourceFileLoader("telemetry_utils", str(ROOT / "scripts" / "telemetry_utils.py")).load_module()

def run_test():
    settings = {
        "show_cpu": True,
        "show_gpu": True,
        "gpu_tool": "auto",
        "show_log": True,
        "theme": "default",
        "ollama_host": "http://localhost:11434"
    }
    
    render_event = threading.Event()
    set_error = MagicMock()
    
    t = threading.Thread(target=TELEMETRY.poll_smi, args=(settings, set_error, render_event), daemon=True)
    t.start()
    
    time.sleep(2)
    
    lines, _, _ = TELEMETRY.get_smi_snapshot()
    with open("smi_dump.txt", "w") as f:
        for line in lines:
            f.write(line + "\n")
            
if __name__ == "__main__":
    run_test()