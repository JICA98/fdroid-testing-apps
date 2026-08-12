import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report import render_report

META = {
    "iid": 45475,
    "title": "New app: Kinetica",
    "web_url": "https://gitlab.com/fdroid/fdroiddata/-/merge_requests/45475",
    "package": "com.kinetica.keyboard",
    "label": "Kinetica",
    "versionName": "1.0.1",
    "versionCode": 2,
    "minSdk": 26,
    "has_internet": False,
}

RESULTS = {
    "start_ok": True,
    "functions_ok": True,
    "unique_icon": True,
    "policy_ok": True,
    "categories_ok": True,
    "terms_ok": True,
    "runtime_perms_ok": True,
    "no_manage_storage": True,
    "conn_observed": None,
    "conn_on_start": None,
    "conn_update_check": None,
    "conn_unnecessary": None,
    "conn_tracking": None,
    "conn_unclear": None,
    "conn_webview": None,
    "english_ok": True,
    "virustotal_ok": None,
}


class TestReport(unittest.TestCase):
    def setUp(self):
        self.report = render_report(META, RESULTS, "OnePlus Pad 2", ["No INTERNET permission."])

    def test_header(self):
        self.assertIn("## Tester review: Kinetica (com.kinetica.keyboard)", self.report)
        self.assertIn("https://gitlab.com/fdroid/fdroiddata/-/merge_requests/45475", self.report)
        self.assertIn("Version 1.0.1 (2), minSdk 26", self.report)

    def test_checked_items(self):
        self.assertIn("- [x] The app can start and work normally.", self.report)
        self.assertIn("- [x] The app has a unique icon (instead of a default one).", self.report)

    def test_unchecked_items(self):
        self.assertIn("- [ ] Tracking domains connected.", self.report)
        self.assertIn("- [ ] All or most vendors on VirusTotal indicate the app is benign.", self.report)

    def test_notes(self):
        self.assertIn("- No INTERNET permission.", self.report)

    def test_network_section_present(self):
        self.assertIn("Network Connections", self.report)


if __name__ == "__main__":
    unittest.main()
