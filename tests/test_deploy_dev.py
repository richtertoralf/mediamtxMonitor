"""Tests for the controlled development deployment script."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest


REPOSITORY_DIR = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = REPOSITORY_DIR / "devtools/deploy-dev.sh"
MONITOR_UNITS = (
    "mediamtx-api.service",
    "mediamtx-collector.service",
    "mediamtx-system.service",
)


class DeployDevTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.install_dir = self.temp_dir / "installation"
        self.service_dir = self.temp_dir / "systemd"
        self.fake_bin = self.temp_dir / "fake-bin"
        self.command_log = self.temp_dir / "commands.log"
        self.fake_bin.mkdir()
        self.service_dir.mkdir()
        self._copy_deployable_application()
        for unit in MONITOR_UNITS:
            shutil.copy2(REPOSITORY_DIR / "systemd" / unit, self.service_dir / unit)
        (self.service_dir / "mediamtx.service").write_text(
            "local MediaMTX unit\n", encoding="utf-8"
        )
        self._write_executable(
            self.fake_bin / "sudo",
            "#!/usr/bin/env bash\nset -euo pipefail\nexec \"$@\"\n",
        )
        self._write_executable(
            self.fake_bin / "systemctl",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'systemctl %s\n' "$*" >> "$FAKE_LOG"
[[ "$1" != "is-active" ]] || printf 'active\n'
""",
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "FAKE_LOG": str(self.command_log),
                "MEDIAMTX_MONITOR_INSTALL_DIR": str(self.install_dir),
                "MEDIAMTX_MONITOR_SERVICE_DIR": str(self.service_dir),
                "PATH": f"{self.fake_bin}:{self.env['PATH']}",
            }
        )

    def _copy_deployable_application(self) -> None:
        shutil.copytree(REPOSITORY_DIR / "bin", self.install_dir / "bin")
        shutil.copytree(REPOSITORY_DIR / "static", self.install_dir / "static")
        (self.install_dir / "config").mkdir()
        shutil.copy2(
            REPOSITORY_DIR / "config/collector.yaml",
            self.install_dir / "config/collector.yaml",
        )
        shutil.copy2(REPOSITORY_DIR / "VERSION", self.install_dir / "VERSION")

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _run(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(DEPLOY_SCRIPT), *arguments],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_unchanged_units_do_not_trigger_deployment(self) -> None:
        result = self._run("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Keine deploybaren Änderungen gefunden.", result.stdout)
        self.assertNotIn("--- systemd/", result.stdout)
        self.assertFalse(self.command_log.exists())

    def test_dry_run_reports_changed_unit_without_modifying_local_files(self) -> None:
        api_unit = self.service_dir / "mediamtx-api.service"
        api_unit.write_text("ExecStart=python bin/mediamtx_api.py\n", encoding="utf-8")
        original_api_unit = api_unit.read_bytes()
        mediamtx_unit = self.service_dir / "mediamtx.service"
        original_mediamtx_unit = mediamtx_unit.read_bytes()
        collector_config = self.install_dir / "config/collector.yaml"
        original_collector_config = collector_config.read_bytes()

        result = self._run("--dry-run")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--- systemd/", result.stdout)
        self.assertIn("mediamtx-api.service", result.stdout)
        self.assertNotIn("mediamtx-collector.service\n", result.stdout)
        self.assertNotIn("mediamtx-system.service\n", result.stdout)
        self.assertIn("Dry-Run: Es wurden keine Dateien verändert.", result.stdout)
        self.assertEqual(api_unit.read_bytes(), original_api_unit)
        self.assertEqual(mediamtx_unit.read_bytes(), original_mediamtx_unit)
        self.assertEqual(collector_config.read_bytes(), original_collector_config)
        self.assertFalse(self.command_log.exists())

    def test_deployment_installs_changed_unit_reloads_and_restarts(self) -> None:
        api_unit = self.service_dir / "mediamtx-api.service"
        api_unit.write_text("ExecStart=python bin/mediamtx_api.py\n", encoding="utf-8")
        mediamtx_unit = self.service_dir / "mediamtx.service"
        original_mediamtx_unit = mediamtx_unit.read_bytes()
        collector_config = self.install_dir / "config/collector.yaml"
        original_collector_config = collector_config.read_bytes()

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            api_unit.read_bytes(),
            (REPOSITORY_DIR / "systemd/mediamtx-api.service").read_bytes(),
        )
        self.assertEqual(stat.S_IMODE(api_unit.stat().st_mode), 0o644)
        self.assertEqual(mediamtx_unit.read_bytes(), original_mediamtx_unit)
        self.assertEqual(collector_config.read_bytes(), original_collector_config)
        log = self.command_log.read_text(encoding="utf-8")
        self.assertEqual(log.count("systemctl daemon-reload\n"), 1)
        self.assertIn(
            "systemctl restart mediamtx-api mediamtx-collector mediamtx-system",
            log,
        )
        self.assertNotIn("mediamtx.service", log)
        self.assertIn("Dev-Deployment abgeschlossen.", result.stdout)


if __name__ == "__main__":
    unittest.main()
