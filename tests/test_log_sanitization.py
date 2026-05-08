import importlib.machinery
import pathlib
import curses
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
WATCHER = importlib.machinery.SourceFileLoader(
    "ollama_watcher", str(ROOT / "scripts" / "ollama_watcher.py")
).load_module()
TUI = importlib.machinery.SourceFileLoader(
    "watch_ollama_tui", str(ROOT / "scripts" / "watch-ollama")
).load_module()
UI = importlib.machinery.SourceFileLoader(
    "ui_utils", str(ROOT / "scripts" / "ui_utils.py")
).load_module()
from unittest.mock import MagicMock


class LogSanitizationTests(unittest.TestCase):
    def test_decoded_text_removes_chatml_artifacts_and_controls(self):
        text = WATCHER.sanitize_decoded_text(
            "<|im_start|><|im_start|>hello\r\x00<|im_end|><|endoftext|>"
        )

        self.assertEqual(text, "hello")

    def test_format_text_preserves_think_markers(self):
        text = WATCHER.format_text("<|im_start|>assistant<think>plan</think><|im_end|>")

        self.assertIn("### ASSISTANT", text)
        self.assertIn("<think>plan</think>", text)

    def test_prompt_without_assistant_marker_needs_generated_marker(self):
        prompt = WATCHER.format_text("<|im_start|>userhello<|im_end|>")

        self.assertFalse(WATCHER.prompt_ends_with_assistant_marker(prompt))

    def test_prompt_with_assistant_marker_does_not_need_generated_marker(self):
        prompt = WATCHER.format_text("<|im_start|>userhello<|im_end|><|im_start|>assistant")

        self.assertTrue(WATCHER.prompt_ends_with_assistant_marker(prompt))

    def test_format_text_keeps_prompt_content_and_role_boundaries_visible(self):
        prompt = WATCHER.format_text(
            "<|im_start|>userHello<|im_end|><|im_start|>assistantHi<|im_end|>"
        )

        self.assertEqual(prompt, "### USER\nHello\n\n### ASSISTANT\nHi")
        self.assertFalse(WATCHER.prompt_ends_with_assistant_marker(prompt))

    def test_tui_sanitizes_control_sequences_before_rendering(self):
        text = UI.sanitize_render_text("\x1b[31m<|im_start|>assistant\tok\r\x00<|endoftext|>")

        self.assertEqual(text, "### ASSISTANT    ok")

    def test_tui_sanitizes_literal_ansi_sequences_before_rendering(self):
        text = UI.sanitize_render_text("\\033[38;5;51mWATCH\\033[0m")

        self.assertEqual(text, "WATCH")

    def test_tui_gets_visible_text_from_literal_ansi_header_line(self):
        text = UI.visible_ansi_text("\\033[38;5;51mWATCH\\033[0m")

        self.assertEqual(text, "WATCH")

    def test_tui_wraps_long_sanitized_lines(self):
        self.assertEqual(UI.wrap_render_line("abcdef", 3), ["abc", "def"])

    def test_watcher_sanitizer_preserves_html_css_and_code(self):
        code = (
            "<div class=\"box\">Hello</div>\n"
            "<style>.box { color: red; }</style>\n"
            "if (a < b && b > c) { return '<tag>'; }"
        )

        self.assertEqual(WATCHER.sanitize_decoded_text(code), code)

    def test_tui_sanitizer_preserves_html_css_and_code(self):
        code = (
            "<div class=\"box\">Hello</div>\n"
            "<style>.box { color: red; }</style>\n"
            "if (a < b && b > c) { return '<tag>'; }"
        )

        self.assertEqual(UI.sanitize_render_text(code), code)

    def test_error_lines_render_once_per_error_key(self):
        TUI.error_messages.clear()

        try:
            TUI.set_error("ollama", "\x1b[31mOllama down\r")
            TUI.set_error("ollama", "\x1b[31mOllama down\r")

            self.assertEqual(TUI.get_error_lines(80), ["Ollama down"])

            TUI.set_error("ollama", None)
            self.assertEqual(TUI.get_error_lines(80), [])
        finally:
            TUI.error_messages.clear()

    def test_tui_only_normalized_role_markers_drive_colors(self):
        self.assertEqual(UI.role_color_pair_for_line("### USER"), 1)
        self.assertEqual(UI.role_color_pair_for_line("### ASSISTANT"), 2)
        self.assertEqual(UI.role_color_pair_for_line("### SYSTEM"), 2)
        self.assertIsNone(UI.role_color_pair_for_line("USER: quoted chat history"))
        self.assertIsNone(UI.role_color_pair_for_line("ASSISTANT: quoted chat history"))

    def test_tui_chat_history_content_uses_default_color(self):
        self.assertEqual(
            UI.render_attr_for_log_line(
                {"in_thought": False}, "normal prompt content", color_pair=lambda n: n
            ),
            0,
        )

    def test_tui_collects_all_pending_input(self):
        class FakeScreen:
            def __init__(self, keys):
                self.keys = list(keys)

            def getch(self):
                if self.keys:
                    return self.keys.pop(0)
                return -1

        self.assertEqual(
            TUI.collect_input(FakeScreen([curses.KEY_UP, curses.KEY_DOWN])),
            [curses.KEY_UP, curses.KEY_DOWN],
        )

    def test_tui_scroll_direction_can_reverse_without_waiting_for_backlog(self):
        # apply_input(stdscr, keys, scroll_pos, scroll_offset, auto_scroll, log_h, render_width, smi_lines, visible_log_window)
        TUI.log_indexer = MagicMock()
        TUI.log_indexer.__len__.return_value = 100
        TUI.log_indexer.get_line.return_value = "line"
        
        scroll_pos, scroll_offset, auto_scroll, changed, smi_changed, quit_req = TUI.apply_input(
            None, [curses.KEY_UP, curses.KEY_UP, curses.KEY_DOWN],
            scroll_pos=50, scroll_offset=0, auto_scroll=False,
            log_h=10, render_width=80, smi_lines=10, visible_log_window=[]
        )

        self.assertTrue(changed)
        self.assertFalse(auto_scroll)
        # SCROLL_LINE_STEP is 3. 2 Ups = -6, 1 Down = +3. Total = -3.
        # 50 - 6 + 3 = 47.
        self.assertEqual(scroll_pos, 47)

    def test_tui_scroll_down_at_bottom_does_not_auto_resume_if_paused(self):
        TUI.log_indexer = MagicMock()
        TUI.log_indexer.__len__.return_value = 100
        TUI.log_indexer.get_line.return_value = "line"
        
        # At bottom (99,0)
        scroll_pos, scroll_offset, auto_scroll, changed, smi_changed, quit_req = TUI.apply_input(
            None, [curses.KEY_DOWN],
            scroll_pos=99, scroll_offset=0, auto_scroll=False,
            log_h=10, render_width=80, smi_lines=10, visible_log_window=[]
        )

        self.assertFalse(auto_scroll)
        self.assertEqual(scroll_pos, 99)
        self.assertFalse(changed)

    def test_tui_scroll_down_to_hit_bottom_resumes_follow(self):
        TUI.log_indexer = MagicMock()
        TUI.log_indexer.__len__.return_value = 100
        TUI.log_indexer.get_line.return_value = "line"
        
        # Near bottom. SCROLL_LINE_STEP is 3. 
        # If we are at 98, one KEY_DOWN takes us to 99 and sets auto_scroll=True.
        # When auto_scroll=True, scroll_pos is recalculated via find_scroll_start_for_bottom(log_h=10)
        # 100 - 10 = 90.
        scroll_pos, scroll_offset, auto_scroll, changed, smi_changed, quit_req = TUI.apply_input(
            None, [curses.KEY_DOWN],
            scroll_pos=98, scroll_offset=0, auto_scroll=False,
            log_h=10, render_width=80, smi_lines=10, visible_log_window=[]
        )

        self.assertTrue(auto_scroll)
        self.assertEqual(scroll_pos, 90)
        self.assertTrue(changed)

    def test_tui_startup_logo_has_fixed_minimum_duration(self):
        self.assertEqual(TUI.STARTUP_LOGO_SECONDS, 2.0)

    def test_line_is_in_thought_bounds_check(self):
        TUI.thought_cache.clear()
        log_indexer = MagicMock()
        TUI.log_indexer = log_indexer
        lines = ["<think>", "thought content", "</think>", "normal line"]
        log_indexer.get_line.side_effect = lambda i: lines[i] if 0 <= i < len(lines) else ""

        # Test scan back logic
        self.assertTrue(TUI.line_is_in_thought(1))

        
        # Out of thought (index 3 is "normal line")
        self.assertFalse(TUI.line_is_in_thought(3))
        
        # Out of bounds (positive) - should return False because loop won't find <think>
        self.assertFalse(TUI.line_is_in_thought(10))
        
        # Out of bounds (negative) - should return False
        self.assertFalse(TUI.line_is_in_thought(-1))

    def test_relative_index_calculation_logic(self):
        # This test was checking old maxlen logic. 
        # In new architecture, we use absolute indices directly.
        pass


if __name__ == "__main__":
    unittest.main()
