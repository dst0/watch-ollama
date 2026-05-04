# watch-ollama

A comprehensive collection of monitoring, benchmarking, and management tools for Ollama servers.

## Features

- **Interactive TUI**: `watch-ollama` provides real-time GPU/SMI monitoring and readable logs.
- **Background Watcher**: `ollama_watcher.py` logs processing service with systemd integration.
- **Reporting & Stats**: `ollama_report.py` and `ollama_stats.py` for inference and hardware analysis.
- **Utility Scripts**:
  - `switch-gpu.sh`: Toggle between ROCm and Vulkan backends.
  - `update-ollama.sh`: Automated Ollama update process.
  - `setup-ollama.sh`: Configuration helper for setting ports/hosts.

## Repository Structure
- **`scripts/`**: All executable tools and utility scripts.
- **`systemd/`**: Systemd unit files for background services.
- **`VERSION`**: Tracks the project release version.
- **`install.sh`**: The unified universal installer.

## Installation

1. **Clone the repository**:
   ```bash
   mkdir -p ~/dev/ollama-tools
   cd ~/dev/ollama-tools
   git clone https://github.com/dst0/watch-ollama.git .
   ```
2. **Versioning**: Verify the `VERSION` file in the repository root. If making modifications, increment this version.
3. **Run the installer**:
   ```bash
   ./install.sh
   ```
   *   The installer will prompt you for a clean installation if an existing one is detected. 
   *   **Safe Reinstall**: Configuration files (`*.conf`) are preserved during clean installs.
   *   Logs are recorded to `/var/log/watch-ollama-install.log`.

## Usage

### Interactive Monitoring
Run the TUI for real-time monitoring:
```bash
~/.ollama-watch-tool/scripts/watch-ollama
```

### Switching GPU Backends
```bash
~/.ollama-watch-tool/scripts/switch-gpu.sh [vulkan|rocm|status]
```

### Server Configuration
To set your Ollama host and port (default 11435):
```bash
~/.ollama-watch-tool/scripts/setup-ollama.sh
```

## System Requirements
- **OS**: Ubuntu Linux (or systemd-based Linux distributions)
- Python 3.x
- Ollama
- `amd-smi` (for AMD GPU monitoring)
- `systemd` (required for background watcher)

## Disclaimer
**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**
