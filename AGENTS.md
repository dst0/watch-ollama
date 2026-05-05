# Repository Guidelines

## Project Structure & Module Organization

`scripts/` contains the runtime tools: `watch-ollama` is the curses TUI, `ollama_watcher.py` tails `/var/log/ollama.log` into a readable log, and helper scripts manage setup, GPU backend switching, updates, reports, stats, and Modelfile creation. `systemd/` contains the `ollama-watcher.service` template. `tests/` contains Python unit tests, currently focused on log sanitization and TUI rendering helpers. Root-level `install.sh` and `uninstall.sh` manage the installed copy under `~/.ollama-watch-tool/`; `VERSION` tracks the release version.

## Build, Test, and Development Commands

This project is script-based and has no build step.

```bash
python3 -m unittest discover -s tests
```

Runs the full test suite.

```bash
./install.sh
```

Installs scripts, aliases, and the systemd watcher service. The installer may prompt for a clean reinstall and preserves `*.conf` files.

```bash
watch-ollama
setup-ollama 0.0.0.0 11435
switch-gpu [vulkan|rocm|status]
```

Common installed commands for running the TUI, configuring the Ollama host, and switching GPU backends.

## Coding Style & Naming Conventions

Use Python 3 and shell scripts consistent with the existing files. Prefer 4-space indentation in Python and clear function names such as `sanitize_render_text` or `parse_ollama_ps`. Keep shell variables uppercase for configuration values, for example `INSTALL_DIR` and `OLLAMA_SERVICE_DIR`. Avoid broad rewrites; this repo favors small, direct fixes to the relevant script.

## Testing Guidelines

Tests use the standard library `unittest` framework. Add tests under `tests/` with names like `test_log_sanitization.py` and methods beginning with `test_`. When changing log parsing, rendering, sanitization, or watcher behavior, add focused tests that cover the exact log shape being fixed. Run `python3 -m unittest discover -s tests` before committing.

## Commit & Pull Request Guidelines

Recent commits use short imperative messages, for example `Fix watch log streaming colors` and `Stabilize telemetry panel height`. Keep commits scoped to one behavior change. Pull requests should describe the user-visible effect, list verification commands, mention any installer or systemd impact, and include screenshots or terminal excerpts for TUI-facing changes when useful.

## Security & Configuration Tips

Do not commit local `*.conf` files or logs. Be careful with scripts that write `/etc/systemd/system/` or restart services; document those effects in PRs. The default project Ollama port is `11435`, not Ollama's built-in `11434`, so preserve that distinction unless intentionally changing deployment behavior.
