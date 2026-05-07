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
        text = TUI.sanitize_render_text("\x1b[31m<|im_start|>assistant\tok\r\x00<|endoftext|>")

        self.assertEqual(text, "### ASSISTANT    ok")

    def test_tui_sanitizes_literal_ansi_sequences_before_rendering(self):
        text = TUI.sanitize_render_text("\\033[38;5;51mWATCH\\033[0m")

        self.assertEqual(text, "WATCH")

    def test_tui_gets_visible_text_from_literal_ansi_header_line(self):
        text = TUI.visible_ansi_text("\\033[38;5;51mWATCH\\033[0m")

        self.assertEqual(text, "WATCH")

    def test_tui_wraps_long_sanitized_lines(self):
        self.assertEqual(TUI.wrap_render_line("abcdef", 3), ["abc", "def"])

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

        self.assertEqual(TUI.sanitize_render_text(code), code)

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
        self.assertEqual(TUI.role_color_pair_for_line("### USER"), 1)
        self.assertEqual(TUI.role_color_pair_for_line("### ASSISTANT"), 2)
        self.assertEqual(TUI.role_color_pair_for_line("### SYSTEM"), 2)
        self.assertIsNone(TUI.role_color_pair_for_line("USER: quoted chat history"))
        self.assertIsNone(TUI.role_color_pair_for_line("ASSISTANT: quoted chat history"))

    def test_tui_chat_history_content_uses_default_color(self):
        self.assertEqual(
            TUI.render_attr_for_log_line(
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
        scroll_pos, auto_scroll, changed, smi_changed = TUI.apply_input(
            [curses.KEY_UP, curses.KEY_UP, curses.KEY_DOWN],
            scroll_pos=50,
            auto_scroll=False,
            log_line_count=100,
            log_h=10,
        )

        self.assertTrue(changed)
        self.assertFalse(auto_scroll)
        self.assertEqual(scroll_pos, 47)

    def test_tui_scroll_down_at_bottom_does_not_auto_resume_if_paused(self):
        # Initial state: at bottom, but paused (auto_scroll=False)
        scroll_pos, auto_scroll, changed, smi_changed = TUI.apply_input(
            [curses.KEY_DOWN],
            scroll_pos=90,
            auto_scroll=False,
            log_line_count=100,
            log_h=10,
        )

        self.assertFalse(auto_scroll)
        self.assertEqual(scroll_pos, 90)
        self.assertFalse(changed)

    def test_tui_scroll_down_to_hit_bottom_resumes_follow(self):
        # Initial state: not at bottom, paused
        scroll_pos, auto_scroll, changed, smi_changed = TUI.apply_input(
            [curses.KEY_DOWN],
            scroll_pos=88, # max_scroll is 90, SCROLL_LINE_STEP is 3
            auto_scroll=False,
            log_line_count=100,
            log_h=10,
        )

        # Hits bottom (91 -> 90), so it SHOULD resume
        self.assertTrue(auto_scroll)
        self.assertEqual(scroll_pos, 90)
        self.assertTrue(changed)

    def test_tui_startup_logo_has_fixed_minimum_duration(self):
        self.assertEqual(TUI.STARTUP_LOGO_SECONDS, 2.0)

    def test_line_is_in_thought_bounds_check(self):
        log_snapshot = ["<think>", "thought content", "</think>", "normal line"]
        
        # In thought (index 1 is "thought content")
        self.assertTrue(TUI.line_is_in_thought(1, log_snapshot))
        
        # Out of thought (index 3 is "normal line")
        self.assertFalse(TUI.line_is_in_thought(3, log_snapshot))
        
        # Out of bounds (positive) - should not crash and return False
        self.assertFalse(TUI.line_is_in_thought(4, log_snapshot))
        
        # Out of bounds (negative) - should not crash and return False
        self.assertFalse(TUI.line_is_in_thought(-1, log_snapshot))

    def test_relative_index_calculation_logic(self):
        # This mirrors the logic added to main
        total_count = 20005
        log_snapshot = ["line"] * 20000 # maxlen
        first_abs_idx = total_count - len(log_snapshot) # 5
        
        # First line in snapshot has abs_idx 5
        abs_idx = 5
        rel_idx = abs_idx - first_abs_idx
        self.assertEqual(rel_idx, 0)
        self.assertEqual(log_snapshot[rel_idx], "line")
        
        # Last line in snapshot has abs_idx 20004
        abs_idx = 20004
        rel_idx = abs_idx - first_abs_idx
        self.assertEqual(rel_idx, 19999)
        self.assertEqual(log_snapshot[rel_idx], "line")


if __name__ == "__main__":
    unittest.main()
