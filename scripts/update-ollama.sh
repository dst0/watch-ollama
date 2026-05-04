#!/bin/bash

# Update Ollama to latest version
echo "Updating Ollama..."
curl -fsSL https://ollama.com/install.sh | sh

echo "Reloading systemd and restarting Ollama..."
sudo systemctl daemon-reload
sudo systemctl restart ollama

echo "Ollama updated and restarted."
