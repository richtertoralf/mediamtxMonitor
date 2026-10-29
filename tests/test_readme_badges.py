"""The README version badge must follow the VERSION file."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReadmeBadgeTests(unittest.TestCase):
    def test_version_badge_matches_version_file(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        badges = re.findall(r"img\.shields\.io/badge/version-([0-9.]+)-", readme)
        self.assertEqual(badges, [version])

    def test_mediamtx_badge_names_the_supported_minimum(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        minimum = re.search(r'MINIMUM_MEDIAMTX_VERSION="([0-9.]+)"', installer).group(1)
        self.assertIn(f"MediaMTX-%E2%89%A5%20{minimum}-", readme)


if __name__ == "__main__":
    unittest.main()
