
import re
import curses

ANSI_ESCAPE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[ -/]*[@-~])")
LITERAL_ANSI_ESCAPE_RE = re.compile(r"\\033(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\\033\\)|[ -/]*[@-~])")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ANSI_TOKEN_RE = re.compile(r"(?:\x1b|\\033)\[([0-9;]*)m")

ansi_color_pairs = {}
next_ansi_color_pair = 20

ROLE_MARKERS = {
    "### USER": 1,
    "### ASSISTANT": 2,
    "### SYSTEM": 2,
}

def sanitize_render_text(text):
    text = ANSI_ESCAPE_RE.sub("", text)
    text = LITERAL_ANSI_ESCAPE_RE.sub("", text)
    text = text.replace("\r", "")
    text = text.replace("\t", "    ")
    text = text.replace("<|im_start|>system", "### SYSTEM")
    text = text.replace("<|im_start|>user", "### USER")
    text = text.replace("<|im_start|>assistant", "### ASSISTANT")
    text = text.replace("<|im_start|>", "")
    text = text.replace("<|im_end|>", "")
    text = text.replace("<|endoftext|>", "")
    return CONTROL_CHARS_RE.sub("", text)

def wrap_render_line(line, width):
    if width <= 0: return [line]
    if not line.strip(): return [line] if line else [""]
    prefix = ""
    if width > 4:
        if line.startswith("| "): prefix = "| "
        elif line.startswith("  "):
            ws_match = re.match(r"^(\s+)", line)
            if ws_match: prefix = ws_match.group(1)[:width//3]
    content_width = width - len(prefix)
    if content_width <= 0: return [line[:width]]
    first_segment = line[:width]
    remaining = line[width:]
    if not remaining: return [first_segment]
    segments = [first_segment]
    for i in range(0, len(remaining), content_width):
        segments.append(prefix + remaining[i:i + content_width])
    return segments

def visible_ansi_text(line):
    return ANSI_TOKEN_RE.sub("", line)

def ansi_attr(fg_color, bold):
    global next_ansi_color_pair
    attr = curses.A_BOLD if bold else curses.A_NORMAL
    if fg_color is None: return attr
    if not curses.has_colors() or fg_color >= curses.COLORS: return attr
    pair = ansi_color_pairs.get(fg_color)
    if pair is None:
        pair = next_ansi_color_pair
        next_ansi_color_pair += 1
        try: curses.init_pair(pair, fg_color, -1)
        except curses.error: return attr
        ansi_color_pairs[fg_color] = pair
    return attr | curses.color_pair(pair)

def render_ansi_line(stdscr, y, x, line, max_width):
    fg_color = None
    bold = False
    pos = 0
    draw_x = x
    for match in ANSI_TOKEN_RE.finditer(line):
        chunk = line[pos:match.start()]
        if chunk and draw_x < max_width:
            try: stdscr.addstr(y, draw_x, chunk[:max_width - draw_x], ansi_attr(fg_color, bold))
            except curses.error: pass
            draw_x += len(chunk)
        codes = [int(code) for code in match.group(1).split(";") if code.isdigit()]
        i = 0
        while i < len(codes):
            code = codes[i]
            if code == 0: fg_color = None; bold = False
            elif code == 1: bold = True
            elif code == 38 and i + 2 < len(codes) and codes[i + 1] == 5: fg_color = codes[i + 2]; i += 2
            elif 30 <= code <= 37: fg_color = code - 30
            elif 90 <= code <= 97: fg_color = code - 90 + 8
            elif code == 39: fg_color = None
            i += 1
        pos = match.end()
    chunk = line[pos:]
    if chunk and draw_x < max_width:
        try:
            stdscr.addstr(y, draw_x, chunk[:max_width - draw_x], ansi_attr(fg_color, bold))
            draw_x += len(chunk[:max_width - draw_x])
        except curses.error: pass
    try: stdscr.clrtoeol()
    except curses.error: pass

def get_val_color(val, t1, t2, t3, t4):
    if val < t1: return curses.color_pair(5)
    elif val < t2: return curses.color_pair(2)
    elif val < t3: return curses.color_pair(3)
    elif val < t4: return curses.color_pair(6)
    else: return curses.color_pair(11)

def get_temp_color(temp):
    return get_val_color(temp, 35, 55, 70, 85)

def role_color_pair_for_line(line):
    for marker, color_pair in ROLE_MARKERS.items():
        if line.startswith(marker): return color_pair
    return None

def is_role_marker_line(line):
    return role_color_pair_for_line(line) is not None

def is_separator_line(line):
    return line.startswith("====================") or line.startswith("--------------------------------------------------------------------------------")

def line_opens_thought(line):
    return "<think>" in line or "[THOUGHT]" in line

def line_closes_thought(line):
    return "</think>" in line or "[/THOUGHT]" in line

def render_attr_for_log_line(entry, line, color_pair=None):
    if color_pair is None: color_pair = curses.color_pair
    # Use color pair 7 (often mapped to white/gray in 256-color) for better visibility than 8
    if line.startswith("| "): return color_pair(7)
    role_color_pair = role_color_pair_for_line(line)
    if role_color_pair is not None: return color_pair(role_color_pair) | curses.A_BOLD
    if is_separator_line(line): return color_pair(3) | curses.A_BOLD
    if line_opens_thought(line) or line_closes_thought(line): return color_pair(4) | curses.A_BOLD
    if entry["in_thought"]: return color_pair(4)
    return color_pair(0)
