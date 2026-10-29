"""CPU breakdown, steal time, CPU pressure and hints of the system monitor."""

from collections import namedtuple
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from bin import system_monitor


Times = namedtuple("Times", "user system idle iowait steal")
SETTINGS = {
    "saturation_idle_percent": 5.0,
    "steal_hint_percent": 10.0,
    "pressure_hint_percent": 20.0,
}


class FakeCpuPsutil:
    def __init__(self, cores):
        self.cores = cores
        self.calls = []

    def cpu_times_percent(self, interval=None, percpu=False):
        self.calls.append((interval, percpu))
        return self.cores


class CpuBreakdownTests(unittest.TestCase):
    def breakdown(self, cores, pressure=None):
        fake = FakeCpuPsutil(cores)
        with (
            mock.patch.object(system_monitor, "psutil", fake),
            mock.patch.object(system_monitor, "read_cpu_pressure", return_value=pressure),
        ):
            result = system_monitor.get_cpu_breakdown(SETTINGS)
        # Non-blocking: the window is the time since the previous sample.
        self.assertEqual(fake.calls, [(None, True)])
        return result

    def test_per_core_values_and_separate_steal(self):
        result = self.breakdown([
            Times(40.0, 10.0, 45.0, 5.0, 0.0),
            Times(20.0, 5.0, 60.0, 0.0, 15.0),
        ], pressure={"some_avg10": 3.5, "some_avg60": 1.0})
        self.assertEqual(result["logical_cores"], 2)
        self.assertEqual(result["per_core"][0], {
            "busy": 50.0, "idle": 45.0, "iowait": 5.0, "steal": 0.0,
        })
        # Steal counts as busy (the VM wanted the time) and is shown separately.
        self.assertEqual(result["per_core"][1]["busy"], 40.0)
        self.assertEqual(result["busy_percent"], 45.0)
        self.assertEqual(result["steal_percent"], 7.5)
        self.assertEqual(result["iowait_percent"], 2.5)
        self.assertEqual(result["pressure"], {"some_avg10": 3.5, "some_avg60": 1.0})
        self.assertEqual(result["hints"], [])

    def test_hints_name_saturation_steal_and_pressure(self):
        result = self.breakdown([
            Times(70.0, 10.0, 2.0, 0.0, 18.0),
            Times(80.0, 15.0, 1.0, 0.0, 4.0),
        ], pressure={"some_avg10": 35.0, "some_avg60": 30.0})
        self.assertEqual(result["hints"], ["saturation", "steal", "pressure"])

    def test_one_idle_core_is_no_saturation(self):
        result = self.breakdown([
            Times(95.0, 4.0, 1.0, 0.0, 0.0),
            Times(10.0, 5.0, 85.0, 0.0, 0.0),
        ])
        self.assertNotIn("saturation", result["hints"])
        self.assertIsNone(result["pressure"])


class CpuPressureTests(unittest.TestCase):
    def test_reads_some_averages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "cpu")
            path.write_text(
                "some avg10=12.50 avg60=4.00 avg300=1.00 total=123\n"
                "full avg10=0.00 avg60=0.00 avg300=0.00 total=0\n",
                encoding="utf-8",
            )
            self.assertEqual(
                system_monitor.read_cpu_pressure(path),
                {"some_avg10": 12.5, "some_avg60": 4.0},
            )

    def test_missing_or_broken_pressure_file_is_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(system_monitor.read_cpu_pressure(Path(directory, "fehlt")))
            broken = Path(directory, "cpu")
            broken.write_text("some avg10=x\n", encoding="utf-8")
            self.assertIsNone(system_monitor.read_cpu_pressure(broken))


if __name__ == "__main__":
    unittest.main()
