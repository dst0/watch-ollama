#!/bin/bash

# watch-ollama Uninstaller
# Every system change is logged to console AND a timestamped file in /tmp

set -e

INSTALL_DIR="$HOME/.ollama-watch-tool/scripts"
INSTALL_ROOT="$HOME/.ollama-watch-tool"
LEGACY_BIN="$HOME/.local/bin/watch-ollama"
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

if [ -n "${NO_COLOR:-}" ]; then
    COLOR_INFO=""
    COLOR_WARN=""
    COLOR_ERROR=""
    COLOR_CHANGE=""
    COLOR_SECTION=""
    COLOR_RESET=""
else
    COLOR_INFO=$'\033[36m'
    COLOR_WARN=$'\033[33m'
    COLOR_ERROR=$'\033[31m'
    COLOR_CHANGE=$'\033[32m'
    COLOR_SECTION=$'\033[1;34m'
    COLOR_RESET=$'\033[0m'
fi

emit() {
    local color="$1"
    local text="$2"
    printf "%s%s%s\n" "$color" "$text" "$COLOR_RESET"
}

timestamp() {
    date +'%Y-%m-%d %H:%M:%S'
}

log() {
    emit "$COLOR_INFO" "[$(timestamp)] [v$VERSION] [INFO] $1"
}

warn() {
    emit "$COLOR_WARN" "[$(timestamp)] [v$VERSION] [WARN] $1"
}

error() {
    emit "$COLOR_ERROR" "[$(timestamp)] [v$VERSION] [ERROR] $1"
}

section() {
    emit "$COLOR_SECTION" ""
    emit "$COLOR_SECTION" "================================================================"
    emit "$COLOR_SECTION" "$1"
    emit "$COLOR_SECTION" "================================================================"
}

# Every line tagged [CHANGE] represents a modification made to the system
change() {
    emit "$COLOR_CHANGE" "[$(timestamp)] [v$VERSION] [CHANGE] $1"
}

prompt_yes_no() {
    local prompt="$1"
    local reply
    local prompt_text="${COLOR_WARN}? ${prompt} [Y/n] ${COLOR_RESET}"

    if [ -r /dev/tty ] && [ -w /dev/tty ]; then
        printf "%b" "$prompt_text"
        IFS= read -r -n 1 reply < /dev/tty || reply=""
        if [ -n "$reply" ]; then
            printf "%s\n" "$reply"
        else
            printf "\n" > /dev/tty
        fi
    else
        printf "%b" "$prompt_text"
        IFS= read -r reply
    fi

    [[ -z "$reply" || $reply == [yY] ]]
}

section "watch-ollama v$VERSION uninstaller"
log "Uninstall log: $LOG_FILE"

# ── Detect shell rc file ───────────────────────────────────────────────────────
section "1. Shell aliases"
CURRENT_SHELL="$(basename "$SHELL")"
case "$CURRENT_SHELL" in
    bash)  SHELL_RC="$HOME/.bashrc" ;;
    zsh)   SHELL_RC="$HOME/.zshrc" ;;
    fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
    ksh)   SHELL_RC="$HOME/.kshrc" ;;
    *)
        warn "Unknown shell '$CURRENT_SHELL', assuming ~/.bashrc"
        SHELL_RC="$HOME/.bashrc"
        ;;
esac
log "Detected shell: $CURRENT_SHELL  →  rc file: $SHELL_RC"

# ── Remove aliases / legacy PATH from rc file ──────────────────────────────────
if [ -f "$SHELL_RC" ]; then
    if grep -qF "$ALIAS_MARKER_START" "$SHELL_RC" 2>/dev/null; then
        cp "$SHELL_RC" "$SHELL_RC.tmp"
        sed "/$ALIAS_MARKER_START/,/$ALIAS_MARKER_END/d" "$SHELL_RC.tmp" > "$SHELL_RC"
        rm -f "$SHELL_RC.tmp"
        change "Removed alias block from $SHELL_RC"
    else
        log "No alias block found in $SHELL_RC"
    fi

    if grep -qF "$PATH_MARKER" "$SHELL_RC" 2>/dev/null; then
        cp "$SHELL_RC" "$SHELL_RC.tmp"
        sed "/$PATH_MARKER/{N;d;}" "$SHELL_RC.tmp" > "$SHELL_RC"
        rm -f "$SHELL_RC.tmp"
        change "Removed legacy PATH entry from $SHELL_RC"
    fi
else
    warn "Shell rc file not found: $SHELL_RC — skipping"
fi

# ── Remove legacy PATH executable if it belongs to watch-ollama ────────────────
if [ -f "$LEGACY_BIN" ]; then
    if grep -qF ".ollama-watch-tool/scripts/watch-ollama" "$LEGACY_BIN" 2>/dev/null ||
       grep -qF "/var/log/ollama_readable.log" "$LEGACY_BIN" 2>/dev/null; then
        rm -f "$LEGACY_BIN"
        change "Removed legacy executable: $LEGACY_BIN"
    else
        warn "Legacy path exists but is not a watch-ollama file: $LEGACY_BIN — skipping"
    fi
fi

# ── Remove systemd service ─────────────────────────────────────────────────────
section "2. Systemd service"
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
    warn "Service file not found: $SYSTEMD_DIR/$SERVICE_FILE — skipping"
fi

# ── Remove scripts directory ───────────────────────────────────────────────────
section "3. Installed files"
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
    warn "Scripts directory not found: $INSTALL_DIR — skipping"
fi

# ── Optionally remove install root (contains install.log etc.) ─────────────────
section "4. Install root"
if [ -d "$INSTALL_ROOT" ]; then
    if [ -d "$INSTALL_ROOT/.git" ]; then
        warn "$INSTALL_ROOT appears to be a git repository. Skipping removal of root directory to prevent code loss."
    else
        echo ""
        if prompt_yes_no "Remove entire install directory $INSTALL_ROOT, including all logs?"; then
            rm -rf "$INSTALL_ROOT"
            change "Removed directory tree: $INSTALL_ROOT"
        else
            log "Kept: $INSTALL_ROOT"
        fi
    fi
else
    log "Install root not found: $INSTALL_ROOT — skipping"
fi

section "Uninstallation complete"
printf "%-22s %s\n" "Version:" "v$VERSION"
printf "%-22s %s\n" "Scripts:" "$INSTALL_DIR"
printf "%-22s %s\n" "Aliases:" "$SHELL_RC"
printf "%-22s %s\n" "Uninstall log:" "$LOG_FILE"
echo ""
log "Run 'source $SHELL_RC' or open a new terminal to deactivate aliases."
