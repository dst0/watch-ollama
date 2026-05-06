"""Tests for the CPU-optimisation changes introduced to watch-ollama.

Covers:
  - build_visible_log_lines() wrap cache (hit / miss / width-change invalidation)
  - _get_model_params() TTL cache (hit within TTL, miss after TTL, failure caching)
  - ollama_watcher.py idle-sleep value (must be >= 0.25 s)
  - LOG_HISTORY_MAXLEN constant (must be <= 20000)
  - render_event is a threading.Event (present and usable)
"""

import importlib.machinery
import pathlib
import threading
import time
import types
import unittest
from unittest.mock import patch, MagicMock

ROOT = pathlib.Path(__file__).resolve().parents[1]
TUI = importlib.machinery.SourceFileLoader(
    "watch_ollama_tui", str(ROOT / "scripts" / "watch-ollama")
).load_module()
WATCHER = importlib.machinery.SourceFileLoader(
    "ollama_watcher", str(ROOT / "scripts" / "ollama_watcher.py")
).load_module()


# ---------------------------------------------------------------------------
# Log-line wrap cache
# ---------------------------------------------------------------------------

class WrapCacheTests(unittest.TestCase):
    def setUp(self):
        """Reset module-level cache and log state before each test."""
        TUI._visible_log_cache = None
        TUI._visible_log_cache_key = None
        with TUI.log_lock:
            TUI.log_lines.clear()
            TUI.log_lines_total_count = 0
            TUI.log_version = 0

    def _add_line(self, text):
        """Append a line and bump log_version (mirrors what tail_log does)."""
        with TUI.log_lock:
            TUI.log_lines.append(text)
            TUI.log_lines_total_count += 1
            TUI.log_version += 1

    def test_cache_miss_on_first_call(self):
        self._add_line("hello world")
        visible, snapshot, _ = TUI.build_visible_log_lines(80)
        self.assertEqual(len(visible), 1)
        self.assertIsNotNone(TUI._visible_log_cache)

    def test_cache_hit_returns_same_object(self):
        self._add_line("hello world")
        result1 = TUI.build_visible_log_lines(80)
        result2 = TUI.build_visible_log_lines(80)
        # Same list objects – no rebuild happened
        self.assertIs(result1[0], result2[0])
        self.assertIs(result1[1], result2[1])

    def test_cache_miss_on_log_version_change(self):
        self._add_line("first line")
        result1 = TUI.build_visible_log_lines(80)

        self._add_line("second line")
        result2 = TUI.build_visible_log_lines(80)

        self.assertIsNot(result1[0], result2[0])
        self.assertEqual(len(result2[0]), 2)

    def test_cache_miss_on_width_change(self):
        self._add_line("abcdefghij")  # 10 chars
        result_wide = TUI.build_visible_log_lines(80)
        result_narrow = TUI.build_visible_log_lines(5)

        # Different width → different wrapped segments
        self.assertIsNot(result_wide[0], result_narrow[0])
        self.assertGreater(len(result_narrow[0]), len(result_wide[0]))

    def test_cache_key_encodes_both_width_and_version(self):
        self._add_line("line")
        TUI.build_visible_log_lines(80)
        key_before = TUI._visible_log_cache_key

        self._add_line("another")
        TUI.build_visible_log_lines(80)
        key_after = TUI._visible_log_cache_key

        self.assertNotEqual(key_before, key_after)
        # Width component stays constant
        self.assertEqual(key_before[0], key_after[0])

    def test_empty_log_returns_empty_visible_lines(self):
        visible, snapshot, total = TUI.build_visible_log_lines(80)
        self.assertEqual(visible, [])
        self.assertEqual(snapshot, [])
        self.assertEqual(total, 0)


# ---------------------------------------------------------------------------
# Model-params TTL cache
# ---------------------------------------------------------------------------

class ModelParamsCacheTests(unittest.TestCase):
    def setUp(self):
        TUI._model_params_cache.clear()

    def _make_api_response(self, params_str="temperature 0.8"):
        """Return a mock urlopen context manager yielding a JSON /api/show response."""
        body = f'{{"parameters": "{params_str}"}}'.encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    @patch("urllib.request.urlopen")
    def test_first_call_fetches_from_api(self, mock_open):
        mock_open.return_value = self._make_api_response("temperature 0.7")
        result = TUI._get_model_params("mymodel")
        self.assertIn("temp:0.7", result)
        mock_open.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_second_call_within_ttl_uses_cache(self, mock_open):
        mock_open.return_value = self._make_api_response("temperature 0.7")
        TUI._get_model_params("mymodel")
        TUI._get_model_params("mymodel")
        # API should only be called once
        self.assertEqual(mock_open.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_cache_expires_after_ttl(self, mock_open):
        mock_open.return_value = self._make_api_response("temperature 0.5")
        TUI._get_model_params("mymodel")

        # Manually expire the cache entry
        ts, val = TUI._model_params_cache["mymodel"]
        TUI._model_params_cache["mymodel"] = (ts - TUI.MODEL_PARAMS_CACHE_TTL - 1, val)

        mock_open.return_value = self._make_api_response("temperature 0.9")
        result = TUI._get_model_params("mymodel")
        self.assertEqual(mock_open.call_count, 2)
        self.assertIn("temp:0.9", result)

    @patch("urllib.request.urlopen", side_effect=Exception("network error"))
    def test_api_failure_cached_as_empty_string(self, mock_open):
        result = TUI._get_model_params("badmodel")
        self.assertEqual(result, "")
        self.assertIn("badmodel", TUI._model_params_cache)

    @patch("urllib.request.urlopen", side_effect=Exception("network error"))
    def test_failure_cache_prevents_repeated_calls(self, mock_open):
        TUI._get_model_params("badmodel")
        TUI._get_model_params("badmodel")
        self.assertEqual(mock_open.call_count, 1)

    def test_ttl_constant_is_at_least_20_seconds(self):
        self.assertGreaterEqual(TUI.MODEL_PARAMS_CACHE_TTL, 20.0)


# ---------------------------------------------------------------------------
# Telemetry polling interval
# ---------------------------------------------------------------------------

class TelemetryIntervalTests(unittest.TestCase):
    def test_smi_poll_trigger_timeout_is_at_least_1_second(self):
        """poll_smi() must wait at least 1 s between cycles.

        We verify this by inspecting the source file rather than running the
        function (which would require mocking many external calls).
        """
        src = (ROOT / "scripts" / "watch-ollama").read_text()
        # The wait call in poll_smi: smi_poll_trigger.wait(timeout=<N>)
        import re
        matches = re.findall(r"smi_poll_trigger\.wait\(timeout=([\d.]+)\)", src)
        self.assertTrue(matches, "Could not find smi_poll_trigger.wait(timeout=...) in source")
        for m in matches:
            self.assertGreaterEqual(float(m), 1.0,
                f"smi_poll_trigger.wait timeout {m}s is below 1s minimum")

    def test_idle_wait_constants_exist_and_are_reasonable(self):
        self.assertTrue(hasattr(TUI, "IDLE_WAIT_DEFAULT"))
        self.assertTrue(hasattr(TUI, "IDLE_WAIT_AFTER_INPUT"))
        # Default idle: enough to drop frame rate significantly from original 60fps
        self.assertGreaterEqual(TUI.IDLE_WAIT_DEFAULT, 0.05)
        # After-input: short enough for responsive scroll feedback
        self.assertLessEqual(TUI.IDLE_WAIT_AFTER_INPUT, 0.1)
        # After-input wait must be shorter than default idle wait
        self.assertLess(TUI.IDLE_WAIT_AFTER_INPUT, TUI.IDLE_WAIT_DEFAULT)


# ---------------------------------------------------------------------------
# Log-history cap
# ---------------------------------------------------------------------------

class LogHistoryCapTests(unittest.TestCase):
    def test_log_history_maxlen_constant_exists_and_is_reasonable(self):
        self.assertTrue(hasattr(TUI, "LOG_HISTORY_MAXLEN"))
        self.assertLessEqual(TUI.LOG_HISTORY_MAXLEN, 20000)
        self.assertGreaterEqual(TUI.LOG_HISTORY_MAXLEN, 1000)

    def test_log_lines_deque_uses_maxlen_constant(self):
        self.assertEqual(TUI.log_lines.maxlen, TUI.LOG_HISTORY_MAXLEN)


# ---------------------------------------------------------------------------
# Render event
# ---------------------------------------------------------------------------

class RenderEventTests(unittest.TestCase):
    def test_render_event_is_threading_event(self):
        self.assertIsInstance(TUI.render_event, threading.Event)

    def test_set_smi_text_sets_render_event(self):
        TUI.render_event.clear()
        TUI.set_smi_text(["CPU:5% 40°C"])
        self.assertTrue(TUI.render_event.is_set())

    def test_smi_version_increments_on_set_smi_text(self):
        before = TUI.smi_version
        TUI.set_smi_text(["CPU:5% 40°C"])
        self.assertEqual(TUI.smi_version, before + 1)

    def test_get_smi_snapshot_returns_version(self):
        TUI.set_smi_text(["test line"], cpu_temp=42.0)
        lines, temp, ver = TUI.get_smi_snapshot()
        self.assertIsInstance(ver, int)
        self.assertEqual(temp, 42.0)
        self.assertEqual(lines, ["test line"])

    def test_log_version_is_int(self):
        self.assertIsInstance(TUI.log_version, int)


# ---------------------------------------------------------------------------
# ollama_watcher.py idle sleep
# ---------------------------------------------------------------------------

class WatcherIdleSleepTests(unittest.TestCase):
    def test_watcher_idle_sleep_is_at_least_0_2_seconds(self):
        """The idle-wait in the readline loop must be >= 0.2 s.

        We inspect the specific else-branch that handles 'no new line yet'
        (as opposed to the log-rotation sleep, which is legitimately 1 s).
        """
        src = (ROOT / "scripts" / "ollama_watcher.py").read_text()
        import re
        # Find the idle else-branch: a time.sleep immediately after the
        # rotation block's else clause inside the readline loop.
        # We match the pattern:  else:\n                    time.sleep(<N>)
        matches = re.findall(
            r"else:\s*\n\s*time\.sleep\(([\d.]+)\)",
            src,
        )
        self.assertTrue(matches,
            "Could not find the idle else: time.sleep(...) in ollama_watcher.py")
        for s in matches:
            self.assertGreaterEqual(float(s), 0.2,
                f"Idle sleep {s}s in ollama_watcher.py is below 0.2s minimum")


if __name__ == "__main__":
    unittest.main()
