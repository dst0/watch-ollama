#!/bin/bash
# Batch update script for all Qwen3.6 models to include tool support.
# Generates 6 concrete modelfile variants covering the Cartesian product of:
#   num_ctx  : 65536 (64k), 32768 (32k), 16384 (16k)
#   num_batch: 256, 1024

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/Qwen3.6.template"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: template not found at $TEMPLATE" >&2
    exit 1
fi

# --- Parameter matrix ---
CTX_VALUES=(65536 32768 16384)
CTX_LABELS=(64k   32k   16k)
BATCH_VALUES=(256 1024)

# --- Step 1: Generate 6 concrete modelfile files ---
echo "Generating concrete modelfile variants..."
for i in "${!CTX_VALUES[@]}"; do
    ctx="${CTX_VALUES[$i]}"
    label="${CTX_LABELS[$i]}"
    for batch in "${BATCH_VALUES[@]}"; do
        outfile="$SCRIPT_DIR/Qwen3.6.${label}.batch_${batch}.modelfile"
        sed \
            -e "s/{num_ctx}/${ctx}/g" \
            -e "s/{num_batch}/${batch}/g" \
            "$TEMPLATE" > "$outfile"
        echo "  Generated: $(basename "$outfile")"
    done
done

# --- Step 2: Apply variants to every Qwen3.6 model found in ollama ---
MODELS=$(ollama list | grep -i "Qwen3.6" | awk '{print $1}')

if [[ -z "$MODELS" ]]; then
    echo "No Qwen3.6 models found in ollama; skipping model creation."
    exit 0
fi

TMPFILE=$(mktemp)
MODELFILE=$(mktemp)
trap 'rm -f "$TMPFILE" "$MODELFILE"' EXIT

for model in $MODELS; do
    # Extract existing FROM line (base weights pointer)
    if ! ollama show --modelfile "$model" > "$MODELFILE" 2>/dev/null; then
        echo "WARNING: could not fetch modelfile for $model, skipping." >&2
        continue
    fi
    FROM_LINE=$(grep "^FROM" "$MODELFILE")
    base_model="${model%%:*}"

    for i in "${!CTX_VALUES[@]}"; do
        label="${CTX_LABELS[$i]}"
        for batch in "${BATCH_VALUES[@]}"; do
            variant="${base_model}:${label}-batch_${batch}"
            echo "Creating $variant ..."

            # Build modelfile: FROM line + concrete variant template
            echo "$FROM_LINE" > "$TMPFILE"
            cat "$SCRIPT_DIR/Qwen3.6.${label}.batch_${batch}.modelfile" >> "$TMPFILE"

            if ! ollama create "$variant" -f "$TMPFILE"; then
                echo "WARNING: failed to create model $variant, skipping." >&2
            fi
        done
    done
done

echo "Models updated. Restarting services..."
sudo systemctl restart ollama ollama-watcher --no-pager
echo "Services restarted."
