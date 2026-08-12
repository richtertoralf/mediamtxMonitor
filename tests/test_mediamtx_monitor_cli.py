"""Tests for the installed MediaMTX Monitor command."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPOSITORY_DIR = Path(__file__).resolve().parents[1]
CLI = REPOSITORY_DIR / "mediamtx-monitor"
SERVICES = (
    "mediamtx-api.service",
    "mediamtx-collector.service",
    "mediamtx-system.service",
)


class MediaMTXMonitorCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.install_dir = self.temp_dir / "installation"
        self.cli_path = self.temp_dir / "installed-bin/mediamtx-monitor"
        self.source_dir = self.temp_dir / "source"
        self.fake_bin = self.temp_dir / "fake-bin"
        self.log_file = self.temp_dir / "commands.log"
        self.fake_bin.mkdir()
        self.cli_path.parent.mkdir()
        self._write_executable(
            self.fake_bin / "git",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'git %s\n' "$*" >> "$FAKE_LOG"
destination="${@: -1}"
cp -a "$FAKE_REPOSITORY" "$destination"
""",
        )
        self._write_executable(
            self.fake_bin / "systemctl",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'systemctl %s\n' "$*" >> "$FAKE_LOG"
if [[ "$1" == "is-active" && "${FAIL_SERVICE:-}" == "$2" ]]; then
  printf 'failed\n'
  exit 3
fi
[[ "$1" != "is-active" ]] || printf 'active\n'
""",
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "MEDIAMTX_MONITOR_INSTALL_DIR": str(self.install_dir),
                "MEDIAMTX_MONITOR_CLI_PATH": str(self.cli_path),
                "MEDIAMTX_MONITOR_REPOSITORY_URL": "https://example.invalid/monitor.git",
                "FAKE_REPOSITORY": str(self.source_dir),
                "FAKE_LOG": str(self.log_file),
                "PATH": f"{self.fake_bin}:{self.env['PATH']}",
            }
        )

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _create_installation(self, version: str = "0.1.0") -> None:
        (self.install_dir / "bin").mkdir(parents=True)
        (self.install_dir / "static").mkdir()
        (self.install_dir / "config").mkdir()
        (self.install_dir / "venv/bin").mkdir(parents=True)
        (self.install_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (self.install_dir / "bin/old.py").write_text("old\n", encoding="utf-8")
        (self.install_dir / "static/old.js").write_text("old\n", encoding="utf-8")
        (self.install_dir / "config/collector.yaml").write_text("local: true\n", encoding="utf-8")
        self._write_executable(
            self.install_dir / "venv/bin/python",
            "#!/usr/bin/env bash\nprintf 'python %s\n' \"$*\" >> \"$FAKE_LOG\"\n",
        )

    def _create_source(self, version: str = "0.1.1") -> None:
        (self.source_dir / "bin").mkdir(parents=True)
        (self.source_dir / "static").mkdir()
        (self.source_dir / "config").mkdir()
        (self.source_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (self.source_dir / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
        (self.source_dir / "bin/new.py").write_text("new\n", encoding="utf-8")
        (self.source_dir / "static/new.js").write_text("new\n", encoding="utf-8")
        (self.source_dir / "config/collector.yaml").write_text("upstream: true\n", encoding="utf-8")
        self._write_executable(
            self.source_dir / "mediamtx-monitor",
            "#!/usr/bin/env bash\nprintf 'new cli\n'\n",
        )

    def _run(self, option: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(CLI), option],
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_version_reads_installed_version(self) -> None:
        self._create_installation("2.3.4")
        result = self._run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "MediaMTX Monitor 2.3.4\n")

    def test_upgrade_rejects_missing_installation(self) -> None:
        result = self._run("--upgrade")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No existing MediaMTX Monitor installation found", result.stderr)
        self.assertIn("Run install.sh first", result.stderr)

    def test_same_version_stops_without_changes_or_services(self) -> None:
        self._create_installation()
        self._create_source("0.1.0")
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("already up to date: 0.1.0", result.stdout)
        self.assertNotIn("systemctl", self.log_file.read_text(encoding="utf-8"))

    def test_upgrade_updates_program_dependencies_version_and_services(self) -> None:
        self._create_installation()
        self._create_source()
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.install_dir / "bin/new.py").is_file())
        self.assertFalse((self.install_dir / "bin/old.py").exists())
        self.assertTrue((self.install_dir / "static/new.js").is_file())
        self.assertEqual(
            (self.install_dir / "config/collector.yaml").read_text(encoding="utf-8"),
            "local: true\n",
        )
        self.assertEqual((self.install_dir / "VERSION").read_text(encoding="utf-8"), "0.1.1\n")
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn(f"python -m pip install --disable-pip-version-check -r {self.install_dir}/requirements.txt", log)
        self.assertIn(f"systemctl restart {' '.join(SERVICES)}", log)
        for service in SERVICES:
            self.assertIn(f"systemctl is-active {service}", log)
        self.assertIn("Upgrade complete: 0.1.0 -> 0.1.1", result.stdout)

    def test_upgrade_replaces_installed_cli_and_keeps_it_executable(self) -> None:
        self._create_installation()
        self._create_source()
        self._write_executable(
            self.cli_path,
            "#!/usr/bin/env bash\nprintf 'old cli\n'\n",
        )

        result = self._run("--upgrade")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.cli_path.read_bytes(), (self.source_dir / "mediamtx-monitor").read_bytes())
        self.assertTrue(os.access(self.cli_path, os.X_OK))

    def test_service_failure_does_not_report_success(self) -> None:
        self._create_installation()
        self._create_source()
        self.env["FAIL_SERVICE"] = "mediamtx-collector.service"
        result = self._run("--upgrade")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Service is not active", result.stderr)
        self.assertNotIn("Upgrade complete", result.stdout)

    def test_unknown_option_shows_usage(self) -> None:
        result = self._run("--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown option", result.stderr)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
