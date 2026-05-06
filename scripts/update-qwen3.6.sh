#!/bin/bash
# Batch update script for all Qwen3.6 models to include tool support

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/Qwen3.6.template"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi

# Get the list of all Qwen3.6 models
MODELS=$(ollama list | grep -i "Qwen3.6" | awk '{print $1}')

if [[ -z "$MODELS" ]]; then
    echo "No Qwen3.6 models found."
    exit 0
fi

TMPFILE=$(mktemp)
MODELFILE=$(mktemp)
trap 'rm -f "$TMPFILE" "$MODELFILE"' EXIT

for model in $MODELS; do
    echo "Updating $model with official template and parameters..."

    # Extract existing FROM line
    if ! ollama show --modelfile "$model" > "$MODELFILE" 2>/dev/null; then
        echo "WARNING: could not fetch modelfile for $model, skipping." >&2
        continue
    fi
    FROM_LINE=$(grep "^FROM" "$MODELFILE")

    # Create new Modelfile: FROM line + base template
    echo "$FROM_LINE" > "$TMPFILE"
    cat "$TEMPLATE" >> "$TMPFILE"

    # Create/Overwrite the model
    if ! ollama create "$model" -f "$TMPFILE"; then
        echo "WARNING: failed to create model $model, skipping." >&2
    fi
done

echo "Models updated. Restarting services..."
sudo systemctl restart ollama ollama-watcher --no-pager
echo "Services restarted."
