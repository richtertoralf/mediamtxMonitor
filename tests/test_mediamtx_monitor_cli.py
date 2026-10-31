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
LEGACY_SERVICE = "mediamtx-systeminfo.service"


class MediaMTXMonitorCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp_dir)
        self.install_dir = self.temp_dir / "installation"
        self.cli_path = self.temp_dir / "installed-bin/mediamtx-monitor"
        self.source_dir = self.temp_dir / "source"
        self.service_dir = self.temp_dir / "systemd"
        self.fake_bin = self.temp_dir / "fake-bin"
        self.log_file = self.temp_dir / "commands.log"
        self.fake_bin.mkdir()
        self.cli_path.parent.mkdir()
        self._write_executable(
            self.fake_bin / "git",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'git %s\n' "$*" >> "$FAKE_LOG"
if [[ "$1" == "-C" && "$3" == "rev-parse" ]]; then
  printf '%s\n' "${FAKE_REVISION:-1111111111111111111111111111111111111111}"
  exit 0
fi
destination="${@: -1}"
cp -a "$FAKE_REPOSITORY" "$destination"
""",
        )
        self._write_executable(
            self.fake_bin / "systemctl",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'systemctl %s\n' "$*" >> "$FAKE_LOG"
if [[ "$1" == "list-unit-files" ]]; then
  legacy_unit="${MEDIAMTX_MONITOR_SERVICE_DIR:?}/$2"
  [[ ! -e "$legacy_unit" && ! -L "$legacy_unit" ]] || printf '%s enabled\n' "$2"
  exit 0
fi
if [[ "$1" == "daemon-reload" && "${FAIL_DAEMON_RELOAD:-}" == "yes" ]]; then
  exit 1
fi
if [[ "$1" == "restart" && "${FAIL_RESTART:-}" == "yes" ]]; then
  exit 1
fi
if [[ "$1" == "disable" && "${FAIL_LEGACY_DISABLE:-}" == "yes" ]]; then
  exit 1
fi
if [[ "$1" == "is-enabled" ]]; then
  if [[ " ${FAKE_DISABLED:-} " == *" $2 "* ]]; then printf 'disabled\n'; exit 1; fi
  printf 'enabled\n'
  exit 0
fi
if [[ "$1" == "is-active" ]]; then
  if [[ " ${FAKE_INACTIVE:-} " == *" $2 "* ]]; then printf 'inactive\n'; exit 3; fi
  # Ein fehlerhafter Dienst fällt erst nach dem Neustart mit der neuen Laufzeit aus.
  if [[ "${FAIL_SERVICE:-}" == "$2" ]] && grep -q '^systemctl restart' "$FAKE_LOG"; then
    printf 'failed\n'
    exit 3
  fi
  printf 'active\n'
fi
""",
        )
        # python3 -m venv ohne Netz: eine venv, deren python jeden Aufruf protokolliert.
        self._write_executable(
            self.fake_bin / "python3",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'python3 %s\n' "$*" >> "$FAKE_LOG"
if [[ "$1" == "-m" && "$2" == "venv" ]]; then
  mkdir -p "$3/bin"
  cat > "$3/bin/python" <<'PYTHON'
#!/usr/bin/env bash
printf '%s %s\n' "$0" "$*" >> "$FAKE_LOG"
[[ "${FAIL_CHECK:-}" != pip || "$*" != "-m pip check" ]] || exit 1
[[ "${FAIL_CHECK:-}" != config || "$*" != *config_check.py* ]] || exit 1
exit 0
PYTHON
  chmod 0755 "$3/bin/python"
  printf '#!%s/bin/python\n' "$3" > "$3/bin/uvicorn"
  exit 0
fi
exec /usr/bin/python3 "$@"
""",
        )
        self.env = os.environ.copy()
        self.env.update(
            {
                "MEDIAMTX_MONITOR_INSTALL_DIR": str(self.install_dir),
                "MEDIAMTX_MONITOR_CLI_PATH": str(self.cli_path),
                "MEDIAMTX_MONITOR_SERVICE_DIR": str(self.service_dir),
                "MEDIAMTX_MONITOR_REPOSITORY_URL": "https://example.invalid/monitor.git",
                "FAKE_REPOSITORY": str(self.source_dir),
                "FAKE_LOG": str(self.log_file),
                "PATH": f"{self.fake_bin}:{self.env['PATH']}",
            }
        )

    def _write_executable(self, path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def _create_installation(self, version: str = "0.1.0", revision: str | None = None) -> None:
        (self.install_dir / "bin").mkdir(parents=True)
        (self.install_dir / "static").mkdir()
        (self.install_dir / "config").mkdir()
        self.service_dir.mkdir()
        (self.install_dir / "venv/bin").mkdir(parents=True)
        (self.install_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        if revision is not None:
            (self.install_dir / "REVISION").write_text(f"{revision}\n", encoding="utf-8")
        (self.install_dir / "bin/old.py").write_text("old\n", encoding="utf-8")
        (self.install_dir / "static/old.js").write_text("old\n", encoding="utf-8")
        (self.install_dir / "config/collector.yaml").write_text("local: true\n", encoding="utf-8")
        (self.temp_dir / "mediamtx.yml").write_text("local mediamtx\n", encoding="utf-8")
        (self.service_dir / "mediamtx.service").write_text(
            "local mediamtx unit\n", encoding="utf-8"
        )
        (self.service_dir / "mediamtx-api.service").write_text(
            "ExecStart=python bin/mediamtx_api.py\n", encoding="utf-8"
        )
        (self.service_dir / "mediamtx-collector.service").write_text(
            "ExecStart=python bin/mediamtx_collector.py\n", encoding="utf-8"
        )
        (self.service_dir / "mediamtx-system.service").write_text(
            "ExecStart=python bin/mediamtx_systeminfo.py\n", encoding="utf-8"
        )
        self._write_executable(
            self.install_dir / "venv/bin/python",
            "#!/usr/bin/env bash\nprintf '%s %s\n' \"$0\" \"$*\" >> \"$FAKE_LOG\"\n",
        )

    def _create_source(self, version: str = "0.1.1") -> None:
        (self.source_dir / "bin").mkdir(parents=True)
        (self.source_dir / "static").mkdir()
        (self.source_dir / "config").mkdir()
        (self.source_dir / "systemd").mkdir()
        (self.source_dir / "VERSION").write_text(f"{version}\n", encoding="utf-8")
        (self.source_dir / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
        (self.source_dir / "bin/new.py").write_text("new\n", encoding="utf-8")
        (self.source_dir / "static/new.js").write_text("new\n", encoding="utf-8")
        (self.source_dir / "config/collector.yaml").write_text("upstream: true\n", encoding="utf-8")
        for service in SERVICES:
            shutil.copy2(REPOSITORY_DIR / "systemd" / service, self.source_dir / "systemd" / service)
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
        self._create_installation(revision="1" * 40)
        self._create_source("0.1.0")
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Installed: 0.1.0 (1111111)", result.stdout)
        self.assertIn("already up to date: 0.1.0 (1111111)", result.stdout)
        self.assertTrue((self.install_dir / "bin/old.py").exists())
        log = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn("python -m pip install", log)
        self.assertNotIn("systemctl disable", log)
        self.assertNotIn("systemctl daemon-reload", log)
        self.assertNotIn("systemctl restart", log)

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
        self.assertRegex(
            log,
            rf"{self.install_dir}\.upgrade-\w+/venv/bin/python -m pip install "
            rf"--disable-pip-version-check -r {self.install_dir}\.upgrade-\w+/requirements.txt",
        )
        self.assertIn("systemctl daemon-reload", log)
        self.assertIn(f"systemctl restart {' '.join(SERVICES)}", log)
        for service in SERVICES:
            self.assertIn(f"systemctl is-active {service}", log)
        self.assertIn(
            "Upgrade complete: 0.1.0 (unknown commit) -> 0.1.1 (1111111)", result.stdout
        )
        self.assertEqual(
            (self.install_dir / "REVISION").read_text(encoding="utf-8"), "1" * 40 + "\n"
        )

    def test_same_version_with_new_commit_updates(self) -> None:
        self._create_installation("0.1.0", revision="a" * 40)
        self._create_source("0.1.0")
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.install_dir / "bin/new.py").is_file())
        self.assertIn("Upgrade complete: 0.1.0 (aaaaaaa) -> 0.1.0 (1111111)", result.stdout)
        self.assertEqual(
            (self.install_dir / "REVISION").read_text(encoding="utf-8"), "1" * 40 + "\n"
        )
        self.assertIn(f"systemctl restart {' '.join(SERVICES)}", self.log_file.read_text())

    def test_unknown_commit_updates_once_then_stops(self) -> None:
        self._create_installation("0.1.0")
        self._create_source("0.1.0")
        first = self._run("--upgrade")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Installed: 0.1.0 (unknown commit)", first.stdout)
        self.assertIn("Upgrade complete", first.stdout)
        second = self._run("--upgrade")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already up to date: 0.1.0 (1111111)", second.stdout)

    def test_invalid_downloaded_commit_aborts_before_changes(self) -> None:
        self._create_installation()
        self._create_source()
        self.env["FAKE_REVISION"] = "not-a-commit"
        result = self._run("--upgrade")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid downloaded commit", result.stderr)
        self.assertTrue((self.install_dir / "bin/old.py").exists())

    def test_version_shows_installed_commit_when_known(self) -> None:
        self._create_installation("2.3.4", revision="0123456789" * 4)
        result = self._run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "MediaMTX Monitor 2.3.4 (0123456)\n")

    def test_upgrade_removes_active_legacy_system_monitor(self) -> None:
        self._create_installation()
        self._create_source()
        legacy_unit = self.service_dir / LEGACY_SERVICE
        legacy_file = self.install_dir / "bin/mediamtx_systeminfo.py"
        legacy_unit.write_text("legacy unit\n", encoding="utf-8")
        legacy_file.write_text("legacy writer\n", encoding="utf-8")

        result = self._run("--upgrade")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(legacy_unit.exists())
        self.assertFalse(legacy_file.exists())
        self.assertFalse((self.install_dir / "bin/old.py").exists())
        self.assertIn(f"Removing legacy service {LEGACY_SERVICE}", result.stdout)
        self.assertIn("Removing legacy file bin/mediamtx_systeminfo.py", result.stdout)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn(f"systemctl disable --now {LEGACY_SERVICE}", log)
        self.assertLess(
            log.index(f"systemctl disable --now {LEGACY_SERVICE}"),
            log.index("systemctl daemon-reload"),
        )
        self.assertIn(f"systemctl restart {' '.join(SERVICES)}", log)
        for service in SERVICES:
            self.assertTrue((self.service_dir / service).is_file())

    def test_upgrade_without_legacy_artifacts_is_quiet_and_idempotent(self) -> None:
        self._create_installation()
        self._create_source()

        first_result = self._run("--upgrade")
        second_result = self._run("--upgrade")

        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        self.assertNotIn("Removing legacy", first_result.stdout)
        self.assertNotIn("Removing legacy", second_result.stdout)
        self.assertFalse((self.install_dir / "bin/old.py").exists())

    def test_upgrade_removes_legacy_file_when_service_is_absent(self) -> None:
        self._create_installation()
        self._create_source()
        legacy_file = self.install_dir / "bin/mediamtx_systeminfo.py"
        legacy_file.write_text("legacy writer\n", encoding="utf-8")

        result = self._run("--upgrade")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(legacy_file.exists())
        log = self.log_file.read_text(encoding="utf-8")
        self.assertNotIn(f"systemctl disable --now {LEGACY_SERVICE}", log)

    def test_inactive_disabled_legacy_service_cleanup_is_idempotent(self) -> None:
        self._create_installation()
        self._create_source()
        legacy_unit = self.service_dir / LEGACY_SERVICE
        legacy_unit.write_text("legacy unit\n", encoding="utf-8")

        first_result = self._run("--upgrade")
        legacy_unit.write_text("legacy unit returned\n", encoding="utf-8")
        second_result = self._run("--upgrade")

        self.assertEqual(first_result.returncode, 0, first_result.stderr)
        self.assertEqual(second_result.returncode, 0, second_result.stderr)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertEqual(log.count(f"systemctl disable --now {LEGACY_SERVICE}\n"), 2)
        self.assertEqual(log.count("systemctl daemon-reload\n"), 2)

    def test_legacy_service_disable_failure_aborts_before_application_update(self) -> None:
        self._create_installation()
        self._create_source()
        (self.service_dir / LEGACY_SERVICE).write_text("legacy unit\n", encoding="utf-8")
        self.env["FAIL_LEGACY_DISABLE"] = "yes"

        result = self._run("--upgrade")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to stop and disable legacy service", result.stderr)
        self.assertFalse((self.install_dir / "bin/new.py").exists())
        self.assertNotIn("Upgrade complete", result.stdout)

    def test_upgrade_migrates_monitor_units_without_touching_local_configuration(self) -> None:
        self._create_installation()
        self._create_source()
        collector_config = self.install_dir / "config/collector.yaml"
        mediamtx_config = self.temp_dir / "mediamtx.yml"
        mediamtx_unit = self.service_dir / "mediamtx.service"

        result = self._run("--upgrade")

        self.assertEqual(result.returncode, 0, result.stderr)
        for service in SERVICES:
            self.assertEqual(
                (self.service_dir / service).read_bytes(),
                (self.source_dir / "systemd" / service).read_bytes(),
            )
        self.assertIn(
            "bin/monitoring_api.py",
            (self.service_dir / "mediamtx-api.service").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "bin/system_monitor.py",
            (self.service_dir / "mediamtx-system.service").read_text(encoding="utf-8"),
        )
        self.assertEqual(mediamtx_unit.read_text(encoding="utf-8"), "local mediamtx unit\n")
        self.assertEqual(collector_config.read_text(encoding="utf-8"), "local: true\n")
        self.assertEqual(mediamtx_config.read_text(encoding="utf-8"), "local mediamtx\n")
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("systemctl daemon-reload", log)
        self.assertIn(f"systemctl restart {' '.join(SERVICES)}", log)

    def test_daemon_reload_failure_does_not_report_success(self) -> None:
        self._create_installation()
        self._create_source()
        self.env["FAIL_DAEMON_RELOAD"] = "yes"

        result = self._run("--upgrade")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to reload systemd units", result.stderr)
        self.assertNotIn("Upgrade complete", result.stdout)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("systemctl daemon-reload", log)
        self.assertNotIn("systemctl restart", log)

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

    def test_restart_failure_does_not_report_success(self) -> None:
        self._create_installation()
        self._create_source()
        self.env["FAIL_RESTART"] = "yes"

        result = self._run("--upgrade")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Failed to restart monitor services", result.stderr)
        self.assertNotIn("Upgrade complete", result.stdout)

    def _siblings(self) -> list[str]:
        return sorted(p.name for p in self.temp_dir.iterdir() if p.name.startswith("installation."))

    def test_new_runtime_is_built_and_checked_beside_the_installation(self) -> None:
        self._create_installation(revision="a" * 40)
        self._create_source()
        (self.install_dir / ".cache").mkdir()
        (self.install_dir / ".cache/pip-marker").write_text("cache\n", encoding="utf-8")
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertRegex(log, rf"python3 -m venv {self.install_dir}\.upgrade-\w+/venv")
        self.assertRegex(log, r"\.upgrade-\w+/venv/bin/python -m pip check")
        self.assertRegex(log, rf"config_check\.py --standard {self.install_dir}/config/collector.yaml")
        # Prüfungen vor dem Austausch, Austausch vor dem Neustart.
        self.assertLess(log.index("config_check.py"), log.index("systemctl daemon-reload"))
        self.assertEqual(
            (self.install_dir / "venv/bin/uvicorn").read_text(encoding="utf-8"),
            f"#!{self.install_dir}/venv/bin/python\n",
        )
        self.assertEqual((self.install_dir / ".cache/pip-marker").read_text(encoding="utf-8"), "cache\n")
        self.assertEqual((self.install_dir / "config/collector.yaml").read_text(encoding="utf-8"), "local: true\n")
        self.assertEqual(self._siblings(), [])
        self.assertNotIn("mediamtx.service", log)
        self.assertNotIn("redis", log)

    def _assert_previous_runtime(self) -> None:
        self.assertTrue((self.install_dir / "bin/old.py").exists())
        self.assertFalse((self.install_dir / "bin/new.py").exists())
        self.assertEqual((self.install_dir / "VERSION").read_text(encoding="utf-8"), "0.1.0\n")
        self.assertEqual((self.install_dir / "REVISION").read_text(encoding="utf-8"), "a" * 40 + "\n")
        self.assertEqual((self.install_dir / "config/collector.yaml").read_text(encoding="utf-8"), "local: true\n")
        self.assertEqual(
            (self.service_dir / "mediamtx-api.service").read_text(encoding="utf-8"),
            "ExecStart=python bin/mediamtx_api.py\n",
        )
        self.assertEqual((self.service_dir / "mediamtx.service").read_text(encoding="utf-8"), "local mediamtx unit\n")
        self.assertEqual(self.cli_path.read_text(encoding="utf-8"), "#!/usr/bin/env bash\nprintf 'old cli\n'\n")
        self.assertEqual(self._siblings(), [])

    def test_failure_after_swap_restores_the_previous_runtime(self) -> None:
        self._create_installation(revision="a" * 40)
        self._create_source()
        self._write_executable(self.cli_path, "#!/usr/bin/env bash\nprintf 'old cli\n'\n")
        self.env["MEDIAMTX_MONITOR_TEST_FAIL_AFTER_SWAP"] = "1"
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Rollback: restoring the previous runtime", result.stderr)
        self._assert_previous_runtime()
        log = self.log_file.read_text(encoding="utf-8")
        # Die Dienste liefen nie mit der neuen Laufzeit: kein Neustart nötig.
        self.assertNotIn("systemctl restart", log)
        self.assertEqual(log.count("systemctl daemon-reload"), 2)

    def test_service_failing_after_restart_rolls_back_and_restarts_previous_services(self) -> None:
        self._create_installation(revision="a" * 40)
        self._create_source()
        self._write_executable(self.cli_path, "#!/usr/bin/env bash\nprintf 'old cli\n'\n")
        self.env["FAIL_SERVICE"] = "mediamtx-collector.service"
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Service is not active after upgrade: mediamtx-collector.service", result.stderr)
        self._assert_previous_runtime()
        log = self.log_file.read_text(encoding="utf-8")
        self.assertEqual(log.count(f"systemctl restart {' '.join(SERVICES)}\n"), 2)

    def test_mixed_service_states_are_kept(self) -> None:
        self._create_installation(revision="a" * 40)
        self._create_source()
        self.env["FAKE_INACTIVE"] = "mediamtx-system.service"
        self.env["FAKE_DISABLED"] = "mediamtx-system.service"
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("mediamtx-system.service      inactive, disabled", result.stdout)
        self.assertIn("mediamtx-system      not started (was not active)", result.stdout)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertIn("systemctl restart mediamtx-api.service mediamtx-collector.service\n", log)
        for action in ("enable", "disable", "start ", "stop"):
            self.assertNotIn(f"systemctl {action}", log)

    def test_mixed_states_rollback_restarts_only_previously_active_services(self) -> None:
        self._create_installation(revision="a" * 40)
        self._create_source()
        self.env["FAKE_INACTIVE"] = "mediamtx-system.service"
        self.env["FAIL_SERVICE"] = "mediamtx-api.service"
        result = self._run("--upgrade")
        self.assertEqual(result.returncode, 1)
        log = self.log_file.read_text(encoding="utf-8")
        self.assertEqual(log.count("systemctl restart mediamtx-api.service mediamtx-collector.service\n"), 2)
        self.assertNotIn("mediamtx-system.service\n", log.split("systemctl restart", 1)[1].split("\n")[0])

    def test_failed_checks_leave_the_installation_untouched(self) -> None:
        for check in ("pip", "config"):
            with self.subTest(check=check):
                shutil.rmtree(self.install_dir, ignore_errors=True)
                shutil.rmtree(self.service_dir, ignore_errors=True)
                shutil.rmtree(self.source_dir, ignore_errors=True)
                self.log_file.unlink(missing_ok=True)
                self._create_installation(revision="a" * 40)
                self._create_source()
                self.env["FAIL_CHECK"] = check
                result = self._run("--upgrade")
                self.assertEqual(result.returncode, 1)
                self.assertTrue((self.install_dir / "bin/old.py").exists())
                self.assertEqual(self._siblings(), [])
                log = self.log_file.read_text(encoding="utf-8")
                self.assertNotIn("systemctl daemon-reload", log)
                self.assertNotIn("systemctl restart", log)
        self.env.pop("FAIL_CHECK")

    def test_unknown_option_shows_usage(self) -> None:
        result = self._run("--unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Unknown option", result.stderr)
        self.assertIn("Usage:", result.stderr)


if __name__ == "__main__":
    unittest.main()
