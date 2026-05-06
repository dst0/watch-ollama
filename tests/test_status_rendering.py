import importlib.machinery
import pathlib
import unittest
from unittest.mock import patch, MagicMock
import json

ROOT = pathlib.Path(__file__).resolve().parents[1]
TUI = importlib.machinery.SourceFileLoader(
    "watch_ollama_tui", str(ROOT / "scripts" / "watch-ollama")
).load_module()

class StatusRenderingTests(unittest.TestCase):
    def test_get_val_color_thresholds(self):
        # Mock color_pair_func to return the index passed to it
        cp = lambda n: n
        
        # Blue (Cold) < 35
        self.assertEqual(TUI.get_val_color(30, 35, 55, 70, 85, cp), 5)
        # Green (Optimal) < 55
        self.assertEqual(TUI.get_val_color(40, 35, 55, 70, 85, cp), 2)
        # Yellow (Warm) < 70
        self.assertEqual(TUI.get_val_color(60, 35, 55, 70, 85, cp), 3)
        # Orange (Hot-Warm) < 85
        self.assertEqual(TUI.get_val_color(77, 35, 55, 70, 85, cp), 6)
        # Red (Hot) >= 85
        self.assertEqual(TUI.get_val_color(90, 35, 55, 70, 85, cp), 11)

    def test_get_temp_color_uses_correct_thresholds(self):
        cp = lambda n: n
        # 77 should be Orange (6)
        self.assertEqual(TUI.get_temp_color(77, cp), 6)
        # 30 should be Blue (5)
        self.assertEqual(TUI.get_temp_color(30, cp), 5)

    @patch('subprocess.check_output')
    def test_get_system_temps_finds_max_temperature(self, mock_sensors):
        # Mock 'sensors -j' output with multiple sensors, one of which is 77C
        sensors_data = {
            "k10temp-pci-00c3": {
                "Adapter": "PCI adapter",
                "Tctl": {"temp1_input": 45.0},
                "Tdie": {"temp2_input": 40.0}
            },
            "amdgpu-pci-0300": {
                "Adapter": "PCI adapter",
                "edge": {"temp1_input": 77.0},
                "junction": {"temp2_input": 82.0}
            },
            "nvme-pci-0100": {
                "Adapter": "PCI adapter",
                "Composite": {"temp1_input": 35.0}
            }
        }
        mock_sensors.return_value = json.dumps(sensors_data)
        
        max_temp, temps = TUI.get_system_temps()
        
        # Should pick up 82.0 as the max temp
        self.assertEqual(max_temp, 82.0)
        # SSD should be in the 'temps' list (others are hidden)
        self.assertIn("SSD:35°C", temps)

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=MagicMock)
    def test_get_cpu_temp_fallback(self, mock_open, mock_exists):
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "55000\n"
        
        temp = TUI.get_cpu_temp()
        self.assertEqual(temp, 55.0)

    def test_ansi_color_pair_start_does_not_overwrite_static_pairs(self):
        # Pre-allocated curses pairs used by get_val_color / get_temp_color are
        # 1..6 and 11. The ANSI dynamic allocator must start above 11 so it
        # never overwrites the RED pair (11) used for hot temperatures.
        self.assertGreater(TUI.next_ansi_color_pair, 11)

if __name__ == "__main__":
    unittest.main()
