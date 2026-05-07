import sys
import pathlib
import threading
import time
import importlib.machinery

ROOT = pathlib.Path(__file__).resolve().parents[1]
watch_ollama = importlib.machinery.SourceFileLoader("watch_ollama_tui", str(ROOT / "scripts" / "watch-ollama")).load_module()

def run_test():
    watch_ollama.SETTINGS = {
        "show_cpu": True,
        "show_gpu": True,
        "gpu_tool": "auto",
        "show_log": True,
        "theme": "default",
    }
    
    t = threading.Thread(target=watch_ollama.poll_smi, daemon=True)
    t.start()
    
    time.sleep(2)
    
    lines, _, _ = watch_ollama.get_smi_snapshot()
    with open("smi_dump.txt", "w") as f:
        for line in lines:
            f.write(line + "\n")
            
if __name__ == "__main__":
    run_test()