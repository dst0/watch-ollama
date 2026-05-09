#!/bin/bash

# watch-ollama Universal Installer
# Every system change is logged to console AND ~/.ollama-watch-tool/install.log

set -e

PROJECT_ROOT="$(dirname "$(readlink -f "$0")")"
VERSION=$(cat "$PROJECT_ROOT/VERSION")
INSTALL_DIR="$HOME/.ollama-watch-tool/scripts"
SYSTEMD_DIR="/etc/systemd/system"
SERVICE_FILE="ollama-watcher.service"
LOG_DIR="$HOME/.ollama-watch-tool"
LOG_FILE="$LOG_DIR/install.log"
ALIAS_MARKER_START="# watch-ollama: aliases"
ALIAS_MARKER_END="# watch-ollama: aliases-end"

# Setup logging — all stdout/stderr goes to console AND the log file
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

if [ -n "${NO_COLOR:-}" ]; then
    sed -r 's/\\033\[[0-9;]*m//g' "$PROJECT_ROOT/scripts/header.txt"
else
    printf "%b\n" "$(cat "$PROJECT_ROOT/scripts/header.txt")"
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

    # Try reading from stdin first (to support 'yes | script.sh')
    if [ ! -t 0 ]; then
        IFS= read -r reply
        [[ -z "$reply" || $reply == [yY] ]]
        return
    fi

    # Fallback to /dev/tty if stdin is a terminal
    if [ -r /dev/tty ] && [ -w /dev/tty ]; then
        printf "%b" "$prompt_text"
        IFS= read -t 10 -r -n 1 reply < /dev/tty || reply=""
        if [ -n "$reply" ]; then
            printf "%s\n" "$reply"
        else
            printf "\n" > /dev/tty
        fi
    else
        printf "%b" "$prompt_text"
        IFS= read -t 10 -r reply || reply=""
    fi

    [[ -z "$reply" || $reply == [yY] ]]
}

section "watch-ollama v$VERSION installer"
change "Created/ensured directory: $LOG_DIR"
log "Install log: $LOG_FILE"

# ── Clean install ──────────────────────────────────────────────────────────────
section "1. Existing installation check"
if [ -d "$INSTALL_DIR" ]; then
    log "Existing installation found at $INSTALL_DIR."
    if prompt_yes_no "Perform a clean install? Scripts are removed, config files are preserved."; then
        log "Cleaning up old installation (preserving *.conf files)..."
        while IFS= read -r -d '' f; do
            rm -f "$f"
            change "Removed: $f"
        done < <(find "$INSTALL_DIR" -maxdepth 1 -type f ! -name "*.conf" -print0)
    else
        log "Skipping clean-up, proceeding with update..."
    fi
else
    log "No existing installation found."
fi

# ── Create scripts directory ───────────────────────────────────────────────────
section "2. Install files"
if [ ! -d "$INSTALL_DIR" ]; then
    mkdir -p "$INSTALL_DIR"
    change "Created directory: $INSTALL_DIR"
else
    log "Directory already exists: $INSTALL_DIR"
fi

# ── Copy VERSION ───────────────────────────────────────────────────────────────
cp "$PROJECT_ROOT/VERSION" "$INSTALL_DIR/"
change "Copied: VERSION → $INSTALL_DIR/VERSION"

# ── Copy scripts ───────────────────────────────────────────────────────────────
log "Copying scripts from $PROJECT_ROOT/scripts..."
if [ ! -d "$PROJECT_ROOT/scripts" ]; then
    error "Scripts directory not found at $PROJECT_ROOT/scripts"
    exit 1
fi
for script in "$PROJECT_ROOT/scripts/"*; do
    if [ -f "$script" ]; then
        filename=$(basename "$script")
        cp "$script" "$INSTALL_DIR/$filename"
        change "Copied: $filename → $INSTALL_DIR/$filename"
        if [[ "$filename" == *.sh || "$filename" == watch-ollama || "$filename" == *.py ]]; then
            chmod +x "$INSTALL_DIR/$filename"
            change "chmod +x: $INSTALL_DIR/$filename"
        fi
    fi
done

# ── Copy uninstall.sh ──────────────────────────────────────────────────────────
cp "$PROJECT_ROOT/uninstall.sh" "$INSTALL_DIR/uninstall.sh"
change "Copied: uninstall.sh → $INSTALL_DIR/uninstall.sh"
chmod +x "$INSTALL_DIR/uninstall.sh"
change "chmod +x: $INSTALL_DIR/uninstall.sh"

# ── Shell aliases ──────────────────────────────────────────────────────────────
# Installs named aliases for each user-facing command into the shell rc file.
# Replaces any legacy PATH export written by older versions of this installer.
add_aliases() {
    local rc_file="$1"
    local shell_name="$2"

    # Remove any PATH block written by a previous version of this installer
    if grep -qF "# watch-ollama: PATH" "$rc_file" 2>/dev/null; then
        sed -i '/# watch-ollama: PATH/,+1d' "$rc_file"
        change "Removed legacy PATH entry from $rc_file"
    fi

    # Remove existing alias block so we always write a fresh, up-to-date one
    if grep -qF "$ALIAS_MARKER_START" "$rc_file" 2>/dev/null; then
        sed -i "/$ALIAS_MARKER_START/,/$ALIAS_MARKER_END/d" "$rc_file"
        change "Removed outdated alias block from $rc_file"
    fi

    if [ "$shell_name" = "fish" ]; then
        mkdir -p "$(dirname "$rc_file")"
        touch "$rc_file"
        {
            echo ""
            echo "$ALIAS_MARKER_START"
            echo 'alias watch-ollama  "$HOME/.ollama-watch-tool/scripts/watch-ollama"'
            echo 'alias setup-ollama  "$HOME/.ollama-watch-tool/scripts/setup-ollama.sh"'
            echo 'alias switch-gpu    "$HOME/.ollama-watch-tool/scripts/switch-gpu.sh"'
            echo 'alias update-ollama "$HOME/.ollama-watch-tool/scripts/update-ollama.sh"'
            echo 'alias make-modelfile "python3 $HOME/.ollama-watch-tool/scripts/make-modelfile.py"'
            echo 'alias summarize      "python3 $HOME/.ollama-watch-tool/scripts/summarize.py"'
            echo 'alias ollama-report "python3 $HOME/.ollama-watch-tool/scripts/ollama_report.py"'
            echo 'alias ollama-stats  "python3 $HOME/.ollama-watch-tool/scripts/ollama_stats.py"'
            echo 'alias unwatch-ollama "$HOME/.ollama-watch-tool/scripts/uninstall.sh"'
            echo "$ALIAS_MARKER_END"
        } >> "$rc_file"
    else
        {
            echo ""
            echo "$ALIAS_MARKER_START"
            echo "alias watch-ollama='\$HOME/.ollama-watch-tool/scripts/watch-ollama'"
            echo "alias setup-ollama='\$HOME/.ollama-watch-tool/scripts/setup-ollama.sh'"
            echo "alias switch-gpu='\$HOME/.ollama-watch-tool/scripts/switch-gpu.sh'"
            echo "alias update-ollama='\$HOME/.ollama-watch-tool/scripts/update-ollama.sh'"
            echo "alias make-modelfile='python3 \$HOME/.ollama-watch-tool/scripts/make-modelfile.py'"
            echo "alias summarize='python3 \$HOME/.ollama-watch-tool/scripts/summarize.py'"
            echo "alias ollama-report='python3 \$HOME/.ollama-watch-tool/scripts/ollama_report.py'"
            echo "alias ollama-stats='python3 \$HOME/.ollama-watch-tool/scripts/ollama_stats.py'"
            echo "alias unwatch-ollama='\$HOME/.ollama-watch-tool/scripts/uninstall.sh'"
            echo "$ALIAS_MARKER_END"
        } >> "$rc_file"
    fi
    change "Wrote aliases to $rc_file"
}

CURRENT_SHELL="$(basename "$SHELL")"
section "3. Shell aliases"
case "$CURRENT_SHELL" in
    bash)  SHELL_RC="$HOME/.bashrc" ;;
    zsh)   SHELL_RC="$HOME/.zshrc" ;;
    fish)  SHELL_RC="$HOME/.config/fish/config.fish" ;;
    ksh)   SHELL_RC="$HOME/.kshrc" ;;
    *)
        warn "Unknown shell '$CURRENT_SHELL', falling back to ~/.bashrc"
        CURRENT_SHELL="bash"
        SHELL_RC="$HOME/.bashrc"
        ;;
esac
log "Detected shell: $CURRENT_SHELL  →  rc file: $SHELL_RC"
add_aliases "$SHELL_RC" "$CURRENT_SHELL"

# ── systemd service ────────────────────────────────────────────────────────────
section "4. Systemd service"
if [ -d "$SYSTEMD_DIR" ]; then
    if [ -f "$PROJECT_ROOT/systemd/$SERVICE_FILE" ]; then
        log "Installing/Updating systemd service..."
        sed -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
            -e "s|__USER__|$USER|g" \
            "$PROJECT_ROOT/systemd/$SERVICE_FILE" | sudo tee "$SYSTEMD_DIR/$SERVICE_FILE" > /dev/null
        change "Wrote: $SYSTEMD_DIR/$SERVICE_FILE"
        sudo systemctl daemon-reload
        change "systemctl daemon-reload"

        sudo systemctl enable ollama-watcher
        change "systemctl enable ollama-watcher"

        if sudo systemctl is-active --quiet ollama-watcher; then
            sudo systemctl restart ollama-watcher
            change "systemctl restart ollama-watcher"
        else
            if sudo systemctl start ollama-watcher; then
                change "systemctl start ollama-watcher"
            else
                warn "Could not start ollama-watcher service (will start on next boot)."
            fi
        fi
        log "Service installed and enabled."
    else
        warn "Service file not found at $PROJECT_ROOT/systemd/$SERVICE_FILE — skipping."
    fi
else
    log "systemd not found on this system — skipping service installation."
fi

# ── Environment check ──────────────────────────────────────────────────────────
section "5. Environment check"
if command -v amd-smi >/dev/null 2>&1 || command -v rocm-smi >/dev/null 2>&1; then
    log "AMD GPU tool detected."
    if ! groups | grep -qE "\b(render|video)\b"; then
        warn "You are not in the 'render' or 'video' groups. SMI tools may require elevated permissions for process info."
        warn "Suggested fix: sudo usermod -a -G render,video $USER"
        warn "Note: You must restart your session (logout/login) for group changes to take effect."
    else
        log "User is in appropriate groups (render/video)."
    fi
else
    log "No AMD GPU tools detected. Skipping group check."
fi

section "Installation complete"
printf "%-22s %s\n" "Version:" "v$VERSION"
printf "%-22s %s\n" "Scripts:" "$INSTALL_DIR"
printf "%-22s %s\n" "Aliases:" "$SHELL_RC"
printf "%-22s %s\n" "Install log:" "$LOG_FILE"
echo ""
log "Run 'source $SHELL_RC' or open a new terminal to activate aliases."
