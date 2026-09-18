"""Statische Verträge der mitgelieferten Monitor-systemd-Units."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
UNIT_DIR = ROOT / "systemd"
MONITOR_UNITS = (
    "mediamtx-api.service",
    "mediamtx-collector.service",
    "mediamtx-system.service",
)


def unit_section(unit: str, section: str) -> list[str]:
    """Return the directive lines of one unit section without comments."""
    lines: list[str] = []
    current = None
    for raw in (UNIT_DIR / unit).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line
        elif current == section and line and not line.startswith("#"):
            lines.append(line)
    return lines


class MonitorUnitTests(unittest.TestCase):
    def test_api_starts_after_mediamtx_for_the_startup_derivation(self):
        after = [
            line for line in unit_section("mediamtx-api.service", "[Unit]")
            if line.startswith("After=")
        ]
        self.assertEqual(len(after), 1)
        ordered = after[0].removeprefix("After=").split()
        self.assertIn("mediamtx.service", ordered)
        self.assertIn("redis-server.service", ordered)

    def test_api_orders_without_owning_the_mediamtx_lifecycle(self):
        directives = unit_section("mediamtx-api.service", "[Unit]")
        self.assertNotIn(
            "mediamtx.service",
            " ".join(
                line for line in directives
                if line.startswith(("Wants=", "Requires=", "BindsTo=", "PartOf="))
            ),
        )
        self.assertIn("Requires=redis-server.service", directives)

    def test_monitor_units_never_start_or_restart_mediamtx(self):
        for unit in MONITOR_UNITS:
            source = (UNIT_DIR / unit).read_text(encoding="utf-8")
            for directive in ("ExecStart=", "ExecStartPre=", "ExecStopPost="):
                for line in source.splitlines():
                    if line.strip().startswith(directive):
                        self.assertNotIn("mediamtx.service", line, unit)
                        self.assertNotIn("systemctl", line, unit)


if __name__ == "__main__":
    unittest.main()
