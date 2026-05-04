#!/bin/bash

# watch-ollama Universal Installer
# Hardened, location-independent installer

set -e

# Project root based on the script's location
PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
INSTALL_DIR="$HOME/.ollama-tools/scripts"
SYSTEMD_DIR="/etc/systemd/system"
LOG_FILE="/var/log/watch-ollama-install.log"

# Setup logging (create log file if it doesn't exist)
sudo touch "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "--- Starting watch-ollama Installation ---"
log "Project Root: $PROJECT_ROOT"

# Ensure target directory exists
if [ ! -d "$INSTALL_DIR" ]; then
    log "Creating directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# Copy scripts
log "Copying scripts from $PROJECT_ROOT/scripts..."
if [ -d "$PROJECT_ROOT/scripts" ]; then
    for script in "$PROJECT_ROOT/scripts/"*; do
        if [ -f "$script" ]; then
            filename=$(basename "$script")
            log "Installing script: $filename"
            cp "$script" "$INSTALL_DIR/"
            chmod +x "$INSTALL_DIR/$filename"
            log "Successfully installed and made executable: $filename"
        fi
    done
else
    log "Error: Scripts directory not found in $PROJECT_ROOT"
    exit 1
fi

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/ollama-watcher.service" ]; then
        log "Installing systemd service to $SYSTEMD_DIR..."
        sudo cp "$PROJECT_ROOT/systemd/ollama-watcher.service" "$SYSTEMD_DIR/"
        log "Reloading systemd daemon..."
        sudo systemctl daemon-reload
        log "Enabling ollama-watcher service..."
        sudo systemctl enable ollama-watcher
        log "Starting ollama-watcher service..."
        sudo systemctl start ollama-watcher
        log "Service installed and started successfully."
    else
        log "Error: Systemd service file not found in $PROJECT_ROOT/systemd/"
    fi
else
    log "Warning: Systemd directory not found. Skipping service installation."
fi

log "--- Installation Complete ---"
log "Log file available at: $LOG_FILE"
