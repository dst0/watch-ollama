#!/bin/bash
# Log rotation script for watch-ollama
# Usage: ./rotate-logs.sh

LOG_FILE="$HOME/.ollama-watch-tool/ollama_readable.log"
BACKUP_DIR="$HOME/.ollama-watch-tool/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

if [ -f "$LOG_FILE" ]; then
    mkdir -p "$BACKUP_DIR"
    mv "$LOG_FILE" "$BACKUP_DIR/ollama_readable.log.$TIMESTAMP"
    echo "Rotated log to $BACKUP_DIR/ollama_readable.log.$TIMESTAMP"
else
    echo "Log file $LOG_FILE not found."
fi
