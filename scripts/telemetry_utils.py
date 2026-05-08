
import subprocess
import time
import json
import os
import pathlib
import urllib.request
import threading

_model_params_cache = {}
MODEL_PARAMS_CACHE_TTL = 30.0

# Global state for telemetry (to be updated by poll_smi)
smi_text = ["Loading GPU status..."]
latest_cpu_temp = 0.0
smi_version = 0
smi_lock = threading.Lock()
smi_ready = threading.Event()
smi_poll_trigger = threading.Event()

GPU_TOOLS = ["auto", "nvidia-smi", "amd-smi", "rocm-smi", "none"]

def get_cpu_usage():
    try:
        with open('/proc/stat', 'r') as f:
            line1 = f.readline()
        time.sleep(0.05)
        with open('/proc/stat', 'r') as f:
            line2 = f.readline()
        
        def parse_stat(line):
            parts = line.split()
            idle = float(parts[4])
            total = sum(float(x) for x in parts[1:])
            return idle, total
        
        idle1, total1 = parse_stat(line1)
        idle2, total2 = parse_stat(line2)
        diff_idle = idle2 - idle1
        diff_total = total2 - total1
        if diff_total == 0: return 0.0
        return max(0.0, min(100.0, (1.0 - diff_idle / diff_total) * 100.0))
    except Exception: return 0.0

def get_cpu_freq():
    try:
        freq_files = list(pathlib.Path('/sys/devices/system/cpu').glob('cpu*/cpufreq/scaling_cur_freq'))
        if not freq_files: return 0.0
        total_freq = 0
        count = 0
        for fpath in freq_files:
            try:
                total_freq += int(fpath.read_text().strip())
                count += 1
            except (IOError, ValueError): continue
        if count > 0: return (total_freq / count) / 1000.0
    except Exception: pass
    return 0.0

def get_ram_usage():
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
        mem_info = {}
        for line in lines:
            parts = line.split(':')
            if len(parts) == 2:
                mem_info[parts[0].strip()] = int(parts[1].strip().split()[0])
        total = mem_info.get('MemTotal', 0)
        available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0))
        if total > 0:
            total_gb = total / (1024 * 1024)
            available_gb = available / (1024 * 1024)
            used_gb = total_gb - available_gb
            return total_gb, available_gb, used_gb
    except Exception: pass
    return 0.0, 0.0, 0.0

def get_cpu_temp():
    try:
        paths = [
            '/sys/class/thermal/thermal_zone0/temp',
            '/sys/class/thermal/thermal_zone1/temp',
            '/sys/class/hwmon/hwmon0/temp1_input',
            '/sys/class/hwmon/hwmon1/temp1_input',
        ]
        for p in paths:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    return float(f.read().strip()) / 1000.0
    except Exception: pass
    return 0.0

def get_system_temps():
    temps = []
    temp_dict = {}
    max_sys_temp = 0.0
    try:
        output = subprocess.check_output(["sensors", "-j"], text=True, errors="replace", stderr=subprocess.DEVNULL)
        data = json.loads(output)
        for adapter, sensors_dict in data.items():
            if adapter == "Adapter": continue
            for sensor_name, readings in sensors_dict.items():
                if isinstance(readings, dict):
                    for k, v in readings.items():
                        if k.endswith("_input") and "temp" in k:
                            temp_val = float(v)
                            max_sys_temp = max(max_sys_temp, temp_val)
                            short_adapter = adapter.split('-')[0].upper()
                            replacements = {"AMDGPU": "GPU", "K10TEMP": "K10", "CORETEMP": "CPU", "NVME": "SSD", "ACPI": "SYS", "R8169": "NET"}
                            for old, new in replacements.items():
                                short_adapter = short_adapter.replace(old, new)
                            if short_adapter in ["CPU", "K10", "GPU", "SYS", "SYSTZ", "ACPI", "ACPITZ"]: continue
                            label = short_adapter.split('_')[0].split('-')[0]
                            temp_dict[label] = max(temp_dict.get(label, 0.0), temp_val)
    except Exception: pass
    for label in sorted(temp_dict.keys()):
        temps.append(f"{label}:{temp_dict[label]:.0f}°C")
    if max_sys_temp == 0.0: max_sys_temp = get_cpu_temp()
    return max_sys_temp, temps

def detect_gpu_tool(settings_gpu_tool):
    if settings_gpu_tool != "auto":
        return settings_gpu_tool
    for tool in ["nvidia-smi", "amd-smi", "rocm-smi"]:
        if subprocess.call(["which", tool], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return tool
    return "none"

def get_ollama_num_parallel():
    val = os.environ.get("OLLAMA_NUM_PARALLEL")
    if val: return val
    try:
        pid_out = subprocess.check_output(['pgrep', '-x', 'ollama'], text=True, timeout=2, stderr=subprocess.DEVNULL).strip()
        if pid_out:
            pid = pid_out.splitlines()[0].strip()
            with open(f'/proc/{pid}/environ', 'rb') as f:
                env_data = f.read()
            for entry in env_data.split(b'\x00'):
                if entry.startswith(b'OLLAMA_NUM_PARALLEL='):
                    return entry.split(b'=', 1)[1].decode()
    except Exception: pass
    return "auto"

def parse_ollama_ps():
    result = {}
    try:
        ps_output = subprocess.check_output(['ollama', 'ps'], text=True, errors="replace", timeout=3, stderr=subprocess.DEVNULL)
        ps_lines = ps_output.strip().splitlines()
        if len(ps_lines) < 2: return result
        header_line = ps_lines[0].upper()
        proc_col = header_line.find("PROCESSOR")
        until_col = header_line.find("UNTIL")
        if proc_col < 0: return result
        for row in ps_lines[1:]:
            if not row.strip(): continue
            name_field = row[:proc_col].strip()
            name = name_field.split()[0] if name_field else ""
            processor = row[proc_col:until_col].strip() if until_col > proc_col else row[proc_col:].strip()
            if name: result[name] = processor
    except Exception: pass
    return result

def _get_model_params(model_name, ollama_api_url):
    now = time.time()
    cached = _model_params_cache.get(model_name)
    if cached and now - cached[0] < MODEL_PARAMS_CACHE_TTL: return cached[1]
    params_of_interest = ["temperature", "num_batch", "num_gqa", "top_k", "top_p", "tfs_z"]
    try:
        req_body = json.dumps({"name": model_name}).encode()
        req = urllib.request.Request(f"{ollama_api_url}/api/show", data=req_body, method="POST")
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=1) as response:
            data = json.loads(response.read().decode())
            param_str = data.get("parameters", "")
            if not param_str:
                _model_params_cache[model_name] = (now, "")
                return ""
            params = {}
            for line in param_str.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2: params[parts[0]] = parts[1]
            param_list = []
            for p in params_of_interest:
                if p in params:
                    short_name = p.replace("temperature", "temp").replace("num_", "")
                    param_list.append(f"{short_name}:{params[p]}")
            result = (" | " + " ".join(param_list)) if param_list else ""
            _model_params_cache[model_name] = (now, result)
            return result
    except Exception:
        _model_params_cache[model_name] = (now, "")
        return ""

def set_smi_text(lines, cpu_temp=0.0):
    global smi_text, latest_cpu_temp, smi_version
    with smi_lock:
        smi_text = lines
        latest_cpu_temp = cpu_temp
        smi_version += 1
    smi_ready.set()

def get_smi_snapshot():
    with smi_lock:
        return list(smi_text), latest_cpu_temp, smi_version

def poll_smi(settings, set_error_func, render_event):
    while True:
        tool = detect_gpu_tool(settings["gpu_tool"])
        hw_lines = []
        if tool != "none":
            try:
                output = subprocess.check_output([tool], text=True, errors="replace", stderr=subprocess.STDOUT)
                if "Elevated permissions" in output or "Permission denied" in output:
                    try:
                        output = subprocess.check_output(["sudo", "-n", tool], text=True, errors="replace", stderr=subprocess.STDOUT)
                    except Exception:
                        if "Elevated permissions" in output:
                            output += "\n\033[93mTip: Run 'sudo usermod -a -G render,video $USER' and restart session to see process names.\033[0m"
                hw_lines = output.splitlines()
            except Exception: hw_lines = [f"\033[31m({tool} unavailable)\033[0m"]
        else: hw_lines = ["\033[90m(no GPU tool detected)\033[0m"]

        cpu_load = get_cpu_usage()
        cpu_temp, sys_temps = get_system_temps()
        ram_total, ram_avail, ram_used = get_ram_usage()

        if tool == "nvidia-smi":
            try:
                nv_out = subprocess.check_output(["nvidia-smi", "--query-gpu=index,temperature.gpu", "--format=csv,noheader"], text=True, errors="replace", stderr=subprocess.DEVNULL)
                nv_entries = []
                for nv_line in nv_out.strip().splitlines():
                    parts = [p.strip() for p in nv_line.split(",")]
                    if len(parts) >= 2 and parts[1].lstrip("-").isdigit():
                        nv_entries.append((int(parts[0]), float(parts[1])))
                multi_gpu = len(nv_entries) > 1
                for idx, temp in nv_entries:
                    label = f"GPU{idx}" if multi_gpu else "GPU"
                    sys_temps.append(f"{label}:{temp:.0f}°C")
                    cpu_temp = max(cpu_temp, temp)
            except Exception: pass
        
        num_parallel = get_ollama_num_parallel()
        ps_info = parse_ollama_ps()
        model_lines = []
        try:
            req = urllib.request.Request(f"{settings['ollama_host']}/api/ps", method="GET")
            with urllib.request.urlopen(req, timeout=1) as response:
                data = json.loads(response.read().decode())
                models = data.get("models", [])
                if models:
                    current_model_names = {m.get("name", "") for m in models}
                    stale = [k for k in _model_params_cache if k not in current_model_names]
                    for k in stale: del _model_params_cache[k]
                    for m in models:
                        name = m.get("name", "unknown")
                        ctx = m.get("context_length", 0)
                        size = m.get("size", 0)
                        size_vram = m.get("size_vram", 0)
                        processor = ps_info.get(name, "")
                        if not processor and size > 0:
                            gpu_pct = int(round(size_vram / size * 100))
                            processor = f"{gpu_pct}% GPU / {100 - gpu_pct}% CPU"
                        size_str = f"{size / (1024**3):.1f} GB" if size > 0 else "? GB"
                        param_details_str = _get_model_params(name, settings['ollama_host'])
                        model_lines.append(f"  \033[1;32m{name}\033[0m ({size_str} | {processor or 'unknown'})")
                        model_lines.append(f"    \033[34m└\033[0m ctx:{ctx}{param_details_str}")
                else: model_lines = ["  \033[90m(no active models)\033[0m"]
                set_error_func("ollama", None)
        except Exception:
            model_lines = ["  \033[31m(could not reach Ollama API)\033[0m"]
            set_error_func("ollama", "Ollama is not reachable. Run 'ollama serve' to start it.")

        full_smi_lines = [f"\033[1;36m=== OLLAMA  parallel:{num_parallel}  tool:{tool} ===\033[0m"]
        full_smi_lines.extend(model_lines)
        if settings["show_cpu"]:
            full_smi_lines.append("")
            freq_str = f" {get_cpu_freq()/1000:.1f}GHz" if get_cpu_freq() >= 1000 else f" {get_cpu_freq():.0f}MHz" if get_cpu_freq() > 0 else ""
            cpu_line = f"CPU:{cpu_load:2.0f}%{freq_str} {cpu_temp:2.0f}°C"
            if ram_total > 0: cpu_line += f" | RAM:{ram_used:.1f}/{ram_total:.1f}GiB"
            if sys_temps: cpu_line += " | " + " ".join(sys_temps)
            full_smi_lines.append(cpu_line)
        if settings["show_gpu"]:
            full_smi_lines.append("")
            full_smi_lines.extend(hw_lines)
        set_smi_text(full_smi_lines, cpu_temp=cpu_temp)
        render_event.set()
        smi_poll_trigger.wait(timeout=2.0)
        smi_poll_trigger.clear()
