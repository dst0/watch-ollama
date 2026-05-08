
import subprocess
import curses

class SelectionManager:
    def __init__(self):
        self.active = False
        self.start = None  # (raw_idx, segment_off, char_pos)
        self.end = None    # (raw_idx, segment_off, char_pos)

    def is_pos_in_selection(self, raw_idx, seg_off, char_pos):
        if not self.start or not self.end: return False
        s, e = sorted([self.start, self.end])
        (s_raw, s_off, s_char) = s
        (e_raw, e_off, e_char) = e
        if raw_idx < s_raw or raw_idx > e_raw: return False
        if raw_idx == s_raw:
            if seg_off < s_off: return False
            if seg_off == s_off and char_pos < s_char: return False
        if raw_idx == e_raw:
            if seg_off > e_off: return False
            if seg_off == e_off and char_pos > e_char: return False
        return True

    def get_selected_text(self, log_indexer):
        if not self.start or not self.end: return ""
        s, e = sorted([self.start, self.end])
        raw_lines = log_indexer.get_lines(s[0], e[0] - s[0] + 1)
        if not raw_lines: return ""
        # Simplified: just return full lines for now
        return "\n".join(raw_lines)

    def copy_to_clipboard(self, text):
        for cmd in [['xclip', '-selection', 'clipboard'], ['wl-copy'], ['xsel', '--clipboard', '--input']]:
            try:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                process.communicate(input=text.encode('utf-8'))
                if process.returncode == 0: return True
            except Exception: continue
        return False

    def clear(self):
        self.active = False
        self.start = None
        self.end = None
