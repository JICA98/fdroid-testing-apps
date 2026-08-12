# F-Droid MR Review Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a project-level opencode skill (`fdroid-mr-review`) that an agent follows to perform F-Droid Tester Reviews of new-app MRs on any connected Android device, one MR at a time, generating the review report locally for the user to post manually.

**Architecture:** Two stdlib-only Python scripts (`fetch_mr.py` downloads MR metadata + build APK from GitLab CI artifacts; `report.py` renders the F-Droid wiki report template) plus a `SKILL.md` encoding the 11-phase review workflow. Device interaction uses adb and the existing android-emulator-skill scripts. One pre-existing bug in `gesture.py` must be patched.

**Tech Stack:** Python 3.13 stdlib (urllib, zipfile, json, re, subprocess, unittest), adb, Android SDK build-tools `aapt2`, GitLab REST API v4, GitHub repo JICA98/fdroid-testing-apps.

## Global Constraints

- Python stdlib only — no third-party packages, no pytest (use `unittest`).
- Scripts are invoked from the repo root (`/home/jica/repo/fdroid-testing-apps`).
- Skill lives at `.opencode/skills/fdroid-mr-review/` in this repo.
- android-emulator-skill scripts live at `~/.config/opencode/skills/android-emulator-skill/scripts/`.
- `work/`, `reports/`, `.tokens/` are gitignored scratch/output dirs (already in `.gitignore`).
- Reports must follow the F-Droid wiki Tester Review template structure (Basic Function / Policy Compliance / Permissions / Network Connections / Language Support / Security Scan).
- Checkbox rendering: `true` → `- [x]`, `false` or missing → `- [ ]`.
- GitLab public API + public artifact URLs require no authentication.
- OnePlus Pad 2 serial is `7d6afed8` (verify with `adb devices` at runtime).

---

### Task 1: Scaffold directory structure

**Files:**
- Create: `.opencode/skills/fdroid-mr-review/scripts/.keep`
- Create: `work/.keep`, `reports/.keep`, `.tokens/.keep`

**Interfaces:**
- Consumes: nothing (empty repo; `.gitignore` already has work/, reports/, .tokens/)
- Produces: directory layout every later task writes into

- [ ] **Step 1: Create directories**

```bash
mkdir -p .opencode/skills/fdroid-mr-review/scripts work reports .tokens
touch .opencode/skills/fdroid-mr-review/scripts/.keep work/.keep reports/.keep .tokens/.keep
```

- [ ] **Step 2: Verify layout**

Run: `find . -name .keep -o -name .gitignore | sort`
Expected: the four `.keep` files plus `.gitignore` listed.

- [ ] **Step 3: Commit**

```bash
git add .gitignore .opencode work reports .tokens
git commit -m "chore: scaffold skill, work, reports, tokens directories"
```

---

### Task 2: `fetch_mr.py` with unit tests

**Files:**
- Create: `.opencode/skills/fdroid-mr-review/scripts/fetch_mr.py`
- Test: `.opencode/skills/fdroid-mr-review/scripts/test_fetch_mr.py`

**Interfaces:**
- Consumes: MR iid (int) from CLI. Public GitLab API v4. `aapt2` from PATH or `$ANDROID_HOME/build-tools/<latest>/aapt2`. Network access to gitlab.com.
- Produces: `work/<iid>/metadata.json` (schema below), `work/<iid>/apk/<package>_<vercode>.binary.apk`, `work/<iid>/artifacts.zip`. Exit code 0 on success, 1 on any failure. Functions exported for tests: `parse_badging(output) -> dict`, `parse_permissions(output) -> list[str]`, `find_build_job(jobs) -> dict|None`, `find_binary_apk_member(names) -> str|None`, `find_aapt2() -> str|None`.

metadata.json schema:
```json
{
  "iid": 45475,
  "title": "New app: Kinetica",
  "description": "...",
  "web_url": "https://gitlab.com/fdroid/fdroiddata/-/merge_requests/45475",
  "source_branch": "com.kinetica.keyboard",
  "pipeline_status": "success",
  "apk_path": "work/45475/apk/com.kinetica.keyboard_2.binary.apk",
  "package": "com.kinetica.keyboard",
  "label": "Kinetica",
  "versionName": "1.0.1",
  "versionCode": 2,
  "minSdk": 26,
  "targetSdk": 34,
  "permissions": ["android.permission.VIBRATE", "..."],
  "has_internet": false
}
```

- [ ] **Step 1: Write the failing tests**

```python
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
sdkVersion:'26'
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 .opencode/skills/fdroid-mr-review/scripts/test_fetch_mr.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'fetch_mr'`.

- [ ] **Step 3: Write `fetch_mr.py`**

```python
#!/usr/bin/env python3
"""Fetch an F-Droid MR's metadata and build APK from its CI artifacts."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

GITLAB_API = "https://gitlab.com/api/v4"
UPSTREAM_PROJECT = "fdroid%2Ffdroiddata"


def api_get(url: str):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def get_mr(iid: int) -> dict:
    return api_get(f"{GITLAB_API}/projects/{UPSTREAM_PROJECT}/merge_requests/{iid}")


def get_pipeline_jobs(project_id: int, pipeline_id: int) -> list:
    return api_get(f"{GITLAB_API}/projects/{project_id}/pipelines/{pipeline_id}/jobs")


def get_project_path_with_namespace(project_id: int) -> str:
    return api_get(f"{GITLAB_API}/projects/{project_id}")["path_with_namespace"]


def find_build_job(jobs: list):
    for job in jobs:
        if job.get("name") == "fdroid build" and job.get("status") == "success":
            return job
    return None


def find_binary_apk_member(zip_names: list):
    for name in zip_names:
        if "/binaries/" in name and name.endswith(".binary.apk"):
            return name
    return None


def find_aapt2():
    found = shutil.which("aapt2")
    if found:
        return found
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not android_home:
        return None
    build_tools = Path(android_home) / "build-tools"
    if not build_tools.is_dir():
        return None
    versions = sorted(p.name for p in build_tools.iterdir() if p.is_dir())
    if not versions:
        return None
    candidate = build_tools / versions[-1] / "aapt2"
    return str(candidate) if candidate.exists() else None


def parse_badging(output: str) -> dict:
    info = {
        "package": None,
        "versionCode": None,
        "versionName": None,
        "label": None,
        "minSdk": None,
        "targetSdk": None,
    }
    pkg = re.search(
        r"package: name='([^']+)' versionCode='(\d+)' versionName='([^']*)'", output
    )
    if pkg:
        info["package"] = pkg.group(1)
        info["versionCode"] = int(pkg.group(2))
        info["versionName"] = pkg.group(3)
    label = re.search(r"application-label:'([^']*)'", output)
    if label:
        info["label"] = label.group(1)
    sdk = re.search(r"sdkVersion:'(\d+)'", output)
    if sdk:
        info["minSdk"] = int(sdk.group(1))
    target = re.search(r"targetSdkVersion:'(\d+)'", output)
    if target:
        info["targetSdk"] = int(target.group(1))
    return info


def parse_permissions(output: str) -> list:
    return re.findall(r"uses-permission: name='([^']+)'", output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch F-Droid MR metadata and APK")
    parser.add_argument("iid", type=int, help="MR iid, e.g. 45475")
    parser.add_argument("--workdir", default="work", help="Base scratch dir (default: work)")
    args = parser.parse_args()

    iid = args.iid
    work_dir = Path(args.workdir) / str(iid)
    apk_dir = work_dir / "apk"
    apk_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching MR !{iid} ...")
    mr = get_mr(iid)
    head = mr.get("head_pipeline")
    if not head:
        print("ERROR: MR has no head pipeline. Cannot test.", file=sys.stderr)
        return 1
    if head["status"] != "success":
        print(
            f"ERROR: head pipeline status is '{head['status']}', not 'success'. Cannot test.",
            file=sys.stderr,
        )
        return 1

    print(f"Pipeline {head['id']} OK; locating 'fdroid build' job ...")
    jobs = get_pipeline_jobs(head["project_id"], head["id"])
    build_job = find_build_job(jobs)
    if not build_job:
        print("ERROR: no successful 'fdroid build' job found.", file=sys.stderr)
        return 1

    fork_path = get_project_path_with_namespace(head["project_id"])
    artifact_url = (
        f"https://gitlab.com/{fork_path}/-/jobs/{build_job['id']}/artifacts/download"
    )
    print(f"Downloading artifacts from {artifact_url} ...")
    zip_path = work_dir / "artifacts.zip"
    with urllib.request.urlopen(artifact_url, timeout=300) as resp:
        zip_path.write_bytes(resp.read())

    with zipfile.ZipFile(zip_path) as archive:
        member = find_binary_apk_member(archive.namelist())
        if not member:
            print("ERROR: no binary APK in artifacts.", file=sys.stderr)
            return 1
        apk_path = apk_dir / Path(member).name
        apk_path.write_bytes(archive.read(member))
    print(f"APK saved: {apk_path}")

    aapt2 = find_aapt2()
    if not aapt2:
        print(
            "ERROR: aapt2 not found (set ANDROID_HOME or install build-tools).",
            file=sys.stderr,
        )
        return 1

    badging = subprocess.run(
        [aapt2, "dump", "badging", str(apk_path)], capture_output=True, text=True
    ).stdout
    perms_out = subprocess.run(
        [aapt2, "dump", "permissions", str(apk_path)], capture_output=True, text=True
    ).stdout
    info = parse_badging(badging)
    permissions = parse_permissions(perms_out)

    metadata = {
        "iid": iid,
        "title": mr["title"],
        "description": mr.get("description") or "",
        "web_url": mr["web_url"],
        "source_branch": mr.get("source_branch"),
        "pipeline_status": head["status"],
        "apk_path": str(apk_path),
        "permissions": permissions,
        "has_internet": "android.permission.INTERNET" in permissions,
        **info,
    }
    meta_path = work_dir / "metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2))
    print(f"Metadata written: {meta_path}")
    summary = {
        k: metadata[k]
        for k in ("package", "label", "versionName", "versionCode", "minSdk", "has_internet")
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 .opencode/skills/fdroid-mr-review/scripts/test_fetch_mr.py`
Expected: `OK` — 5 tests pass.

- [ ] **Step 5: Integration check against a real MR**

Run: `python3 .opencode/skills/fdroid-mr-review/scripts/fetch_mr.py 45475`
Expected: exit 0; prints summary with `package: com.kinetica.keyboard`, `has_internet: false`; files exist at `work/45475/metadata.json` and `work/45475/apk/*.binary.apk`.

- [ ] **Step 6: Commit**

```bash
git add .opencode/skills/fdroid-mr-review/scripts/
git commit -m "feat: add fetch_mr.py for F-Droid MR APK retrieval"
```

---

### Task 3: `report.py` with unit tests

**Files:**
- Create: `.opencode/skills/fdroid-mr-review/scripts/report.py`
- Test: `.opencode/skills/fdroid-mr-review/scripts/test_report.py`

**Interfaces:**
- Consumes: `work/<iid>/metadata.json` (from Task 2), a results JSON file (schema in SKILL.md), optional notes file (one note per line), device label from CLI.
- Produces: `reports/<iid>-<package>.md` — wiki-template report. Exported function: `render_report(meta: dict, results: dict, device: str, notes: list) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 .opencode/skills/fdroid-mr-review/scripts/test_report.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'report'`.

- [ ] **Step 3: Write `report.py`**

```python
#!/usr/bin/env python3
"""Generate an F-Droid tester review report from MR metadata and results."""
import argparse
import json
import sys
from pathlib import Path

TEMPLATE = """## Tester review: {label} ({package})

- MR: {web_url}
- Version {versionName} ({versionCode}), minSdk {minSdk}
- Test device: {device}

<table>
<thead>
<tr>
<th>Category</th>
<th>Checklist</th>
</tr>
</thead>
<tbody>
<tr>
<td>Basic Function</td>
<td>

- {start} The app can start and work normally.
- {functions} The functions in the description are implemented.
- {icon} The app has a unique icon (instead of a default one).

</td>
</tr>
<tr>
<td>Policy Compliance</td>
<td>

- {policy} Features don't violate F-Droid's Inclusion Policy.
- {categories} The Categories field is set properly.
- {terms} Doesn't require accepting any terms other than the FOSS license.

</td>
</tr>
<tr>
<td>Permissions</td>
<td>

- {runtime_perms} The app can be used without granting optional runtime permissions.
- {manage_storage} The app doesn't require unnecessary MANAGE_EXTERNAL_STORAGE permission.

</td>
</tr>
<tr>
<td>Network Connections</td>
<td>

- {conn_observed} Network connection is observed.
- {conn_start} The app connects to web services on start.
- {conn_update} The app checks for update automatically.
- {conn_unnecessary} The app has unnecessary connections, e.g., online fonts, icons, connectivity check.
- {conn_tracking} Tracking domains connected.
- {conn_unclear} Connections not described clearly in description.
- {conn_webview} Unnecessary in-app webview presents in the app.

</td>
</tr>
<tr>
<td>Language Support</td>
<td>

- {english} The app has English support.

</td>
</tr>
<tr>
<td>Security Scan</td>
<td>

- {virustotal} All or most vendors on VirusTotal indicate the app is benign.

</td>
</tr>
</tbody>
</table>

## Notes

{notes}
"""


def checkbox(value):
    return "- [x]" if value is True else "- [ ]"


def render_report(meta: dict, results: dict, device: str, notes: list) -> str:
    return TEMPLATE.format(
        label=meta.get("label") or meta.get("package"),
        package=meta.get("package", "unknown"),
        web_url=meta.get("web_url", ""),
        versionName=meta.get("versionName", "?"),
        versionCode=meta.get("versionCode", "?"),
        minSdk=meta.get("minSdk", "?"),
        device=device,
        start=checkbox(results.get("start_ok")),
        functions=checkbox(results.get("functions_ok")),
        icon=checkbox(results.get("unique_icon")),
        policy=checkbox(results.get("policy_ok")),
        categories=checkbox(results.get("categories_ok")),
        terms=checkbox(results.get("terms_ok")),
        runtime_perms=checkbox(results.get("runtime_perms_ok")),
        manage_storage=checkbox(results.get("no_manage_storage")),
        conn_observed=checkbox(results.get("conn_observed")),
        conn_start=checkbox(results.get("conn_on_start")),
        conn_update=checkbox(results.get("conn_update_check")),
        conn_unnecessary=checkbox(results.get("conn_unnecessary")),
        conn_tracking=checkbox(results.get("conn_tracking")),
        conn_unclear=checkbox(results.get("conn_unclear")),
        conn_webview=checkbox(results.get("conn_webview")),
        english=checkbox(results.get("english_ok")),
        virustotal=checkbox(results.get("virustotal_ok")),
        notes="\n".join(f"- {note}" for note in notes) if notes else "_None._",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate F-Droid tester review report")
    parser.add_argument("iid", type=int, help="MR iid")
    parser.add_argument("--results", required=True, help="results JSON file")
    parser.add_argument("--device", required=True, help="test device label or serial")
    parser.add_argument("--meta", default=None, help="metadata.json path (default: work/<iid>/metadata.json)")
    parser.add_argument("--notes", default=None, help="notes file, one note per line")
    parser.add_argument("--out", default="reports", help="output dir (default: reports)")
    args = parser.parse_args()

    meta_path = Path(args.meta) if args.meta else Path("work") / str(args.iid) / "metadata.json"
    meta = json.loads(meta_path.read_text())
    results = json.loads(Path(args.results).read_text())
    notes = Path(args.notes).read_text().splitlines() if args.notes else []

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.iid}-{meta['package']}.md"
    out_path.write_text(render_report(meta, results, args.device, notes))
    print(f"Report written: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 .opencode/skills/fdroid-mr-review/scripts/test_report.py`
Expected: `OK` — 5 tests pass.

- [ ] **Step 5: End-to-end report generation**

```bash
python3 - <<'EOF'
import json
import sys
from pathlib import Path
sys.path.insert(0, ".opencode/skills/fdroid-mr-review/scripts")
from report import render_report
meta = json.load(open("work/45475/metadata.json"))
results = {
    "start_ok": True, "functions_ok": True, "unique_icon": True,
    "policy_ok": True, "categories_ok": True, "terms_ok": True,
    "runtime_perms_ok": True, "no_manage_storage": True,
    "conn_observed": None, "conn_on_start": None, "conn_update_check": None,
    "conn_unnecessary": None, "conn_tracking": None, "conn_unclear": None,
    "conn_webview": None, "english_ok": True, "virustotal_ok": None,
}
Path("work/45475/results.json").write_text(json.dumps(results, indent=2))
Path("work/45475/notes.txt").write_text("No INTERNET permission.\n")
EOF
python3 .opencode/skills/fdroid-mr-review/scripts/report.py 45475 \
  --device "OnePlus Pad 2" --results work/45475/results.json --notes work/45475/notes.txt
```

Expected: `Report written: reports/45475-com.kinetica.keyboard.md`; file contains `## Tester review: Kinetica (com.kinetica.keyboard)` and the notes bullet.

- [ ] **Step 6: Commit**

```bash
git add .opencode/skills/fdroid-mr-review/scripts/
git commit -m "feat: add report.py for F-Droid review report generation"
```

---

### Task 4: Patch `gesture.py` import bug

**Files:**
- Modify: `/home/jica/.config/opencode/skills/android-emulator-skill/scripts/gesture.py:11`

**Interfaces:**
- Consumes: none.
- Produces: working `gesture.py` (used by SKILL.md Phase 5 for swipes). `get_screen_size(serial)` returns `(width, height)` — already matches usage `width, height = get_size(serial)`.

- [ ] **Step 1: Fix the import**

Replace line 11:

```python
from common import resolve_serial, run_adb_command, get_device_screen_size as get_size
```

with:

```python
from common import resolve_serial, run_adb_command, get_screen_size as get_size
```

- [ ] **Step 2: Verify the script runs**

Run: `python3 /home/jica/.config/opencode/skills/android-emulator-skill/scripts/gesture.py --help`
Expected: usage help printed (no ImportError).

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "chore: note gesture.py fix applied in android-emulator-skill"
```

---

### Task 5: Write `SKILL.md`

**Files:**
- Create: `.opencode/skills/fdroid-mr-review/SKILL.md`

**Interfaces:**
- Consumes: scripts from Tasks 2–3; android-emulator-skill scripts (Task 4 fixed); adb; the gitignored dirs.
- Produces: the workflow document the agent follows per MR. References `work/<iid>/results.json` schema and `notes.txt` convention.

- [ ] **Step 1: Write SKILL.md with the full workflow**

```markdown
# F-Droid MR Tester Review

Perform an F-Droid **Tester Review** of one new-app MR in
[fdroid/fdroiddata](https://gitlab.com/fdroid/fdroiddata) on a connected
Android device, following the official guide (F-Droid wiki, "Reviewing new
apps", Tester Review section). The report is generated locally and the user
posts it on the MR manually.

Triggered by the user with an MR number, e.g. "review MR 45475".

## Phase 0: Prerequisites

Check each; if items 1-3 fail, STOP and tell the user what to fix:

1. `python3 --version`
2. `adb devices` — at least one device listed
3. `aapt2` findable: `which aapt2` or `$ANDROID_HOME/build-tools/*/aapt2`
   (`fetch_mr.py` locates it automatically)
4. Scripts present: `.opencode/skills/fdroid-mr-review/scripts/fetch_mr.py`
   and `report.py` (run from repo root)
5. Optional — PCAPdroid installed: `adb shell pm list packages | grep
   com.emanuelef.remote_capture` (needed only if the app has INTERNET)
6. Optional — VirusTotal key at `.tokens/virustotal.key`

## Phase 1: Device selection

- One device in `adb devices` → use it. Multiple → ask the user which serial.
- Device API level: `adb -s <serial> shell getprop ro.build.version.sdk`
- If `minSdk` (from `work/<iid>/metadata.json`) > device API level: STOP
  with that reason.

## Phase 2: Fetch MR

From the repo root:

    python3 .opencode/skills/fdroid-mr-review/scripts/fetch_mr.py <iid>

Show the user a summary card:

    <title> — <label> (<package>)
    <versionName> (<versionCode>), minSdk <minSdk>
    INTERNET permission: yes/no
    permissions: <list>
    <1-2 sentence description summary>

Script error (no pipeline / failed pipeline / no build job / no APK) →
report the error as the MR status and STOP; untestable MRs get no report.

## Phase 3: Install

    adb -s <serial> install -r work/<iid>/apk/*.apk

- Success → proceed.
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE` (existing app, different signature) →
  ask the user to confirm, then `adb -s <serial> uninstall <package>` and
  reinstall.
- Other failures → record FAIL, ask the user, skip app-dependent checks.

## Phase 4: Launch & baseline

1. `mkdir -p work/<iid>/screenshots`
2. Launch: `adb -s <serial> shell monkey -p <package> -c
   android.intent.category.LAUNCHER 1`
3. Wait 3 s, then: `adb -s <serial> exec-out screencap -p >
   work/<iid>/screenshots/01-home.png`
4. Verify it started (not crashed, not stuck on launcher). On crash:
   `adb -s <serial> logcat -d > work/<iid>/logcat.txt`; set `start_ok:
   false`; continue only with checks not needing the app.
5. Icon check: open Settings → Apps → <app> (or launcher grid), screenshot,
   compare against Android's default generic icon. Set `unique_icon`.

## Phase 5: Feature testing

- From the MR description, list the main functions to verify.
- Walk each function using the android-emulator-skill scripts
  (`~/.config/opencode/skills/android-emulator-skill/scripts/`):
  - `screen_mapper.py --serial <serial>` — inspect current UI
  - `navigator.py --find-text "..." --tap --serial <serial>` — tap
  - `navigator.py --find-class EditText --enter-text "..." --serial <serial>` — text entry
  - `gesture.py --swipe up --serial <serial>` — scroll
  - `keyboard.py --key BACK --serial <serial>` — back/home/enter
- Screenshot each reached screen: `work/<iid>/screenshots/NN-<name>.png`
- Crash during testing → logcat dump, `functions_ok: false`, note it.
- `functions_ok: true` only when all described main functions were usable.

## Phase 6: Permissions analysis

From `work/<iid>/metadata.json`:

- For each runtime (dangerous) permission: does the app prompt at first
  launch (bad — set `runtime_perms_ok: false`) or only when the feature is
  used (good)? Prompting at first launch for optional perms is a FAIL per
  the wiki guide.
- `MANAGE_EXTERNAL_STORAGE` present → `no_manage_storage: false` + note
  "suggest SAF instead".
- `has_internet` decides whether Phase 7 runs.

## Phase 7: Network capture (only if has_internet)

1. PCAPdroid (preferred):
   - Start capture: try `adb shell monkey -p com.emanuelef.remote_capture 1`
     then `navigator.py --find-text "Start" --tap`; if that fails, ask the
     user to start it manually.
   - Open the app under test and exercise its main functions for ~1 minute.
   - Stop capture; pull export: `adb -s <serial> pull /sdcard/Download/ ...`
   - Screenshot PCAPdroid's connections list; note destinations.
2. Rooted fallback: `adb -s <serial> shell su -c "tcpdump -i any -w
   /sdcard/cap.pcap &"`, exercise the app, pull the pcap.
3. Neither available → note "Network capture not performed", leave network
   items unchecked.

Record: `conn_observed`, `conn_on_start`, `conn_update_check`,
`conn_unnecessary`, `conn_tracking`, `conn_unclear`, `conn_webview`.
Suspicious/unexplained destinations → note "check with author".

## Phase 8: Language support

English UI or description present → `english_ok: true`; otherwise
`english_ok: false` + note "English not supported; must be declared in the
description".

## Phase 9: VirusTotal (optional)

- Key exists (`.tokens/virustotal.key`):
  `curl -s --header "x-apikey: $(cat .tokens/virustotal.key)"
  "https://www.virustotal.com/api/v3/files/<sha256-of-apk>"` → set
  `virustotal_ok` from `data.attributes.last_analysis_stats` (mostly
  `undetected` → true).
- No key: ask the user to provide one (save to `.tokens/virustotal.key`,
  gitignored) or skip → leave `virustotal_ok` null.

## Phase 10: Report

Write `work/<iid>/results.json` with the schema below and
`work/<iid>/notes.txt` (one note per line), then:

    python3 .opencode/skills/fdroid-mr-review/scripts/report.py <iid> \
      --device "<serial or device name>" --results work/<iid>/results.json \
      --notes work/<iid>/notes.txt

Show `reports/<iid>-<package>.md` to the user for manual posting on the MR.

### results.json schema

```json
{
  "start_ok": true | false | null,
  "functions_ok": true | false | null,
  "unique_icon": true | false | null,
  "policy_ok": true | false | null,
  "categories_ok": true | false | null,
  "terms_ok": true | false | null,
  "runtime_perms_ok": true | false | null,
  "no_manage_storage": true | false | null,
  "conn_observed": true | false | null,
  "conn_on_start": true | false | null,
  "conn_update_check": true | false | null,
  "conn_unnecessary": true | false | null,
  "conn_tracking": true | false | null,
  "conn_unclear": true | false | null,
  "conn_webview": true | false | null,
  "english_ok": true | false | null,
  "virustotal_ok": true | false | null
}
```

`true` → `- [x]`, anything else → `- [ ]`.

## Phase 11: Cleanup

- Ask the user whether to uninstall: `adb -s <serial> uninstall <package>`
- Keep `work/<iid>/` and `reports/` (gitignored) for reference.

## Error handling

| Situation | Action |
|---|---|
| No pipeline / failed / no build job / no APK | report status, STOP |
| aapt2 missing | STOP, install build-tools or set ANDROID_HOME |
| No device | STOP, ask user to connect / enable USB debugging |
| minSdk > device API | STOP with reason |
| Install signature conflict | ask user to uninstall existing first |
| Crash on launch | logcat → FAIL, continue feasible checks |
| No PCAPdroid, no root | note "capture not performed" |
| Invalid VT key | skip scan, note it |

## Per-MR checklist

- [ ] Phase 0 prerequisites
- [ ] Phase 1 device + minSdk
- [ ] Phase 2 fetch + summary shown
- [ ] Phase 3 installed
- [ ] Phase 4 launch + baseline screenshots
- [ ] Phase 5 features tested + screenshots
- [ ] Phase 6 permissions analyzed
- [ ] Phase 7 network captured (if INTERNET)
- [ ] Phase 8 language checked
- [ ] Phase 9 VirusTotal (optional)
- [ ] Phase 10 report generated + shown
- [ ] Phase 11 cleanup confirmed
```

- [ ] **Step 2: Verify skill loads**

Run from repo root: `ls .opencode/skills/fdroid-mr-review/`
Expected: `SKILL.md` and `scripts/` listed. (If opencode is running with
project skills enabled, `available_skills` will include `fdroid-mr-review`
in the next session.)

- [ ] **Step 3: Commit**

```bash
git add .opencode/skills/fdroid-mr-review/SKILL.md
git commit -m "feat: add fdroid-mr-review skill workflow"
```

---

### Task 6: Device acceptance dry-run (OnePlus Pad 2)

**Files:**
- Modify: `work/45475/` (scratch, gitignored), `reports/45475-com.kinetica.keyboard.md` (gitignored)

**Interfaces:**
- Consumes: Task 2 fetch output for MR 45475, Task 3 report.py, Task 4 gesture fix, connected device.
- Produces: proof the full loop works on the real device: installed app, baseline screenshot, report file.

- [ ] **Step 1: Verify device and re-fetch if needed**

Run: `adb devices` — expect `7d6afed8  device` (or whatever serial is present).
Run: `ls work/45475/apk/` — if empty, rerun `python3 .opencode/skills/fdroid-mr-review/scripts/fetch_mr.py 45475`.

- [ ] **Step 2: Install the Kinetica APK**

Run: `adb install -r work/45475/apk/*.binary.apk`
Expected: `Success`.

- [ ] **Step 3: Launch and screenshot**

```bash
mkdir -p work/45475/screenshots
adb shell monkey -p com.kinetica.keyboard -c android.intent.category.LAUNCHER 1
sleep 3
adb exec-out screencap -p > work/45475/screenshots/01-home.png
ls -la work/45475/screenshots/
```

Expected: `01-home.png` exists and is a non-empty PNG (check with `file`).

- [ ] **Step 4: UI mapping smoke test**

Run: `python3 ~/.config/opencode/skills/android-emulator-skill/scripts/screen_mapper.py`
Expected: JSON/text list of UI elements from the keyboard app screen (no crash).

- [ ] **Step 5: Generate final dry-run report**

```bash
python3 - <<'EOF'
import json
from pathlib import Path
results = {
    "start_ok": True, "functions_ok": True, "unique_icon": True,
    "policy_ok": True, "categories_ok": True, "terms_ok": True,
    "runtime_perms_ok": True, "no_manage_storage": True,
    "conn_observed": None, "conn_on_start": None, "conn_update_check": None,
    "conn_unnecessary": None, "conn_tracking": None, "conn_unclear": None,
    "conn_webview": None, "english_ok": True, "virustotal_ok": None,
}
Path("work/45475/results.json").write_text(json.dumps(results, indent=2))
Path("work/45475/notes.txt").write_text("Dry-run on OnePlus Pad 2.\nNo INTERNET permission.\n")
EOF
python3 .opencode/skills/fdroid-mr-review/scripts/report.py 45475 \
  --device "OnePlus Pad 2" --results work/45475/results.json --notes work/45475/notes.txt
```

Expected: `Report written: reports/45475-com.kinetica.keyboard.md`.

- [ ] **Step 6: Uninstall (with user confirmation) and commit**

Ask the user whether to uninstall the dry-run app, then (if yes):
`adb uninstall com.kinetica.keyboard`

```bash
git add -A
git commit -m "docs: finalize fdroid-mr-review skill (acceptance dry-run)"
```

---

## Self-review notes

- Spec coverage: all spec sections map to tasks — components (Tasks 2–3), workflow (Task 5), gesture patch (Task 4), testing (Tasks 2–3 unit tests, Task 6 device dry-run), error handling (SKILL.md table), out-of-scope items intentionally absent.
- Placeholder scan: every step contains complete code or exact commands; no TBD/TODO.
- Type consistency: `parse_badging`/`parse_permissions`/`find_build_job`/`find_binary_apk_member` names identical across tests, implementation, and SKILL.md usage; results.json keys identical across report.py, tests, and SKILL.md schema; `get_screen_size` alias matches gesture.py usage.
