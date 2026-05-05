# watch-ollama

A comprehensive collection of monitoring, benchmarking, and management tools for Ollama servers.

## Features

- **Interactive TUI**: `watch-ollama` provides real-time GPU/SMI monitoring and readable logs.
  - **Integrated Indicators**: 🌡️ symbols with high-compatibility background color indicators for intuitive temperature monitoring.
  - **Hottest-Sensor Status**: Global system health (title and status bar) dynamically reflects the highest temperature across CPU, GPU, and all system sensors.
  - **Dynamic Title**: Synchronized color-coded status blocks (🟦, 🟩, 🟨, 🟧, 🟥) in the terminal title bar.
  - **Official Metrics**: Reporting and TUI use official Ollama log-based token metrics (`prompt_eval_count`, `eval_count`) for precise speed and performance measurement.
  - **Smart Follow Mode**: Intelligent log tailing with dynamic `F:Pause` / `F:Follow` feedback.
- **Background Watcher**: `ollama_watcher.py` logs processing service with systemd integration.
- **Reporting & Stats**: `ollama_report.py` and `ollama_stats.py` for inference and hardware analysis.
- **Utility Scripts**:
  - `switch-gpu`: Toggle between ROCm and Vulkan backends.
  - `update-ollama`: Automated Ollama update process.
  - `setup-ollama`: Interactive configuration helper for setting ports/hosts.
  - `make-modelfile`: Interactive generator for Ollama Modelfiles.

## Visual Preview

`watch-ollama` provides a rich, color-coded terminal interface for monitoring your local LLM stack:

```text
=== OLLAMA  parallel:1  tool:amd-smi ===
  qwen3.6-35b (22.4 GB | 100% GPU / 0% CPU)
    └ ctx:32768 | 35B | IQ3_S

CPU: 14% 48°C | RAM: 12/64G | GPU: 54°C | SSD: 38°C

--------------------------------------------------------------------------------
14:20:05 [NEW PROMPT - GENERATION STARTED]
### USER
Explain the transformer architecture in one sentence.

### ASSISTANT
The transformer is a neural network architecture that relies on self-attention 
mechanisms to process entire sequences of data in parallel, capturing long-range 
dependencies without using recurrent connections.

[GENERATION FINISHED] [LATENCY: 850ms] [GEN: 45 tokens | 52.9 t/s] [PP: 12 tokens | 180.2 pp/s]
--------------------------------------------------------------------------------
[UP/DOWN] Scroll | [F] Follow:ON | [G] GPU:ON | [C] CPU:ON | [L] Log:ON | [Q] Quit
```

## Screenshots & Video

### Screenshot
<img width="1440" height="903" alt="Screenshot 2026-05-06 at 9 23 54 AM" src="https://github.com/user-attachments/assets/00ced232-27f3-4b85-9a18-b72964789ddd" />


### Video Demo
https://github.com/user-attachments/assets/92d20147-c692-4d68-bb0a-2fbf9f5f47b2


## Repository Structure
- **`scripts/`**: All executable tools and utility scripts.
- **`systemd/`**: Systemd unit files for background services.
- **`VERSION`**: Tracks the project release version.
- **`install.sh`**: The unified universal installer.
- **`uninstall.sh`**: Removes all installed components.

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
   *   Every system change is logged with a `[CHANGE]` tag — both to the console and to `~/.ollama-watch-tool/install.log`.
   *   Named shell aliases (`watch-ollama`, `setup-ollama`, `switch-gpu`, `update-ollama`, `ollama-report`, `ollama-stats`, `unwatch-ollama`) are written to the rc file for your current shell (bash → `.bashrc`, zsh → `.zshrc`, fish → `config.fish`, ksh → `.kshrc`). Run `source <your-rc-file>` or open a new terminal to activate them.

## Uninstallation

```bash
unwatch-ollama
# Or, without the alias:
./uninstall.sh
```
The uninstaller:
- Removes all shell aliases (and any legacy PATH entry) from your rc file.
- Stops, disables, and removes the `ollama-watcher` systemd service.
- Removes the scripts directory (`~/.ollama-watch-tool/scripts/`).
- Optionally removes the entire install directory (including logs).
- Logs every change with a `[CHANGE]` tag to the console **and** to a timestamped file in `/tmp` (e.g. `/tmp/watch-ollama-uninstall-20260504-150000.log`).

## Usage

### Interactive Monitoring
Run the TUI for real-time monitoring:
```bash
watch-ollama
```

### Generating Modelfiles
Use the interactive tool to create custom Modelfiles from your GGUF models:
```bash
make-modelfile
# Or, if alias not set:
python3 ~/.ollama-watch-tool/scripts/make-modelfile.py
```

### Switching GPU Backends
```bash
switch-gpu [vulkan|rocm|status]
```

### Server Configuration
Configure the Ollama bind address and port interactively (defaults: `0.0.0.0:11435`):
```bash
setup-ollama
```
Or pass values directly:
```bash
setup-ollama 0.0.0.0 11435
```
This writes an `ollama.conf` file alongside the scripts so that `watch-ollama` automatically connects to the correct address.

> **Note on port**: Ollama's built-in default is `11434`. This project defaults to `11435` to allow running a custom instance alongside a system-managed one. Adjust as needed.

## System Requirements
- **OS**: Ubuntu Linux (or systemd-based Linux distributions)
- Python 3.x
- Ollama
- `amd-smi` (for AMD GPU monitoring)
- `systemd` (required for background watcher)

## Better Together

For full token-per-second metrics in logs (the `prompt_eval_count`, `eval_count`, and timing fields that power the `[GEN: ... t/s]` and `[PP: ... pp/s]` display), use this project alongside the forked Ollama build that emits those fields:

👉 **[dst0/ollama-logs-with-tokens](https://github.com/dst0/ollama-logs-with-tokens)** — Ollama fork that adds token counts and timing to inference log lines.

Without it, `watch-ollama` still works but token-speed lines won't appear in the TUI or reports.

## Disclaimer
**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**
