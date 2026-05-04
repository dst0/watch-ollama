#!/bin/bash

# watch-ollama Universal Installer
# Versioned, location-independent installer with safe reinstallation

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

echo "
   ___  __    __                __   __        __ 
  / _ \/ /   / /  ___ ________ / /  / /  ___  / / 
 / // / /__ / /__/ _ \`/ __/ _ / /  / /__/ _ \/ _ \ 
/___/_____/____/\_,_/_/  \__,_/_/  /____/\___/_.__/ 
                                                    
"

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

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/$SERVICE_FILE" ]; then
        log "Installing/Updating systemd service..."
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
