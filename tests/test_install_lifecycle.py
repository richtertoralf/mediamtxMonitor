"""Statische Verträge für die automatische MediaMTX-Lifecycle-Auswahl."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class InstallLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "install.sh").read_text(encoding="utf-8")

    def test_default_install_is_valid_and_has_tested_version(self):
        self.assertIn('while [ "$#" -gt 0 ]; do', self.source)
        self.assertIn('readonly DEFAULT_MEDIAMTX_VERSION="1.21.0"', self.source)
        self.assertIn('readonly MINIMUM_MEDIAMTX_VERSION="1.21.0"', self.source)
        self.assertIn('MEDIAMTX_VERSION="$DEFAULT_MEDIAMTX_VERSION"', self.source)
        self.assertNotIn("--app-only", self.source)

    def test_reuse_checks_shared_mediamtx_without_writing_it(self):
        self.assertIn('INSTALL_MODE=reuse', self.source)
        self.assertIn('path_mediamtx="$(command -v mediamtx', self.source)
        self.assertIn('systemctl show mediamtx.service --property=LoadState --value', self.source)
        self.assertIn('if [ "$foreign_path" = true ]; then', self.source)
        self.assertIn('[ -x "$MEDIAMTX_BIN" ]', self.source)
        self.assertIn('[ -r "$MEDIAMTX_CONFIG" ]', self.source)
        self.assertIn('systemctl is-active --quiet mediamtx.service', self.source)
        self.assertIn('"$MEDIAMTX_BIN" --version', self.source)
        self.assertIn('MediaMTX-Version konnte nicht bestimmt werden', self.source)
        self.assertIn('"$TEMP_DIR/extract/mediamtx" "--validate-conf=$TEMP_DIR/mediamtx.yml"', self.source)

    def test_reuse_requires_monitor_owned_configuration_and_runtime_api(self):
        self.assertNotIn("monitor_config_is_complete", self.source)
        self.assertIn("check_reuse_config.py", self.source)
        self.assertIn('"${MEDIAMTX_API_URL%/}/v3/info"', self.source)
        self.assertIn("read_runtime_version", self.source)
        self.assertIn("python3 fehlt", self.source)
        self.assertIn("Laufende MediaMTX-Runtime", self.source)

    def test_reuse_reports_binary_runtime_version_mismatch_without_restart(self):
        self.assertIn("Installierte MediaMTX-Binary v$existing_version", self.source)
        self.assertIn("laufende Prozess verwendet noch v$runtime_version", self.source)
        self.assertIn("kontrolliert neu gestartet werden", self.source)
        self.assertNotIn("systemctl restart mediamtx", self.source)
        self.assertIn('if [ "$INSTALL_MODE" = fresh ]; then\n  install -o root -g root -m 0755', self.source)
        self.assertIn('if [ "$INSTALL_MODE" = fresh ]; then\n  install -o root -g root -m 0644', self.source)

    def test_reuse_does_not_install_or_start_mediamtx(self):
        self.assertIn('if [ "$INSTALL_MODE" = fresh ]; then\n  install -m 0644 "$SCRIPT_DIR/systemd/mediamtx.service"', self.source)
        self.assertIn('if [ "$INSTALL_MODE" = fresh ]; then\n  systemctl enable --now mediamtx.service', self.source)

    def test_partial_installation_aborts_before_mutation(self):
        self.assertIn('Unvollständige MediaMTX-Installation erkannt.', self.source)
        self.assertIn('Die Installation wurde nicht verändert.', self.source)
        self.assertIn('exit 1', self.source)

    def test_foreign_path_and_known_alternate_unit_are_conflicts(self):
        self.assertIn('Eine andere MediaMTX-Binary ist im PATH sichtbar', self.source)
        self.assertIn('case "$unit_load_state" in', self.source)
        self.assertIn('loaded|masked)', self.source)
        self.assertIn('[ -z "$path_mediamtx" ]', self.source)

    def test_detection_precedes_mutation(self):
        detection = self.source.index('path_mediamtx=')
        apt_update = self.source.index('apt-get update')
        user_creation = self.source.index('groupadd --system')
        self.assertLess(detection, apt_update)
        self.assertLess(detection, user_creation)


if __name__ == "__main__":
    unittest.main()
