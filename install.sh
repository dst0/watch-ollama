#!/bin/bash

# watch-ollama Universal Installer
# Every system change is logged to console AND ~/.ollama-watch-tool/install.log

set -e

PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
VERSION=$(cat "$PROJECT_ROOT/VERSION")
INSTALL_DIR="$HOME/.ollama-watch-tool/scripts"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="ollama-watcher.service"
LOG_DIR="$HOME/.ollama-watch-tool"
LOG_FILE="$LOG_DIR/install.log"
ALIAS_MARKER_START="# watch-ollama: aliases"
ALIAS_MARKER_END="# watch-ollama: aliases-end"

# Setup logging — all stdout/stderr goes to console AND the log file
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

cat "$PROJECT_ROOT/scripts/header.txt"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] $1"
}

# Every line tagged [CHANGE] represents a modification made to the system
change() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] [CHANGE] $1"
}

log "--- Starting watch-ollama v$VERSION Installation ---"
change "Created/ensured directory: $LOG_DIR"
log "Install log: $LOG_FILE"

# ── Clean install ──────────────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    log "Existing installation found at $INSTALL_DIR."
    read -p "Perform a clean install? (scripts removed, config files preserved) (y/n): " confirm
    if [[ $confirm == [yY] ]]; then
        log "Cleaning up old installation (preserving *.conf files)..."
        while IFS= read -r -d '' f; do
            rm -f "$f"
            change "Removed: $f"
        done < <(find "$INSTALL_DIR" -maxdepth 1 -type f ! -name "*.conf" -print0)
    else
        log "Skipping clean-up, proceeding with update..."
    fi
fi

# ── Create scripts directory ───────────────────────────────────────────────────
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    change "Created directory: $INSTALL_DIR"
else
    log "Directory already exists: $INSTALL_DIR"
fi

# ── Copy VERSION ───────────────────────────────────────────────────────────────
cp "$PROJECT_ROOT/VERSION" "$INSTALL_DIR/"
change "Copied: VERSION → $INSTALL_DIR/VERSION"

# ── Copy scripts ───────────────────────────────────────────────────────────────
log "Copying scripts from $PROJECT_ROOT/scripts..."
if [ ! -d "$PROJECT_ROOT/scripts" ]; then
    log "ERROR: Scripts directory not found at $PROJECT_ROOT/scripts"
    exit 1
fi
for script in "$PROJECT_ROOT/scripts/"*; do
    if [ -f "$script" ]; then
        filename=$(basename "$script")
        cp "$script" "$INSTALL_DIR/$filename"
        change "Copied: $filename → $INSTALL_DIR/$filename"
        chmod +x "$INSTALL_DIR/$filename"
        change "chmod +x: $INSTALL_DIR/$filename"
    fi
done

# ── Shell aliases ──────────────────────────────────────────────────────────────
# Installs named aliases for each user-facing command into the shell rc file.
# Replaces any legacy PATH export written by older versions of this installer.
add_aliases() {
    local rc_file="$1"
    local shell_name="$2"

    # Remove any PATH block written by a previous version of this installer
    if grep -qF "# watch-ollama: PATH" "$rc_file" 2>/dev/null; then
        sed -i '/# watch-ollama: PATH/,+1d' "$rc_file"
        change "Removed legacy PATH entry from $rc_file"
    fi

    # Remove existing alias block so we always write a fresh, up-to-date one
    if grep -qF "$ALIAS_MARKER_START" "$rc_file" 2>/dev/null; then
        sed -i "/$ALIAS_MARKER_START/,/$ALIAS_MARKER_END/d" "$rc_file"
        change "Removed outdated alias block from $rc_file"
    fi

    if [ "$shell_name" = "fish" ]; then
        mkdir -p "$(dirname "$rc_file")"
        touch "$rc_file"
        {
            echo ""
            echo "$ALIAS_MARKER_START"
            echo 'alias watch-ollama  "$HOME/.ollama-watch-tool/scripts/watch-ollama"'
            echo 'alias setup-ollama  "$HOME/.ollama-watch-tool/scripts/setup-ollama.sh"'
            echo 'alias switch-gpu    "$HOME/.ollama-watch-tool/scripts/switch-gpu.sh"'
            echo 'alias update-ollama "$HOME/.ollama-watch-tool/scripts/update-ollama.sh"'
            echo 'alias ollama-report "python3 $HOME/.ollama-watch-tool/scripts/ollama_report.py"'
            echo 'alias ollama-stats  "python3 $HOME/.ollama-watch-tool/scripts/ollama_stats.py"'
            echo "$ALIAS_MARKER_END"
        } >> "$rc_file"
    else
        {
            echo ""
            echo "$ALIAS_MARKER_START"
            echo "alias watch-ollama='\$HOME/.ollama-watch-tool/scripts/watch-ollama'"
            echo "alias setup-ollama='\$HOME/.ollama-watch-tool/scripts/setup-ollama.sh'"
            echo "alias switch-gpu='\$HOME/.ollama-watch-tool/scripts/switch-gpu.sh'"
            echo "alias update-ollama='\$HOME/.ollama-watch-tool/scripts/update-ollama.sh'"
            echo "alias ollama-report='python3 \$HOME/.ollama-watch-tool/scripts/ollama_report.py'"
            echo "alias ollama-stats='python3 \$HOME/.ollama-watch-tool/scripts/ollama_stats.py'"
            echo "$ALIAS_MARKER_END"
        } >> "$rc_file"
    fi
    change "Wrote aliases to $rc_file"
}

CURRENT_SHELL="$(basename "$SHELL")"
case "$CURRENT_SHELL" in
    bash)  SHELL_RC="$HOME/.bashrc" ;;
    zsh)   SHELL_RC="$HOME/.zshrc" ;;
    fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
    ksh)   SHELL_RC="$HOME/.kshrc" ;;
    *)
        log "Unknown shell '$CURRENT_SHELL', falling back to ~/.bashrc"
        CURRENT_SHELL="bash"
        SHELL_RC="$HOME/.bashrc"
        ;;
esac
log "Detected shell: $CURRENT_SHELL  →  rc file: $SHELL_RC"
add_aliases "$SHELL_RC" "$CURRENT_SHELL"

# ── systemd service ────────────────────────────────────────────────────────────
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/$SERVICE_FILE" ]; then
        log "Installing/Updating systemd service..."
        sed -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
            -e "s|__USER__|$USER|g" \
            "$PROJECT_ROOT/systemd/$SERVICE_FILE" | sudo tee "$SYSTEMD_DIR/$SERVICE_FILE" > /dev/null
        change "Wrote: $SYSTEMD_DIR/$SERVICE_FILE"
        sudo systemctl daemon-reload
        change "systemctl daemon-reload"

        sudo systemctl enable ollama-watcher
        change "systemctl enable ollama-watcher"

        if sudo systemctl is-active --quiet ollama-watcher; then
            sudo systemctl restart ollama-watcher
            change "systemctl restart ollama-watcher"
        else
            if sudo systemctl start ollama-watcher; then
                change "systemctl start ollama-watcher"
            else
                log "Warning: Could not start ollama-watcher service (will start on next boot)."
            fi
        fi
        log "Service installed and enabled."
    else
        log "Warning: Service file not found at $PROJECT_ROOT/systemd/$SERVICE_FILE — skipping."
    fi
else
    log "systemd not found on this system — skipping service installation."
fi

log "--- Installation v$VERSION Complete ---"
log "Scripts installed to : $INSTALL_DIR"
log "Aliases registered in: $SHELL_RC"
log "Run 'source $SHELL_RC' (or open a new terminal) to activate aliases."
log "Install log          : $LOG_FILE"
