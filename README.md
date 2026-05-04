# watch-ollama

A collection of useful instruments for monitoring, benchmarking, and managing Ollama servers.

## Features

- **Interactive TUI**: `watch-ollama` provides a real-time view of GPU status (via `amd-smi`) and readable Ollama logs.
- **Background Watcher**: `ollama_watcher.py` processes raw Ollama logs into a readable format.
- **Performance Reporting**: `ollama_report.py` and `ollama_stats.py` for analyzing inference performance and hardware usage.
- **Benchmarking**: `benchmark_ollama.py` for testing model performance.
- **GPU Backend Management**: Easily switch between ROCm and Vulkan backends.
- **Server Configuration**: Setup scripts for custom ports and host settings.

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/dst0/watch-ollama.git
   cd watch-ollama
   ```

2. (Optional) Install the background watcher as a systemd service:
   ```bash
   sudo cp systemd/ollama-watcher.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable ollama-watcher
   sudo systemctl start ollama-watcher
   ```

## Usage

### Interactive Monitoring
Run the TUI for real-time monitoring:
```bash
./scripts/watch-ollama
```

### Reporting
Generate a status report:
```bash
python3 scripts/ollama_report.py
```

### Switching GPU Backends
Switch to Vulkan:
```bash
./scripts/switch-gpu.sh vulkan
```
Switch to ROCm:
```bash
./scripts/switch-gpu.sh rocm
```

### Updating Ollama
```bash
./scripts/update-ollama.sh
```

## System Requirements
- Ubuntu 24.10+
- Python 3.x
- Ollama
- `amd-smi` (for AMD GPUs)
- `curses` library (standard in Python)

## Configuration
The scripts assume Ollama is listening on `0.0.0.0:11435`. Use `./scripts/setup-ollama.sh` to apply this configuration to your system.
