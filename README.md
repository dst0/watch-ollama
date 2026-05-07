# watch-ollama

A comprehensive collection of monitoring, benchmarking, and management tools for Ollama servers.

## Features

- **Interactive TUI**: `watch-ollama` provides real-time GPU/SMI monitoring and readable logs.
  - **Multi-vendor GPU support**: Auto-detects `nvidia-smi` (NVIDIA), `amd-smi`, or `rocm-smi` (AMD). Press `T` to cycle through tools at runtime.
  - **Integrated Indicators**: 🌡️ symbols with high-compatibility background color indicators for intuitive temperature monitoring.
  - **Hottest-Sensor Status**: Global system health (title and status bar) dynamically reflects the highest temperature across CPU, GPU, and all system sensors.
  - **Dynamic Title**: Synchronized color-coded status blocks (🟦, 🟩, 🟨, 🟧, 🟥) in the terminal title bar.
  - **Official Metrics**: Reporting and TUI use official Ollama log-based token metrics (`prompt_eval_count`, `eval_count`) for precise speed and performance measurement.
  - **Smart Follow Mode**: Intelligent log tailing with dynamic `F:Pause` / `F:Follow` feedback.
  - **Toggleable Panels**: GPU, CPU (load, frequency, temp) / RAM, log, and hint bar can each be toggled on/off with a single keypress.
- **Background Watcher**: `ollama_watcher.py` logs processing service with systemd integration.
- **Reporting & Stats**: `ollama_report.py` and `ollama_stats.py` for inference and hardware analysis.
- **Utility Scripts**:
  - `switch-gpu`: Toggle between ROCm and Vulkan backends.
  - `update-ollama`: Automated Ollama update process.
  - `setup-ollama`: Interactive configuration helper for setting ports/hosts.
  - `make-modelfile`: Interactive generator for Ollama Modelfiles.

## Visual Preview

`watch-ollama` provides a rich, color-coded terminal interface for monitoring your local LLM stack:

AMD GPU example (`tool:amd-smi`):
```text
=== OLLAMA  parallel:1  tool:amd-smi ===
  qwen3.6-35b (22.4 GB | 100% GPU / 0% CPU)
    └ ctx:32768 | 35B | IQ3_S

CPU: 14% 3.2GHz 48°C | RAM: 12/64G | GPU: 54°C | SSD: 38°C
```

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
[FOLLOWING] (Line 542/542) (G:GPU C:CPU L:Log H:Hint T:Tool | F:Follow | Q:Quit)  🌡  output
```

NVIDIA GPU example (`tool:nvidia-smi`):
```text
=== OLLAMA  parallel:1  tool:nvidia-smi ===
  llama3:8b (4.7 GB | 100% GPU / 0% CPU)
    └ ctx:8192 | 8B | Q4_K_M

CPU:  8% 2.1GHz 42°C | RAM: 9/32G | GPU:65°C | SSD: 37°C
```

--------------------------------------------------------------------------------
...
[FOLLOWING] (Line 98/98) (G:GPU C:CPU L:Log H:Hint T:Tool | F:Follow | Q:Quit)  🌡  output
```

## Screenshots & Video

### Screenshot
<img width="1440" height="903" alt="Screenshot 2026-05-06 at 9 23 54 AM" src="https://github.com/user-attachments/assets/00ced232-27f3-4b85-9a18-b72964789ddd" />


### Video Demo
https://github.com/user-attachments/assets/92d20147-c692-4d68-bb0a-2fbf9f5f47b2


## Performance Tuning

To optimize performance and minimize background CPU usage, consider the following recommendations:

### 1. Persistent Loading (`OLLAMA_KEEP_ALIVE`)
Short keep-alive durations cause frequent, high-cost model reloads. 
- Use the `setup-ollama` script to set a longer duration (e.g., `3m` or longer) to keep the model resident in VRAM.

### 2. Recommended Parameters
When generating Modelfiles with `make-modelfile`, use these tuned parameters for a balance between speed and efficiency:
- **`num_ctx`**: `32768` (Default, lower if memory constrained)
- **`num_thread`**: `4` (Adjust based on core availability)
- **`num_batch`**: `256`

### 3. CPU Power Limiting
Prevent Ollama from saturating your system CPU by limiting its quota via systemd. Create or edit `/etc/systemd/system/ollama.service.d/40-cpu-limit.conf`:

```ini
[Service]
# Limits CPU usage to 400% (effectively 8 cores)
CPUQuota=800%
```

After creating the file, apply the changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

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

### Interactive Monitoring — `watch-ollama`
Run the TUI for real-time monitoring:
```bash
watch-ollama
```

The TUI is split into two panels separated by a reverse-video divider. It uses **event-driven redraws**: the screen is repainted only when log content, telemetry, errors, scroll position, or terminal size actually change, keeping idle CPU usage low. Telemetry (CPU/GPU/RAM/sensor data) refreshes every 2 s; active-model parameters are cached for 30 s per model and re-fetched only when the model set changes or the TTL expires.

| Panel | Contents |
|-------|----------|
| **Top — Telemetry** | Ollama header, active models with VRAM/ctx, CPU load, frequency & temperature, RAM usage, GPU temperature (when nvidia-smi/amd-smi is present), extra sensor readings. Dynamic height adjustment prevents "jitter" while maintaining a stable view. |
| **Bottom — Log** | Scrollable view of `ollama_readable.log` with color-coded roles, thought blocks, and generation metrics |

#### Keyboard & Mouse shortcuts

| Key / Action | Effect |
|---|---|
| `↑` / `↓` | Scroll log one step at a time |
| `Page Up` / `Page Down` | Scroll log one screen at a time |
| Mouse wheel | Scroll log (most terminals) |
| `F` | Toggle **Follow** mode (auto-scroll to newest line) |
| `G` | Toggle GPU panel on/off |
| `C` | Toggle CPU/RAM/temp line on/off |
| `L` | Toggle log panel on/off |
| `H` | Toggle hint bar on/off |
| `T` | Cycle GPU tool: `auto` → `nvidia-smi` → `amd-smi` → `rocm-smi` → `none` → … |
| `S` | Toggle mouse interception (enable/disable terminal selection) |
| `Q` / `Ctrl-C` / `Esc` | Quit |

> `T` cycles the GPU tool and persists the choice to `ollama.conf` — useful when you want to force a specific SMI tool or disable the GPU panel entirely.

#### Status bar indicators

```
[FOLLOWING] (Line 120/542) (G:GPU C:CPU L:Log H:Hint T:Tool | F:Follow | Q:Quit)  🌡  output
```

- **🌡** — thermometer tinted blue/green/yellow/orange/red based on the hottest sensor reading across CPU, GPU, and all detected hardware.
- **⚠️** — appears when a background error is active (e.g. Ollama unreachable, log tail stopped).
- **`output` / `idle`** — green when log traffic was seen in the last 2 seconds, yellow otherwise.
- **Terminal title** — dynamically updated with a colored square (🟦🟩🟨🟧🟥) to reflect system heat at a glance.

### Generating Modelfiles — `make-modelfile`
Use the interactive tool to create and register custom Modelfiles from your GGUF models:
```bash
make-modelfile
```
Scans `~/models` and the current directory for `.gguf` files, prompts for context length and an optional system prompt, and generates ready-to-use `Modelfile` variants. After generation, the tool offers to **automatically import** the models into Ollama and **restart the services** for you, handling naming, registration, and activation in one step.

### Switching GPU Backends — `switch-gpu`
Toggles Ollama between the ROCm and Vulkan backends by writing a systemd drop-in and restarting the service:
```bash
switch-gpu vulkan   # switch to Vulkan backend
switch-gpu rocm     # switch to ROCm backend
switch-gpu status   # show current backend
```

### Server Configuration — `setup-ollama`
Configure the Ollama bind address, port, and model keep-alive duration interactively (defaults: `0.0.0.0:11435`, `1m`):
```bash
setup-ollama
```
Or pass values directly:
```bash
setup-ollama 0.0.0.0 11435 1m
```
This writes an `ollama.conf` file alongside the scripts so that `watch-ollama` automatically connects to the correct address. It also configures systemd drop-ins for `OLLAMA_HOST`, `OLLAMA_KEEP_ALIVE`, and `OLLAMA_DEBUG=2` logging to `/var/log/ollama.log`.

> **Note on port**: Ollama's built-in default is `11434`. This project defaults to `11435` to allow running a custom instance alongside a system-managed one. Adjust as needed.

### Debugging — `watch-ollama-debug.log`
If the TUI is behaving unexpectedly or failing to display error indicators correctly, an internal debug log is maintained in the project working directory:
- **Location**: `~/.ollama-watch-tool/watch-ollama-debug.log`
- **Purpose**: Records internal tool errors and active UI indicator states.

### Updating Ollama — `update-ollama`
Downloads the latest Ollama release and restarts the service:
```bash
update-ollama
```

### Log Reports — `ollama-report` / `ollama-stats`
Parse `/var/log/ollama.log` for human-readable summaries:

```bash
ollama-report   # hardware detection, model loading info, and per-conversation transcript with latency/token-speed
ollama-stats    # token throughput and performance metrics per request
```

## System Requirements
- **OS**: Ubuntu Linux (or systemd-based Linux distributions)
- Python 3.x
- Ollama
- `systemd` (required for background watcher)
- **GPU monitoring** (install whichever matches your hardware):
  - `nvidia-smi` — NVIDIA GPUs (ships with the NVIDIA driver)
  - `amd-smi` — AMD GPUs (ships with the ROCm stack)
  - `rocm-smi` — AMD GPUs (legacy ROCm tool, used when `amd-smi` is absent)
  - If none are installed, the GPU panel is hidden automatically (`tool:none`)

## Better Together

For full token-per-second metrics in logs (the `prompt_eval_count`, `eval_count`, and timing fields that power the `[GEN: ... t/s]` and `[PP: ... pp/s]` display), use this project alongside the forked Ollama build that emits those fields:

👉 **[dst0/ollama-logs-with-tokens](https://github.com/dst0/ollama-logs-with-tokens)** — Ollama fork that adds token counts and timing to inference log lines.

Without it, `watch-ollama` still works but token-speed lines won't appear in the TUI or reports.

## Disclaimer
**THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.**
