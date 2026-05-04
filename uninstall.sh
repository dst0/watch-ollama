#!/bin/bash

# watch-ollama Uninstaller
# Every system change is logged to console AND a timestamped file in /tmp

set -e

INSTALL_DIR="$HOME/.ollama-watch-tool/scripts"
INSTALL_ROOT="$HOME/.ollama-watch-tool"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="ollama-watcher.service"
ALIAS_MARKER_START="# watch-ollama: aliases"
ALIAS_MARKER_END="# watch-ollama: aliases-end"
PATH_MARKER="# watch-ollama: PATH"

LOG_FILE="/tmp/watch-ollama-uninstall-$(date +%Y%m%d-%H%M%S).log"

# Setup logging — all stdout/stderr goes to console AND the /tmp log
exec > >(tee -a "$LOG_FILE") 2>&1

# Read installed version if available
VERSION="unknown"
if [ -f "$INSTALL_DIR/VERSION" ]; then
    VERSION=$(cat "$INSTALL_DIR/VERSION")
fi

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] $1"
}

# Every line tagged [CHANGE] represents a modification made to the system
change() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] [v$VERSION] [CHANGE] $1"
}

log "--- watch-ollama Uninstaller ---"
log "Uninstall log: $LOG_FILE"

# ── Detect shell rc file ───────────────────────────────────────────────────────
CURRENT_SHELL="$(basename "$SHELL")"
case "$CURRENT_SHELL" in
    bash)  SHELL_RC="$HOME/.bashrc" ;;
    zsh)   SHELL_RC="$HOME/.zshrc" ;;
    fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
    ksh)   SHELL_RC="$HOME/.kshrc" ;;
    *)
        log "Unknown shell '$CURRENT_SHELL', assuming ~/.bashrc"
        SHELL_RC="$HOME/.bashrc"
        ;;
esac
log "Detected shell: $CURRENT_SHELL  →  rc file: $SHELL_RC"

# ── Remove aliases / legacy PATH from rc file ──────────────────────────────────
if [ -f "$SHELL_RC" ]; then
    if grep -qF "$ALIAS_MARKER_START" "$SHELL_RC" 2>/dev/null; then
        sed -i "/$ALIAS_MARKER_START/,/$ALIAS_MARKER_END/d" "$SHELL_RC"
        change "Removed alias block from $SHELL_RC"
    else
        log "No alias block found in $SHELL_RC"
    fi

    if grep -qF "$PATH_MARKER" "$SHELL_RC" 2>/dev/null; then
        sed -i "/$PATH_MARKER/,+1d" "$SHELL_RC"
        change "Removed legacy PATH entry from $SHELL_RC"
    fi
else
    log "Shell rc file not found: $SHELL_RC — skipping"
fi

# ── Remove systemd service ─────────────────────────────────────────────────────
if [ -f "$SYSTEMD_DIR/$SERVICE_FILE" ]; then
    log "Removing systemd service: $SERVICE_FILE"

    if sudo systemctl is-active --quiet ollama-watcher 2>/dev/null; then
        sudo systemctl stop ollama-watcher
        change "systemctl stop ollama-watcher"
    fi

    if sudo systemctl is-enabled --quiet ollama-watcher 2>/dev/null; then
        sudo systemctl disable ollama-watcher
        change "systemctl disable ollama-watcher"
    fi

    sudo rm -f "$SYSTEMD_DIR/$SERVICE_FILE"
    change "Removed: $SYSTEMD_DIR/$SERVICE_FILE"

    sudo systemctl daemon-reload
    change "systemctl daemon-reload"
else
    log "Service file not found: $SYSTEMD_DIR/$SERVICE_FILE — skipping"
fi

# ── Remove scripts directory ───────────────────────────────────────────────────
if [ -d "$INSTALL_DIR" ]; then
    log "Removing scripts: $INSTALL_DIR"
    while IFS= read -r -d '' f; do
        rm -f "$f"
        change "Removed: $f"
    done < <(find "$INSTALL_DIR" -type f -print0)
    find "$INSTALL_DIR" -type d | sort -r | while read -r d; do
        rmdir "$d" 2>/dev/null && change "Removed directory: $d" || true
    done
else
    log "Scripts directory not found: $INSTALL_DIR — skipping"
fi

# ── Optionally remove install root (contains install.log etc.) ─────────────────
if [ -d "$INSTALL_ROOT" ]; then
    echo ""
    read -p "Remove entire install directory $INSTALL_ROOT (including all logs)? (y/n): " remove_root
    if [[ $remove_root == [yY] ]]; then
        if [ -d "$INSTALL_ROOT/.git" ]; then
            log "Warning: $INSTALL_ROOT appears to be a git repository. Skipping removal of root directory to prevent code loss."
        else
            rm -rf "$INSTALL_ROOT"
            change "Removed directory tree: $INSTALL_ROOT"
        fi
    else
        log "Kept: $INSTALL_ROOT"
    fi
fi

log "--- Uninstallation complete ---"
log "Run 'source $SHELL_RC' (or open a new terminal) to deactivate aliases."
log "Uninstall log: $LOG_FILE"
