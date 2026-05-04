#!/bin/bash

# watch-ollama Universal Installer
# Installs monitoring scripts and systemd service

set -e

INSTALL_DIR="$HOME/.local/bin"
SYSTEMD_DIR="/etc/systemd/system"

echo "--- watch-ollama Installer ---"

# Ensure local bin exists
mkdir -p "$INSTALL_DIR"

# Copy scripts
echo "Installing scripts to $INSTALL_DIR..."
cp scripts/* "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR"/*

# Setup systemd service
if [ -d "$SYSTEMD_DIR" ]; then
    echo "Installing systemd service..."
    sudo cp systemd/ollama-watcher.service "$SYSTEMD_DIR/"
    sudo systemctl daemon-reload
    sudo systemctl enable ollama-watcher
    sudo systemctl start ollama-watcher
    echo "Service installed and started."
else
    echo "Warning: Systemd directory not found. Skipping service installation."
fi

echo "--- Installation Complete ---"
echo "You can now run 'watch-ollama' from your terminal."
