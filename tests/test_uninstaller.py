"""Sicherheitsvertrag des Monitor-Uninstallers."""

from pathlib import Path
import os
import unittest


ROOT = Path(__file__).resolve().parents[1]


class UninstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "uninstall.sh").read_text(encoding="utf-8")

    def test_uninstaller_is_executable_bash_script(self):
        self.assertTrue(os.access(ROOT / "uninstall.sh", os.X_OK))
        self.assertTrue(self.source.startswith("#!/bin/bash\nset -Eeuo pipefail\n"))

    def test_monitor_units_are_the_only_units_removed(self):
        services = self.source.split("SERVICES=(", 1)[1].split(")", 1)[0]
        self.assertNotIn("mediamtx.service", services)
        self.assertNotRegex(self.source, r"systemctl\s+(stop|disable).*mediamtx\.service")
        self.assertNotRegex(self.source, r"rm\s+-f.*mediamtx\.service")
        for unit in (
            "mediamtx-api.service",
            "mediamtx-collector.service",
            "mediamtx-system.service",
            "mediamtx-systeminfo.service",
        ):
            self.assertIn(unit, self.source)

    def test_shared_mediamtx_resources_are_not_removed(self):
        self.assertNotIn('rm -f -- "/usr/local/bin/mediamtx"', self.source)
        self.assertNotIn('rm -f -- "/usr/local/etc/mediamtx.yml"', self.source)
        self.assertIn("MediaMTX einschließlich Unit, Binary und Konfiguration blieb erhalten.", self.source)


if __name__ == "__main__":
    unittest.main()
