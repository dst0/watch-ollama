#!/bin/bash

# watch-ollama Universal Installer
# Versioned, location-independent installer with verification

set -e

# Project root based on the script's location
PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
VERSION=$(cat "$PROJECT_ROOT/VERSION")
INSTALL_DIR="$HOME/.ollama-tools/scripts"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="ollama-watcher.service"
LOG_FILE="/var/log/watch-ollama-install.log"

# Setup logging
sudo touch "$LOG_FILE" 2>/dev/null || true
exec > >(tee -a "$LOG_FILE") 2>&1

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] $1"
}

log "--- Starting watch-ollama v$VERSION Installation ---"

# Verify Existing Installation
if [ -d "$INSTALL_DIR" ]; then
    log "Existing installation found at $INSTALL_DIR."
    read -p "Do you want to overwrite the existing installation? (y/n): " confirm
    if [[ $confirm != [yY] ]]; then
        log "Installation aborted by user."
        exit 0
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

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/$SERVICE_FILE" ]; then
        log "Installing systemd service..."
        sudo cp "$PROJECT_ROOT/systemd/$SERVICE_FILE" "$SYSTEMD_DIR/"
        sudo systemctl daemon-reload
        sudo systemctl enable ollama-watcher
        sudo systemctl restart ollama-watcher
        log "Service installed and restarted."
    else
        log "Error: Service file not found."
    fi
fi

log "--- Installation v$VERSION Complete ---"
log "Log file: $LOG_FILE"
