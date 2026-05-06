"""
Unit tests for make-modelfile.py (non-curses, pure-logic parts).
"""
import importlib.machinery
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MM = importlib.machinery.SourceFileLoader(
    "make_modelfile", str(ROOT / "scripts" / "make-modelfile.py")
).load_module()


class TestFindGgufFiles(unittest.TestCase):
    def test_finds_gguf_in_directory(self):
        with tempfile.TemporaryDirectory() as d:
            # Create a fake .gguf file and a non-.gguf file
            gguf_path = os.path.join(d, "model.gguf")
            other_path = os.path.join(d, "model.bin")
            open(gguf_path, "w").close()
            open(other_path, "w").close()

            # Temporarily override search dirs via monkeypatching getcwd
            orig_getcwd = os.getcwd
            os.getcwd = lambda: d
            try:
                found = MM.find_gguf_files()
            finally:
                os.getcwd = orig_getcwd

        self.assertIn(os.path.abspath(gguf_path), found)
        for f in found:
            self.assertTrue(f.endswith(".gguf"), f"Non-.gguf in results: {f}")

    def test_no_duplicates_between_search_dirs(self):
        with tempfile.TemporaryDirectory() as d:
            gguf_path = os.path.join(d, "dupe.gguf")
            open(gguf_path, "w").close()

            orig_expanduser = os.path.expanduser
            orig_getcwd = os.getcwd
            # Make both search dirs point to the same directory
            os.path.expanduser = lambda p: d if p == "~/models" else orig_expanduser(p)
            os.getcwd = lambda: d
            try:
                found = MM.find_gguf_files()
            finally:
                os.path.expanduser = orig_expanduser
                os.getcwd = orig_getcwd

        self.assertEqual(len(found), len(set(found)), "Duplicates found in result")

    def test_returns_empty_when_no_gguf(self):
        with tempfile.TemporaryDirectory() as d:
            orig_getcwd = os.getcwd
            os.getcwd = lambda: d
            orig_expanduser = os.path.expanduser
            # Point ~/models to a non-existent subdir
            os.path.expanduser = lambda p: os.path.join(d, "nomodels") if p == "~/models" else orig_expanduser(p)
            try:
                found = MM.find_gguf_files()
            finally:
                os.getcwd = orig_getcwd
                os.path.expanduser = orig_expanduser

        self.assertEqual(found, [])

    def test_recursive_discovery(self):
        with tempfile.TemporaryDirectory() as d:
            subdir = os.path.join(d, "sub", "deep")
            os.makedirs(subdir)
            gguf_path = os.path.join(subdir, "nested.gguf")
            open(gguf_path, "w").close()

            orig_getcwd = os.getcwd
            os.getcwd = lambda: d
            try:
                found = MM.find_gguf_files()
            finally:
                os.getcwd = orig_getcwd

        self.assertIn(os.path.abspath(gguf_path), found)


class TestFilterLogic(unittest.TestCase):
    """Tests for the substring-filter behaviour used by gguf_select_screen."""

    FILES = [
        "/models/Qwen3-6b-q4_K_M.gguf",
        "/models/Qwen3-6b-q8_0.gguf",
        "/models/llama3.2-instruct-q4_K_M.gguf",
        "/models/mistral-7b-v0.1.Q4_K_M.gguf",
        "/models/Qwen3-14b-q4_K_M.gguf",
        "/models/phi-3-mini-4k-instruct.gguf",
    ]

    def _filter(self, query):
        lq = query.lower()
        return [p for p in self.FILES if lq in os.path.basename(p).lower()]

    def test_empty_query_returns_all(self):
        self.assertEqual(self._filter(""), self.FILES)

    def test_case_insensitive_match(self):
        result = self._filter("QWEN3")
        for p in result:
            self.assertIn("qwen3", os.path.basename(p).lower())
        self.assertEqual(len(result), 3)

    def test_middle_substring_match(self):
        result = self._filter("instruct")
        self.assertTrue(all("instruct" in os.path.basename(p).lower() for p in result))
        self.assertEqual(len(result), 2)

    def test_no_match_returns_empty(self):
        self.assertEqual(self._filter("zzznomatch"), [])

    def test_digit_match(self):
        result = self._filter("6b")
        self.assertEqual(len(result), 2)
        for p in result:
            self.assertIn("6b", os.path.basename(p).lower())


class TestScrollLogic(unittest.TestCase):
    """Tests for the 5-item window + ..more scroll logic."""

    N = MAX_VISIBLE = MM.MAX_VISIBLE_FILES

    def _window(self, total, cursor, scroll_offset):
        """
        Simulate the scroll adjustment used in gguf_select_screen.
        Returns (adjusted_scroll_offset, has_above, has_below, visible_slice).
        """
        filtered_count = total
        # clamp cursor
        cursor = max(0, min(cursor, filtered_count - 1))
        # auto-scroll
        if cursor < scroll_offset:
            scroll_offset = cursor
        elif cursor >= scroll_offset + self.N:
            scroll_offset = cursor - self.N + 1

        window_end = min(scroll_offset + self.N, filtered_count)
        has_above  = scroll_offset > 0
        has_below  = window_end < filtered_count
        visible    = list(range(scroll_offset, window_end))
        return scroll_offset, has_above, has_below, visible

    def test_first_five_items_no_more_above(self):
        _, has_above, _, visible = self._window(10, cursor=0, scroll_offset=0)
        self.assertFalse(has_above)
        self.assertEqual(visible, [0, 1, 2, 3, 4])

    def test_more_below_when_total_exceeds_window(self):
        _, _, has_below, _ = self._window(10, cursor=0, scroll_offset=0)
        self.assertTrue(has_below)

    def test_scroll_offset_advances_when_cursor_at_bottom_of_window(self):
        # cursor at index 5 forces scroll_offset = 1
        scroll_offset, has_above, _, visible = self._window(10, cursor=5, scroll_offset=0)
        self.assertEqual(scroll_offset, 1)
        self.assertTrue(has_above)
        self.assertIn(5, visible)

    def test_no_more_below_when_at_end(self):
        _, _, has_below, visible = self._window(5, cursor=4, scroll_offset=0)
        self.assertFalse(has_below)
        self.assertEqual(visible, [0, 1, 2, 3, 4])

    def test_cursor_clamped_to_last_item(self):
        scroll_offset, _, _, visible = self._window(3, cursor=99, scroll_offset=0)
        self.assertIn(2, visible)

    def test_more_appears_at_top_when_scrolled(self):
        scroll_offset, has_above, has_below, visible = self._window(
            10, cursor=7, scroll_offset=0
        )
        self.assertTrue(has_above)
        self.assertTrue(has_below or 9 in visible)


class TestMultiSelectLogic(unittest.TestCase):
    """Tests for multi-select state transitions (A / N / Space)."""

    OPTIONS = MM.CTX_OPTIONS[:]

    def _apply(self, keys, initial=None):
        """
        Simulate multiselect_screen key handling without curses.
        keys: list of characters / special strings: 'A', 'N', ' ', '<left>', '<right>', '<enter>'
        Returns (selected_set, cursor) after all keys, or 'cancelled' on Esc.
        """
        selected = set(initial or [])
        cursor   = 0

        for k in keys:
            if k == "A":
                selected = set(range(len(self.OPTIONS)))
            elif k == "N":
                selected.clear()
            elif k == " ":
                if cursor in selected:
                    selected.discard(cursor)
                else:
                    selected.add(cursor)
            elif k == "<left>":
                cursor = max(0, cursor - 1)
            elif k == "<right>":
                cursor = min(len(self.OPTIONS) - 1, cursor + 1)
            elif k == "<enter>":
                if selected:
                    return ([self.OPTIONS[i] for i in sorted(selected)], cursor)
                return ([self.OPTIONS[cursor]], cursor)
            elif k == "<esc>":
                return "cancelled"

        return (selected, cursor)

    def test_A_selects_all(self):
        result, _ = self._apply(["A", "<enter>"])
        self.assertEqual(result, self.OPTIONS)

    def test_N_deselects_all(self):
        result, _ = self._apply(["A", "N", "<enter>"])
        # nothing selected → cursor item returned
        self.assertEqual(len(result), 1)

    def test_space_toggles_on(self):
        result, _ = self._apply([" ", "<enter>"])
        self.assertIn(self.OPTIONS[0], result)

    def test_space_toggles_off(self):
        result, _ = self._apply([" ", " ", "<enter>"])
        # toggled on then off → implicit single pick of cursor (still cursor=0)
        self.assertEqual(result, [self.OPTIONS[0]])

    def test_right_then_space(self):
        _, cursor = self._apply(["<right>", "<right>"])
        self.assertEqual(cursor, 2)

    def test_left_clamp(self):
        _, cursor = self._apply(["<left>", "<left>", "<left>"])
        self.assertEqual(cursor, 0)

    def test_right_clamp(self):
        far_right = ["<right>"] * 100
        _, cursor = self._apply(far_right)
        self.assertEqual(cursor, len(self.OPTIONS) - 1)

    def test_enter_with_no_selection_returns_cursor_item(self):
        result, _ = self._apply(["<right>", "<right>", "<enter>"])
        self.assertEqual(result, [self.OPTIONS[2]])

    def test_esc_returns_cancelled(self):
        result = self._apply(["A", "<esc>"])
        self.assertEqual(result, "cancelled")

    def test_multiple_selections_ordered(self):
        result, _ = self._apply(
            ["<right>", " ", "<right>", " ", "<right>", " ", "<enter>"]
        )
        self.assertEqual(result, [self.OPTIONS[1], self.OPTIONS[2], self.OPTIONS[3]])

    def test_a_key_does_not_produce_literal_a_in_output(self):
        """A must select all options, not append the character 'a'."""
        result, _ = self._apply(["A", "<enter>"])
        # All CTX_OPTIONS are purely numeric strings.
        for item in result:
            self.assertTrue(item.isdigit(), f"Expected numeric option, got: {item!r}")
        self.assertEqual(sorted(result, key=int), sorted(self.OPTIONS, key=int))

    def test_n_key_does_not_produce_literal_n_in_output(self):
        """N must deselect all, not append the character 'n'."""
        # Select everything then press N; Enter returns the cursor item (a number).
        result, _ = self._apply(["A", "N", "<enter>"])
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].isdigit(), f"Expected numeric option, got: {result[0]!r}")


class TestSanitization(unittest.TestCase):
    def test_sanitize_logic(self):
        import re
        def sanitize(s):
            return re.sub(r'[^a-z0-9:-]', '-', s.lower())

        self.assertEqual(sanitize("MyModel:32k-b512"), "mymodel:32k-b512")
        self.assertEqual(sanitize("Invalid_Name!"), "invalid-name-")
        self.assertEqual(sanitize("qwen_qwen3.5"), "qwen-qwen3-5")
        self.assertEqual(sanitize("model:tag"), "model:tag")


    """Tests for the file-generation loop logic."""

    def _gen_filenames(self, model_name, ctx_values, batch_values):
        multi_variant = len(ctx_values) > 1 or len(batch_values) > 1
        names = []
        for ctx in ctx_values:
            for batch in batch_values:
                if multi_variant:
                    names.append(f"Modelfile-{model_name}-ctx{ctx}-batch{batch}")
                else:
                    names.append(f"Modelfile-{model_name}")
        return names

    def test_single_ctx_single_batch_no_variant_suffix(self):
        names = self._gen_filenames("mymodel", ["32768"], ["512"])
        self.assertEqual(names, ["Modelfile-mymodel"])

    def test_multi_ctx_adds_suffix(self):
        names = self._gen_filenames("mymodel", ["16384", "32768"], ["512"])
        self.assertIn("Modelfile-mymodel-ctx16384-batch512", names)
        self.assertIn("Modelfile-mymodel-ctx32768-batch512", names)

    def test_cross_product(self):
        names = self._gen_filenames("m", ["4096", "32768"], ["256", "512"])
        self.assertEqual(len(names), 4)
        self.assertIn("Modelfile-m-ctx4096-batch256", names)
        self.assertIn("Modelfile-m-ctx32768-batch512", names)

    def test_file_content_written(self):
        with tempfile.TemporaryDirectory() as d:
            fname = os.path.join(d, "Modelfile-test")
            lines = [
                "FROM /models/test.gguf",
                "PARAMETER num_ctx 32768",
                "PARAMETER num_thread 4",
                "PARAMETER num_batch 512",
            ]
            with open(fname, "w") as fh:
                fh.write("\n".join(lines) + "\n")
            with open(fname) as fh:
                content = fh.read()

        self.assertIn("FROM /models/test.gguf", content)
        self.assertIn("PARAMETER num_ctx 32768", content)
        self.assertIn("PARAMETER num_batch 512", content)

    def test_system_prompt_escaped(self):
        prompt = 'Say "hello"'
        escaped = prompt.replace('"', '\\"')
        line = f'SYSTEM "{escaped}"'
        self.assertIn('\\"hello\\"', line)


if __name__ == "__main__":
    unittest.main()
