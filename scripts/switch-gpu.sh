#!/bin/bash

# Utility to switch Ollama between ROCm and Vulkan backends

SWITCH_FILE="/etc/systemd/system/ollama.service.d/20-gpu.conf"

show_usage() {
    echo "Usage: $0 [vulkan|rocm|status]"
    echo "  vulkan: Switch to Vulkan backend"
    echo "  rocm:   Switch to ROCm backend"
    echo "  status: Show current backend"
}

set_gpu() {
    local backend=$1
    local val=$2
    echo "Switching to $backend..."
    sudo mkdir -p "$(dirname "$SWITCH_FILE")"
    printf "[Service]\nEnvironment=\"OLLAMA_VULKAN=$val\"\n" | sudo tee "$SWITCH_FILE" > /dev/null
    sudo systemctl daemon-reload
    sudo systemctl restart ollama
    echo "Ollama restarted with $backend."
}

case "$1" in
    vulkan)
        set_gpu "Vulkan" "1"
        ;;
    rocm)
        set_gpu "ROCm" "0"
        ;;
    status)
        if [ -f "$SWITCH_FILE" ]; then
            grep "OLLAMA_VULKAN" "$SWITCH_FILE"
        else
            echo "Default backend (likely ROCm/Native)"
        fi
        ;;
    *)
        show_usage
        exit 1
        ;;
esac
