
import pathlib

class ConfigManager:
    def __init__(self, install_dir, scripts_dir):
        self.install_dir = install_dir
        self.scripts_dir = scripts_dir
        self.config_file = scripts_dir / "ollama.conf"
        
        if (install_dir / "ollama.conf").exists():
            self.config_file = install_dir / "ollama.conf"
        elif not self.config_file.exists() and (install_dir / "scripts" / "ollama.conf").exists():
            self.config_file = install_dir / "scripts" / "ollama.conf"
            
        self.settings = {
            "gpu_tool": "auto",
            "show_gpu": True,
            "show_cpu": True,
            "show_log": True,
            "show_hints": True,
            "ollama_host": "http://127.0.0.1:11435"
        }
        self.load_settings()

    def load_settings(self):
        if self.config_file.exists():
            for raw in self.config_file.read_text().splitlines():
                line = raw.strip()
                if not line or "=" not in line: continue
                try:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"')
                    if key == "OLLAMA_HOST" and val:
                        if not val.startswith("http://") and not val.startswith("https://"):
                            val = "http://" + val
                        self.settings["ollama_host"] = val.rstrip("/")
                    elif key == "GPU_TOOL": self.settings["gpu_tool"] = val
                    elif key in ["SHOW_GPU", "SHOW_CPU", "SHOW_LOG", "SHOW_HINTS"]:
                        self.settings[key.lower()] = val.lower() == "true"
                except ValueError: continue

    def save_setting(self, key, value):
        lines = []
        key_upper = "OLLAMA_HOST" if key == "ollama_host" else key.upper()
        if self.config_file.exists(): lines = self.config_file.read_text().splitlines()
        new_lines = []
        found = False
        for line in lines:
            if line.strip().startswith(key_upper + "="):
                new_lines.append(f"{key_upper}={value}")
                found = True
            else: new_lines.append(line)
        if not found: new_lines.append(f"{key_upper}={value}")
        self.config_file.write_text("\n".join(new_lines) + "\n")
        self.settings[key] = value
