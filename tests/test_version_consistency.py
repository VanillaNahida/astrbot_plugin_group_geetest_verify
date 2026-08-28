import re
import unittest
from pathlib import Path

from core.version import PLUGIN_VERSION, PLUGIN_VERSION_TAG


REPO_ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_manifest_matches_shared_version(self):
        metadata = (REPO_ROOT / "metadata.yaml").read_text(encoding="utf-8")
        match = re.search(r"^version:\s*(\S+)", metadata, re.MULTILINE)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), PLUGIN_VERSION_TAG)
        self.assertEqual(PLUGIN_VERSION, "1.3.4")
        self.assertEqual(PLUGIN_VERSION_TAG, "v1.3.4")

    def test_runtime_version_consumers_use_shared_constant(self):
        main_source = (REPO_ROOT / "main.py").read_text(encoding="utf-8")
        api_source = (REPO_ROOT / "core" / "api.py").read_text(encoding="utf-8")

        self.assertIn("PLUGIN_VERSION_TAG,", main_source)
        self.assertNotIn('"v1.3.0"', main_source)
        self.assertIn("group_geetest_verify/v{PLUGIN_VERSION}", api_source)
        self.assertNotIn('PLUGIN_VERSION = "1.3.0"', api_source)

    def test_changelog_latest_entry_matches_manifest(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        match = re.search(r"^# \[(v[^]]+)\]", changelog, re.MULTILINE)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), PLUGIN_VERSION_TAG)


if __name__ == "__main__":
    unittest.main()
