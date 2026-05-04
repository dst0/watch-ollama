#!/bin/bash

# watch-ollama Universal Installer
# Versioned, location-independent installer with safe reinstallation

set -e

# Project root based on the script's location
PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
VERSION=$(cat "$PROJECT_ROOT/VERSION")
INSTALL_DIR="$HOME/.ollama-watch-tool/scripts"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="ollama-watcher.service"
LOG_FILE="/var/log/watch-ollama-install.log"

# Setup logging
sudo touch "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

cat "$PROJECT_ROOT/scripts/header.txt"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] $1"
}

log "--- Starting watch-ollama v$VERSION Installation ---"

# Verify Existing Installation
if [ -d "$INSTALL_DIR" ]; then
    log "Existing installation found at $INSTALL_DIR."
    read -p "Do you want to perform a clean install? (Existing scripts will be removed, config files preserved) (y/n): " confirm
    if [[ $confirm == [yY] ]]; then
        log "Cleaning up old installation (preserving configs)..."
        # Remove scripts but keep potential config files if they existed
        # Assuming configs are not in /scripts, but just in case:
        find "$INSTALL_DIR" -maxdepth 1 -type f ! -name "*.conf" -delete
    else
        log "Skipping clean-up, proceeding with update..."
    fi
fi

# Ensure target directory exists
mkdir -p "$INSTALL_DIR"

# Copy VERSION file
log "Copying version metadata..."
cp "$PROJECT_ROOT/VERSION" "$INSTALL_DIR/"

# Copy scripts
log "Copying scripts from $PROJECT_ROOT/scripts..."
if [ -d "$PROJECT_ROOT/scripts" ]; then
    for script in "$PROJECT_ROOT/scripts/"*; do
        if [ -f "$script" ]; then
            filename=$(basename "$script")
            cp "$script" "$INSTALL_DIR/"
            chmod +x "$INSTALL_DIR/$filename"
            log "Installed: $filename"
        fi
    done
else
    log "Error: Scripts directory not found in $PROJECT_ROOT"
    exit 1
fi

# Add scripts directory to PATH in the active shell's rc file (idempotent)
add_to_path() {
    local rc_file="$1"
    local shell_name="$2"
    local marker="# watch-ollama: PATH"
    local path_line

    if [ "$shell_name" = "fish" ]; then
        path_line="set -gx PATH \$HOME/.ollama-watch-tool/scripts \$PATH"
        mkdir -p "$(dirname "$rc_file")"
        # fish config.fish may not exist yet; touch it so the -f check passes
        touch "$rc_file"
    else
        path_line='export PATH="$HOME/.ollama-watch-tool/scripts:$PATH"'
    fi

    if ! grep -qF "$marker" "$rc_file"; then
        echo "" >> "$rc_file"
        echo "$marker" >> "$rc_file"
        echo "$path_line" >> "$rc_file"
        log "Added scripts to PATH in $rc_file"
    fi
}

# Detect the user's current shell and target its rc file
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
add_to_path "$SHELL_RC" "$CURRENT_SHELL"
SOURCE_CMD="source $SHELL_RC"

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/$SERVICE_FILE" ]; then
        log "Installing/Updating systemd service..."
        # Generate a customised service file with the current user and install path
        WATCHER_BIN="$INSTALL_DIR/ollama_watcher.py"
        sed \
            -e "s|User=dst|User=$USER|g" \
            -e "s|Group=dst|Group=$USER|g" \
            -e "s|/home/dst/.ollama-watch-tool/scripts|$INSTALL_DIR|g" \
            "$PROJECT_ROOT/systemd/$SERVICE_FILE" \
            | sudo tee "$SYSTEMD_DIR/$SERVICE_FILE" > /dev/null
        sudo systemctl daemon-reload
        sudo systemctl enable ollama-watcher
        # Use 'restart' if already running, 'start' otherwise, to avoid a
        # non-zero exit on the very first install.
        if sudo systemctl is-active --quiet ollama-watcher; then
            sudo systemctl restart ollama-watcher
        else
            if ! sudo systemctl start ollama-watcher; then
                log "Warning: Could not start ollama-watcher service (will be started on next boot)."
            fi
        fi
        log "Service installed and enabled."
    else
        log "Error: Service file not found."
    fi
fi

log "--- Installation v$VERSION Complete ---"
log "Scripts installed to: $INSTALL_DIR"
log "Run '$SOURCE_CMD' (or open a new terminal) to use watch-ollama directly."
log "Log file: $LOG_FILE"
