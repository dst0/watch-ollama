#!/bin/bash

# Ollama Server Configuration Setup
# Usage: setup-ollama.sh [HOST] [PORT] [KEEP_ALIVE]
#   HOST: bind address (default: 0.0.0.0)
#   PORT: port number  (default: 11435)
#   KEEP_ALIVE: model duration (default: 1m)

OLLAMA_SERVICE_DIR="/etc/systemd/system/ollama.service.d"
OLLAMA_CONFIG="$OLLAMA_SERVICE_DIR/10-host.conf"
KEEP_ALIVE_CONFIG="$OLLAMA_SERVICE_DIR/20-keep-alive.conf"
INSTALL_DIR="$(dirname "$(readlink -f "$0")")"
OLLAMA_CONF="$INSTALL_DIR/ollama.conf"

DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT="11435"
DEFAULT_KEEP_ALIVE="1m"

# Accept positional args or prompt interactively
if [ -n "$1" ]; then
    OLLAMA_HOST_VAL="$1"
else
    read -p "Bind address [${DEFAULT_HOST}]: " input_host
    OLLAMA_HOST_VAL="${input_host:-$DEFAULT_HOST}"
fi

if [ -n "$2" ]; then
    OLLAMA_PORT_VAL="$2"
else
    read -p "Port [${DEFAULT_PORT}]: " input_port
    OLLAMA_PORT_VAL="${input_port:-$DEFAULT_PORT}"
fi

if [ -n "$3" ]; then
    OLLAMA_KEEP_ALIVE_VAL="$3"
else
    read -p "Keep Alive [${DEFAULT_KEEP_ALIVE}]: " input_keep_alive
    OLLAMA_KEEP_ALIVE_VAL="${input_keep_alive:-$DEFAULT_KEEP_ALIVE}"
fi

# Validate port is numeric and in valid range (1-65535)
if ! [[ "$OLLAMA_PORT_VAL" =~ ^[0-9]+$ ]] || [ "$OLLAMA_PORT_VAL" -lt 1 ] || [ "$OLLAMA_PORT_VAL" -gt 65535 ]; then
    echo "Error: Port must be a number between 1 and 65535." >&2
    exit 1
fi

FULL_ADDR="${OLLAMA_HOST_VAL}:${OLLAMA_PORT_VAL}"

echo "Setting Ollama Host to ${FULL_ADDR}..."
sudo mkdir -p "$OLLAMA_SERVICE_DIR"
printf "[Service]\nEnvironment=\"OLLAMA_HOST=%s\"\n" "$FULL_ADDR" | sudo tee "$OLLAMA_CONFIG" > /dev/null

echo "Setting Ollama Keep Alive to ${OLLAMA_KEEP_ALIVE_VAL}..."
printf "[Service]\nEnvironment=\"OLLAMA_KEEP_ALIVE=%s\"\n" "$OLLAMA_KEEP_ALIVE_VAL" | sudo tee "$KEEP_ALIVE_CONFIG" > /dev/null

LOGGING_CONFIG="$OLLAMA_SERVICE_DIR/30-logging.conf"
echo "Configuring Ollama logging to /var/log/ollama.log..."
printf "[Service]\nEnvironment=\"OLLAMA_DEBUG=2\"\nStandardOutput=append:/var/log/ollama.log\nStandardError=append:/var/log/ollama.log\n" | sudo tee "$LOGGING_CONFIG" > /dev/null

# Persist the URL so other tools (e.g. watch-ollama) can read it
printf "OLLAMA_HOST=%s\n" "$FULL_ADDR" > "$OLLAMA_CONF"
echo "Configuration saved to $OLLAMA_CONF"

echo "Applying changes..."
sudo systemctl daemon-reload
sudo systemctl restart ollama

echo "Ollama is now configured to listen on ${FULL_ADDR}"
