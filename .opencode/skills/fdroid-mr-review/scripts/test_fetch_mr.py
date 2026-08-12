import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_mr import (
    find_binary_apk_member,
    find_build_job,
    parse_badging,
    parse_permissions,
)

BADGING = """package: name='com.kinetica.keyboard' versionCode='2' versionName='1.0.1' platformBuildVersionName='14' platformBuildVersionCode='34' compileSdkVersion='34' compileSdkVersionCodename='14'
minSdkVersion:'26'
targetSdkVersion:'34'
application-label:'Kinetica'
application-label-zh:'Kinetica'
uses-feature: name='android.hardware.faketouch'
"""

PERMS = """package: com.kinetica.keyboard
uses-permission: name='android.permission.VIBRATE'
permission: com.kinetica.keyboard.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION
uses-permission: name='com.kinetica.keyboard.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION'
"""

JOBS = [
    {"name": "fdroid lint", "status": "success"},
    {"name": "fdroid build", "status": "success", "id": 42},
    {"name": "check apk", "status": "success"},
]


class TestParsing(unittest.TestCase):
    def test_badging(self):
        info = parse_badging(BADGING)
        self.assertEqual(info["package"], "com.kinetica.keyboard")
        self.assertEqual(info["versionCode"], 2)
        self.assertEqual(info["versionName"], "1.0.1")
        self.assertEqual(info["label"], "Kinetica")
        self.assertEqual(info["minSdk"], 26)
        self.assertEqual(info["targetSdk"], 34)

    def test_permissions(self):
        self.assertEqual(
            parse_permissions(PERMS),
            [
                "android.permission.VIBRATE",
                "com.kinetica.keyboard.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION",
            ],
        )

    def test_find_build_job(self):
        self.assertEqual(find_build_job(JOBS)["id"], 42)

    def test_find_build_job_failed_status(self):
        self.assertIsNone(find_build_job([{"name": "fdroid build", "status": "failed"}]))

    def test_find_binary_apk_member(self):
        names = [
            "repo/index.html",
            "tmp/binaries/com.kinetica.keyboard_2.binary.apk",
            "tmp/com.kinetica.keyboard_2.apk",
        ]
        self.assertEqual(
            find_binary_apk_member(names),
            "tmp/binaries/com.kinetica.keyboard_2.binary.apk",
        )


if __name__ == "__main__":
    unittest.main()
