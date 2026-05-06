#!/usr/bin/env python3
"""
Interactive curses-based Ollama Modelfile generator.

Flow:
  1. Type-to-search GGUF file selector
  2. Model name prompt
  3. Context-length multi-select  (left/right + space/A/N)
  4. Thread-count prompt
  5. Batch-size multi-select      (left/right + space/A/N)
  6. Optional system prompt
  7. Generates one Modelfile per (ctx × batch) combination
  8. Interactive Ollama import (ollama create)
  9. Restart services
"""
import curses
import os
import sys
import subprocess

# ── Preset option lists ────────────────────────────────────────────────────────
CTX_OPTIONS = ["2048", "4096", "8192", "16384", "32768", "65536", "131072"]
BATCH_OPTIONS = ["128", "256", "512", "1024", "2048"]

# Number of GGUF results shown at one time (exclusive of ..more indicators)
MAX_VISIBLE_FILES = 5


# ── File discovery ─────────────────────────────────────────────────────────────

def find_gguf_files():
    """Return sorted list of absolute .gguf paths found under ~/models and cwd."""
    search_dirs = [os.path.expanduser("~/models"), os.getcwd()]
    seen   = set()
    result = []
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for root, _, files in os.walk(d):
            for f in sorted(files):
                if f.endswith(".gguf"):
                    path = os.path.abspath(os.path.join(root, f))
                    if path not in seen:
                        seen.add(path)
                        result.append(path)
    return result


# ── Low-level curses helpers ───────────────────────────────────────────────────

def _safe_addstr(stdscr, y, x, text, attr=0):
    max_y, max_x = stdscr.getmaxyx()
    if y < 0 or y >= max_y or x < 0 or x >= max_x:
        return
    text = text[: max_x - x]
    if text:
        try:
            stdscr.addstr(y, x, text, attr)
        except curses.error:
            pass


def _draw_title(stdscr, text):
    max_y, max_x = stdscr.getmaxyx()
    _safe_addstr(stdscr, 0, 0, text[:max_x - 1], curses.A_BOLD)


# ── Screen 1: GGUF file selector ───────────────────────────────────────────────

def gguf_select_screen(stdscr, all_files):
    """
    Interactive GGUF file selector.

    Layout (rows):
      0  title / key hints
      1  "Search: <query>_"
      2  (blank separator)
      3  ..more  (only when scroll_offset > 0)
      3/4  up to MAX_VISIBLE_FILES file rows
      last+1  ..more  (only when items remain below window)

    Returns the selected absolute path, or None on Esc.
    """
    curses.curs_set(1)
    query         = ""
    cursor_idx    = 0   # index within *filtered* list
    scroll_offset = 0   # index of first shown item in filtered list

    while True:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        # ── Filter ────────────────────────────────────────────────────────────
        lq = query.lower()
        filtered = [p for p in all_files if lq in os.path.basename(p).lower()]

        # Clamp cursor
        if filtered:
            cursor_idx = max(0, min(cursor_idx, len(filtered) - 1))
            # Auto-scroll so cursor stays in window
            if cursor_idx < scroll_offset:
                scroll_offset = cursor_idx
            elif cursor_idx >= scroll_offset + MAX_VISIBLE_FILES:
                scroll_offset = cursor_idx - MAX_VISIBLE_FILES + 1
        else:
            cursor_idx    = 0
            scroll_offset = 0

        # ── Header ────────────────────────────────────────────────────────────
        _draw_title(stdscr, "Select GGUF file")
        _safe_addstr(stdscr, 1, 0,
                     "Type to search  \u2191\u2193 navigate  Enter confirm  Esc quit",
                     curses.A_DIM)
        search_prefix = "Search: "
        _safe_addstr(stdscr, 2, 0, search_prefix + query)
        # blinking cursor after query
        cursor_display_x = len(search_prefix) + len(query)
        if cursor_display_x < max_x - 1:
            _safe_addstr(stdscr, 2, cursor_display_x, "_", curses.A_BLINK)

        # ── List area ─────────────────────────────────────────────────────────
        list_start_row = 4
        row = list_start_row

        has_above = scroll_offset > 0
        window_end = min(scroll_offset + MAX_VISIBLE_FILES, len(filtered))
        has_below  = window_end < len(filtered)

        # "..more" at top when scrolled down
        if has_above:
            _safe_addstr(stdscr, row, 2, "..more", curses.A_DIM)
            row += 1

        # Visible file items
        for i in range(scroll_offset, window_end):
            if row >= max_y - 1:
                break
            label = os.path.basename(filtered[i])
            prefix = "> " if i == cursor_idx else "  "
            attr   = curses.A_REVERSE if i == cursor_idx else 0
            _safe_addstr(stdscr, row, 0, (prefix + label)[: max_x - 1], attr)
            row += 1

        # "..more" at bottom when items remain below
        if has_below and row < max_y - 1:
            _safe_addstr(stdscr, row, 2, "..more", curses.A_DIM)
            row += 1

        if not filtered:
            _safe_addstr(stdscr, list_start_row, 2,
                         "(no matches)" if query else "(no .gguf files found)",
                         curses.A_DIM)

        stdscr.refresh()

        # ── Input ─────────────────────────────────────────────────────────────
        key = stdscr.getch()

        if key in (27,):                                   # Esc
            return None
        elif key in (10, 13, curses.KEY_ENTER):            # Enter
            if filtered:
                return filtered[cursor_idx]
        elif key == curses.KEY_UP:
            if filtered and cursor_idx > 0:
                cursor_idx -= 1
        elif key == curses.KEY_DOWN:
            if filtered and cursor_idx < len(filtered) - 1:
                cursor_idx += 1
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            query = query[:-1]
            cursor_idx    = 0
            scroll_offset = 0
        elif 32 <= key <= 126:                             # printable
            query += chr(key)
            cursor_idx    = 0
            scroll_offset = 0


# ── Screen 2: horizontal multi-select ─────────────────────────────────────────

def multiselect_screen(stdscr, title, options, default_cursor=0):
    """
    Horizontal multi-select widget.

    Controls:
      ← →   move cursor
      Space  toggle selection of current option
      A      select all
      N      deselect all (none selected)
      Enter  confirm  (if nothing selected, selects cursor item)
      Esc    cancel → returns None

    Returns list of selected option strings, or None on Esc.
    """
    curses.curs_set(0)
    cursor  = default_cursor
    selected = set()

    while True:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        _draw_title(stdscr, title)
        _safe_addstr(stdscr, 1, 0,
                     "\u2190\u2192 navigate  Space select/deselect  A=all  N=none  Enter confirm",
                     curses.A_DIM)

        # Render options horizontally, wrapping if needed
        x = 0
        y = 3
        for i, opt in enumerate(options):
            # "[*] label" or "[ ] label"
            marker = "*" if i in selected else " "
            label  = f"[{marker}] {opt}"
            pad    = "  "  # gap between options

            # Wrap to next row if it won't fit
            if x > 0 and x + len(label) > max_x - 1:
                y += 1
                x  = 0
            if y >= max_y - 1:
                break

            attr = curses.A_REVERSE if i == cursor else 0
            if i in selected:
                attr |= curses.A_BOLD
            _safe_addstr(stdscr, y, x, label, attr)
            x += len(label) + len(pad)

        # Hint row below options
        hint_y = y + 2
        if selected:
            chosen = [options[i] for i in sorted(selected)]
            _safe_addstr(stdscr, hint_y, 0,
                         f"Selected: {', '.join(chosen)}", curses.A_DIM)
        else:
            _safe_addstr(stdscr, hint_y, 0,
                         "(nothing selected – Enter will pick highlighted)",
                         curses.A_DIM)

        stdscr.refresh()

        key = stdscr.getch()

        if key == 27:                                          # Esc
            return None
        elif key in (10, 13, curses.KEY_ENTER):                # Enter
            if selected:
                return [options[i] for i in sorted(selected)]
            return [options[cursor]]                           # implicit single pick
        elif key == curses.KEY_LEFT:
            cursor = max(0, cursor - 1)
        elif key == curses.KEY_RIGHT:
            cursor = min(len(options) - 1, cursor + 1)
        elif key == ord(" "):
            if cursor in selected:
                selected.discard(cursor)
            else:
                selected.add(cursor)
        elif key in (ord("a"), ord("A")):
            selected = set(range(len(options)))
        elif key in (ord("n"), ord("N")):
            selected.clear()


# ── Screen 3: simple text-input prompt ────────────────────────────────────────

def input_prompt(stdscr, prompt_lines, default=""):
    """
    Single-line text input.

    prompt_lines: list of strings shown above the input field.
    Returns entered text (or default if empty), or None on Esc.
    """
    curses.curs_set(1)
    buf = ""

    while True:
        max_y, max_x = stdscr.getmaxyx()
        stdscr.erase()

        for row, line in enumerate(prompt_lines):
            if row >= max_y - 2:
                break
            _safe_addstr(stdscr, row, 0, line)

        input_row = len(prompt_lines) + 1
        prefix = f"[{default}]: " if default else ": "
        _safe_addstr(stdscr, input_row, 0, prefix + buf)
        # position curses cursor
        cx = min(len(prefix) + len(buf), max_x - 1)
        try:
            stdscr.move(input_row, cx)
        except curses.error:
            pass

        stdscr.refresh()

        key = stdscr.getch()

        if key == 27:                                          # Esc
            return None
        elif key in (10, 13, curses.KEY_ENTER):                # Enter
            return buf if buf else default
        elif key in (curses.KEY_BACKSPACE, 127, 8):
            buf = buf[:-1]
        elif 32 <= key <= 126:
            buf += chr(key)


# ── Main TUI flow ──────────────────────────────────────────────────────────────

def _run(stdscr):
    curses.start_color()
    curses.use_default_colors()
    try:
        curses.init_pair(1, curses.COLOR_CYAN,  -1)
        curses.init_pair(2, curses.COLOR_GREEN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
    except curses.error:
        pass
    stdscr.keypad(True)
    stdscr.nodelay(False)   # blocking input – this is a wizard, not a TUI loop

    # ── Step 1: discover files ────────────────────────────────────────────────
    all_files = find_gguf_files()
    if not all_files:
        stdscr.erase()
        _draw_title(stdscr, "No .gguf files found")
        _safe_addstr(stdscr, 2, 0,
                     "Place .gguf files in ~/models or the current directory,")
        _safe_addstr(stdscr, 3, 0, "then run make-modelfile again.")
        _safe_addstr(stdscr, 5, 0, "Press any key to exit.")
        stdscr.refresh()
        stdscr.getch()
        return

    # ── Step 2: select GGUF file ──────────────────────────────────────────────
    model_path = gguf_select_screen(stdscr, all_files)
    if model_path is None:
        return

    # ── Step 3: model name ────────────────────────────────────────────────────
    base_default = os.path.splitext(os.path.basename(model_path))[0]
    model_name = input_prompt(
        stdscr,
        [f"Selected: {model_path}", "", "Enter model name:"],
        default=base_default,
    )
    if model_name is None:
        return
    model_name = model_name.strip() or base_default

    # ── Step 4: context-length multi-select ───────────────────────────────────
    ctx_values = multiselect_screen(
        stdscr, "Context length variants:", CTX_OPTIONS, default_cursor=4
    )
    if ctx_values is None:
        return

    # ── Step 5: thread count ──────────────────────────────────────────────────
    threads = input_prompt(stdscr, ["Number of threads:"], default="4")
    if threads is None:
        return
    threads = threads.strip() or "4"

    # ── Step 6: batch-size multi-select ───────────────────────────────────────
    batch_values = multiselect_screen(
        stdscr, "Batch size variants:", BATCH_OPTIONS, default_cursor=2
    )
    if batch_values is None:
        return

    # ── Step 7: optional system prompt ───────────────────────────────────────
    sys_prompt = input_prompt(
        stdscr,
        ["System prompt (text or path to file, leave empty to skip):"],
        default="",
    )
    if sys_prompt is None:
        sys_prompt = ""
    sys_prompt = sys_prompt.strip()

    # Resolve file-path system prompt once
    sys_prompt_text = ""
    if sys_prompt:
        if os.path.exists(sys_prompt):
            with open(sys_prompt, "r") as fh:
                sys_prompt_text = fh.read()
        else:
            sys_prompt_text = sys_prompt

    # ── Step 8: generate Modelfile(s) ────────────────────────────────────────
    generated = []

    # Load template
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Qwen3.6.template")
    template_content = ""
    if os.path.exists(template_path):
        with open(template_path, "r") as fh:
            template_content = fh.read()
    else:
        # Fallback if template missing (should not happen based on requirements)
        template_content = "PARAMETER num_ctx {num_ctx}\nPARAMETER num_thread {num_thread}\nPARAMETER num_batch {num_batch}\n"

    # Helper to convert context to 'k' format (e.g., 32768 -> 32k)
    def ctx_label(c):
        try:
            val = int(c)
            if val >= 1024:
                return f"{val // 1024}k"
            return str(val)
        except:
            return str(c)

    for ctx in ctx_values:
        for batch in batch_values:
            label = ctx_label(ctx)
            fname = f"Modelfile-{model_name}-{label}-b{batch}"

            # Start with FROM line
            content = f"FROM {model_path}\n"
            
            # Apply template with replacements
            body = template_content.replace("{num_ctx}", str(ctx)) \
                                   .replace("{num_thread}", str(threads)) \
                                   .replace("{num_batch}", str(batch))
            content += body

            if sys_prompt_text:
                # Escape embedded double-quotes
                escaped = sys_prompt_text.replace('"', '\\"')
                content += f'\nSYSTEM "{escaped}"'

            with open(fname, "w") as fh:
                fh.write(content.strip() + "\n")
            generated.append(fname)
    
    # ── Step 9: summary ───────────────────────────────────────────────────────
    curses.curs_set(0)
    stdscr.erase()
    _draw_title(stdscr, f"Generated {len(generated)} Modelfile(s):")
    for i, fname in enumerate(generated):
        _safe_addstr(stdscr, i + 2, 2, fname, curses.A_BOLD)
    
    y_off = len(generated) + 4
    _safe_addstr(stdscr, y_off,     0, "Next step: Import these models into Ollama.")
    _safe_addstr(stdscr, y_off + 1, 2, "This will run 'ollama create' for each file.", curses.A_DIM)
    _safe_addstr(stdscr, y_off + 3, 0, "Press Enter to begin import, or Esc to exit.")
    stdscr.refresh()
    
    while True:
        key = stdscr.getch()
        if key in (10, 13, curses.KEY_ENTER):
            break
        if key in (27, ord('q'), ord('Q')):
            return

    # ── Step 10: Import execution ─────────────────────────────────────────────
    stdscr.erase()
    _draw_title(stdscr, "Importing models to Ollama...")
    _safe_addstr(stdscr, 1, 0, "Please wait, this may take a moment per model.", curses.A_DIM)
    stdscr.refresh()
    
    # Try to find OLLAMA_HOST from ollama.conf if it exists near the script
    env = os.environ.copy()
    conf_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ollama.conf")
    if os.path.exists(conf_path):
        try:
            with open(conf_path, "r") as f:
                for line in f:
                    if line.startswith("OLLAMA_HOST="):
                        env["OLLAMA_HOST"] = line.split("=", 1)[1].strip().strip('"').strip("'")
        except:
            pass

    for i, fname in enumerate(generated):
        max_y, max_x = stdscr.getmaxyx()
        
        # Derive o_name from filename, but use a colon for the tag part
        # Modelfile-{model_name}-{label}-b{batch}
        name_parts = fname.replace("Modelfile-", "").split("-")
        if len(name_parts) >= 3:
            # The last two parts are label and batch (e.g., 64k and b256)
            tag = "-".join(name_parts[-2:])
            base = "-".join(name_parts[:-2])
            o_name = f"{base}:{tag}".lower()
        else:
            o_name = fname.replace("Modelfile-", "").lower()

        # Simple scroll/wrap protection
        row = i + 3
        if row >= max_y - 2:
            _safe_addstr(stdscr, max_y - 2, 0, "... more models imported (see ollama list)", curses.A_DIM)
            break

        _safe_addstr(stdscr, row, 2, f"Creating {o_name}...", curses.A_DIM)
        stdscr.refresh()
        
        try:
            res = subprocess.run(["ollama", "create", o_name, "-f", fname], 
                                 capture_output=True, text=True, env=env)
            
            # Clear the "Creating..." line
            stdscr.move(row, 0)
            stdscr.clrtoeol()
            
            if res.returncode == 0:
                _safe_addstr(stdscr, row, 2, f"\u2713 {o_name}", curses.color_pair(2))
            else:
                _safe_addstr(stdscr, row, 2, f"\u2717 {o_name} (failed)", curses.color_pair(3))
                # Show error message on next line if space allows
                if row + 1 < max_y - 2:
                    err_msg = res.stderr.strip().split('\n')[-1]
                    _safe_addstr(stdscr, row + 1, 4, err_msg[:max_x-6], curses.A_DIM)
        except Exception as e:
            _safe_addstr(stdscr, row, 2, f"\u2717 {o_name} (error: {str(e)})", curses.color_pair(3))
        
        stdscr.refresh()

    # Update header to show completion
    stdscr.move(0, 0)
    stdscr.clrtoeol()
    stdscr.move(1, 0)
    stdscr.clrtoeol()
    _draw_title(stdscr, "Ollama import complete")
    _safe_addstr(stdscr, 1, 0, "All selected models have been processed.", curses.A_DIM)

    # ── Step 11: Restart services ─────────────────────────────────────────────
    _safe_addstr(stdscr, max_y - 3, 0, "Restarting Ollama services...", curses.A_DIM)
    stdscr.refresh()
    try:
        # Run restart in background, suppress output but wait for completion
        subprocess.run(["sudo", "systemctl", "restart", "ollama", "ollama-watcher", "--no-pager"], 
                       capture_output=True, check=False)
        _safe_addstr(stdscr, max_y - 3, 0, "\u2713 Services restarted.          ", curses.color_pair(2))
    except Exception as e:
        _safe_addstr(stdscr, max_y - 3, 0, f"\u2717 Service restart failed: {str(e)}", curses.color_pair(3))

    _safe_addstr(stdscr, max_y - 1, 0, "All tasks complete. Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()


def generate_modelfile():
    curses.wrapper(_run)


if __name__ == "__main__":
    generate_modelfile()
