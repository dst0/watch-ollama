#!/bin/bash

# watch-ollama Universal Installer
# Installs monitoring scripts and systemd service with detailed logging

set -e

INSTALL_DIR="/home/dst/.ollama-tools/scripts"
SYSTEMD_DIR="/etc/systemd/system"
LOG_FILE="/var/log/watch-ollama-install.log"

# Setup logging
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

log "--- Starting watch-ollama Installation ---"

# Ensure local bin exists
if [ ! -d "$INSTALL_DIR" ]; then
    log "Creating directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# Copy scripts
log "Copying scripts to $INSTALL_DIR..."
for script in scripts/*; do
    if [ -f "$script" ]; then
        filename=$(basename "$script")
        log "Installing script: $filename"
        cp "$script" "$INSTALL_DIR/"
        chmod +x "$INSTALL_DIR/$filename"
        log "Successfully installed and made executable: $filename"
    fi
done

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    log "Installing systemd service to $SYSTEMD_DIR..."
    sudo cp systemd/ollama-watcher.service "$SYSTEMD_DIR/"
    log "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    log "Enabling ollama-watcher service..."
    sudo systemctl enable ollama-watcher
    log "Starting ollama-watcher service..."
    sudo systemctl start ollama-watcher
    log "Service installed and started successfully."
else
    log "Error: Systemd directory not found. Skipping service installation."
fi

log "--- Installation Complete ---"
log "Log file available at: $LOG_FILE"
