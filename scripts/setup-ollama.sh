#!/bin/bash

# Ollama Server Configuration Setup

# Set the port to 11435 as per your preference
OLLAMA_SERVICE_DIR="/etc/systemd/system/ollama.service.d"
OLLAMA_CONFIG="$OLLAMA_SERVICE_DIR/10-host.conf"

echo "Setting Ollama Host to 0.0.0.0:11435..."
sudo mkdir -p "$OLLAMA_SERVICE_DIR"
printf "[Service]\nEnvironment=\"OLLAMA_HOST=0.0.0.0:11435\"\n" | sudo tee "$OLLAMA_CONFIG" > /dev/null

echo "Applying changes..."
sudo systemctl daemon-reload
sudo systemctl restart ollama

echo "Ollama is now configured to listen on 0.0.0.0:11435"
