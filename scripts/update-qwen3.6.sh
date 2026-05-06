#!/bin/bash
# Interactive Qwen3.6 modelfile generator.
#
# 1. Searches the filesystem for .gguf files and presents a picker
#    (fzf dropdown when available, numbered list otherwise).
# 2. Checkbox-style multi-select for num_ctx and num_batch values.
# 3. Creates a stable symlink under gguf-links/ pointing to the chosen
#    GGUF file; all generated modelfiles reference that symlink via FROM.
# 4. Generates one .modelfile per chosen (ctx, batch) combination and
#    registers each variant with ollama.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$SCRIPT_DIR/Qwen3.6.template"
LINKS_DIR="$SCRIPT_DIR/gguf-links"

[[ -f "$TEMPLATE" ]] || { echo "ERROR: $TEMPLATE not found" >&2; exit 1; }

# ── Parameter options ─────────────────────────────────────────────────────────
CTX_LABELS=(64k   32k   16k)
CTX_VALUES=(65536 32768 16384)
BATCH_OPTIONS=(256 1024)

# ── 1. Discover .gguf files (prune virtual/network filesystems) ───────────────
echo "Searching for .gguf files..."
PRUNE_PATHS=(/proc /sys /dev /run /snap /boot /media /mnt /tmp)
PRUNE_ARGS=()
for p in "${PRUNE_PATHS[@]}"; do
    PRUNE_ARGS+=(-path "$p" -prune -o)
done

# Search the whole filesystem; virtual/noisy paths are pruned above.
# Permission errors are silently discarded via stderr redirection.
mapfile -t GGUF_FILES < <(
    find / "${PRUNE_ARGS[@]}" -name "*.gguf" -print 2>/dev/null | sort
)

if [[ ${#GGUF_FILES[@]} -eq 0 ]]; then
    echo "No .gguf files found on this system." >&2
    exit 1
fi

# ── 2. GGUF picker ────────────────────────────────────────────────────────────
pick_gguf() {
    if command -v fzf &>/dev/null; then
        printf '%s\n' "${GGUF_FILES[@]}" \
            | fzf --prompt="Select GGUF > " --height=40% --reverse
    else
        echo ""
        echo "Available .gguf files:"
        for i in "${!GGUF_FILES[@]}"; do
            printf "  %3d)  %s\n" "$((i+1))" "${GGUF_FILES[$i]}"
        done
        while true; do
            read -rp "Enter number [1-${#GGUF_FILES[@]}]: " n
            if [[ "$n" =~ ^[0-9]+$ ]] && (( n >= 1 && n <= ${#GGUF_FILES[@]} )); then
                echo "${GGUF_FILES[$((n-1))]}"
                return
            fi
            echo "  Invalid choice, try again."
        done
    fi
}

GGUF_PATH=$(pick_gguf)
[[ -n "$GGUF_PATH" ]] || { echo "No file selected." >&2; exit 1; }
echo "Selected: $GGUF_PATH"

# ── 3. Checkbox multi-select helper ──────────────────────────────────────────
# Populates global CHECKBOX_RESULT array.
# Usage: checkbox_select "Title" item1 item2 ...
checkbox_select() {
    local title="$1"; shift
    local items=("$@")
    local -a toggled
    # Default: all options selected
    for i in "${!items[@]}"; do toggled[$i]=1; done

    while true; do
        echo ""
        echo "$title"
        echo "  Toggle: enter number(s)  |  'a' select all  |  'n' clear all  |  ENTER confirm"
        for i in "${!items[@]}"; do
            local mark="[x]"; [[ ${toggled[$i]} -eq 0 ]] && mark="[ ]"
            printf "  %d) %s  %s\n" "$((i+1))" "$mark" "${items[$i]}"
        done
        read -rp "  Choice: " input
        case "$input" in
            '') break ;;
            a)  for i in "${!items[@]}"; do toggled[$i]=1; done ;;
            n)  for i in "${!items[@]}"; do toggled[$i]=0; done ;;
            *)
                for n in $input; do
                    if [[ "$n" =~ ^[0-9]+$ ]] && (( n >= 1 && n <= ${#items[@]} )); then
                        local idx=$((n-1))
                        toggled[$idx]=$(( 1 - toggled[$idx] ))
                    fi
                done
                ;;
        esac
    done

    CHECKBOX_RESULT=()
    for i in "${!items[@]}"; do
        [[ ${toggled[$i]} -eq 1 ]] && CHECKBOX_RESULT+=("${items[$i]}")
    done
}

# ── 4. Pick ctx and batch values ──────────────────────────────────────────────
checkbox_select "Select num_ctx values:" "${CTX_LABELS[@]}"
SEL_CTX_LABELS=("${CHECKBOX_RESULT[@]}")
[[ ${#SEL_CTX_LABELS[@]} -gt 0 ]] || { echo "No ctx values selected." >&2; exit 1; }

checkbox_select "Select num_batch values:" "${BATCH_OPTIONS[@]}"
SEL_BATCH=("${CHECKBOX_RESULT[@]}")
[[ ${#SEL_BATCH[@]} -gt 0 ]] || { echo "No batch values selected." >&2; exit 1; }

# ── 5. Create stable symlink for selected GGUF ───────────────────────────────
mkdir -p "$LINKS_DIR"
GGUF_LINK="$LINKS_DIR/$(basename "$GGUF_PATH")"
ln -sf "$GGUF_PATH" "$GGUF_LINK"
echo "Symlink: $GGUF_LINK → $GGUF_PATH"

# Derive a model base name from the GGUF filename
MODEL_BASE=$(basename "$GGUF_PATH" .gguf | tr '[:upper:]' '[:lower:]' | tr ' ' '-')

# ── 6. Generate modelfiles and register variants with ollama ──────────────────
TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

echo ""
echo "Generating modelfile variants and registering with ollama..."
for label in "${SEL_CTX_LABELS[@]}"; do
    ctx=""
    for i in "${!CTX_LABELS[@]}"; do
        [[ "${CTX_LABELS[$i]}" == "$label" ]] && ctx="${CTX_VALUES[$i]}" && break
    done

    for batch in "${SEL_BATCH[@]}"; do
        outfile="$SCRIPT_DIR/Qwen3.6.${label}_batch_${batch}.modelfile"

        # Substitute placeholders from template
        sed \
            -e "s/{num_ctx}/${ctx}/g" \
            -e "s/{num_batch}/${batch}/g" \
            "$TEMPLATE" > "$outfile"

        # Final modelfile: symlink-based FROM + parameters
        {
            echo "FROM $GGUF_LINK"
            cat "$outfile"
        } > "$TMPFILE"

        variant="${MODEL_BASE}:${label}_batch_${batch}"
        echo "  Creating $variant ..."
        if ! ollama create "$variant" -f "$TMPFILE"; then
            echo "  WARNING: failed to create $variant" >&2
        fi
    done
done

echo ""
echo "Models updated. Restarting services..."
sudo systemctl restart ollama ollama-watcher --no-pager
echo "Services restarted."
