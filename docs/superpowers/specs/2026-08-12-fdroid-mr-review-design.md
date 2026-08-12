# F-Droid MR Review Skill — Design

**Date:** 2026-08-12
**Status:** Approved (user approved Sections 1–3)

## Goal

A project-level opencode skill (`fdroid-mr-review`) that an agent follows to perform F-Droid Tester Reviews on any connected Android device, one MR at a time, conversationally triggered by the user ("review MR 45475"). The agent automates testing and generates the review report locally; the user copy-pastes it onto the MR manually.

## Context

- 117 open MRs in fdroid/fdroiddata carry the `review-requested` label.
- F-Droid's review guide (wiki "Reviewing new apps", Tester Review section) defines what to check: basic function, icon, policy compliance, categories, permissions, network connections (when INTERNET permission present), English support, optional VirusTotal scan.
- APKs are published as CI artifacts: MR → `head_pipeline` → fork project → `fdroid build` job → public artifacts zip → `tmp/binaries/<pkg>_<vercode>.binary.apk`. Verified working without auth on MR 45475.
- Permissions/version info obtainable locally via `aapt2` (SDK build-tools 36.0.0 present at `/home/jica/Android/Sdk/build-tools/`).
- Existing android-emulator-skill scripts (`app_launcher.py`, `screen_mapper.py`, `navigator.py`, `gesture.py`, `log_monitor.py`) drive any connected device via adb/uiautomator.

## Components

```
fdroid-testing-apps/
├── .opencode/skills/fdroid-mr-review/
│   ├── SKILL.md                 # workflow: prerequisites → device → fetch → test → report
│   └── scripts/
│       ├── fetch_mr.py          # MR→APK pipeline
│       └── report.py            # wiki-template report generator
├── work/<mr-iid>/               # scratch: apk/, screenshots/, metadata.json, pcap/, logcat.txt
├── reports/<mr-iid>-<pkg>.md    # finished reports (user copy-pastes to MR)
└── .tokens/virustotal.key       # optional VT API key (gitignored)
```

### fetch_mr.py

Input: MR iid. Output: `work/<iid>/metadata.json` + downloaded APK.

Steps:
1. GET `https://gitlab.com/api/v4/projects/fdroid%2Ffdroiddata/merge_requests/<iid>` → title, description, head_pipeline (project_id, id, status, sha), source_branch.
2. If head pipeline missing/failed, record status and exit with "cannot test".
3. GET `https://gitlab.com/api/v4/projects/<fork_pid>/pipelines/<pipe_id>/jobs` → find job named `fdroid build`.
4. Download artifacts: `https://gitlab.com/<fork>/fdroiddata/-/jobs/<job_id>/artifacts/download` (public, no auth) → unzip → `tmp/binaries/*.binary.apk` → save to `work/<iid>/apk/`.
5. `aapt2 dump badging` → package, versionName, versionCode, minSdk, targetSdk, label. `aapt2 dump permissions` → permissions list + INTERNET flag.
6. Write metadata.json: package, label, versionName, versionCode, minSdk, targetSdk, source_branch, pipeline_status, permissions[], has_internet, apk_path, description.

### report.py

Input: MR iid (+ any JSON of results). Output: `reports/<iid>-<pkg>.md`.

Renders the F-Droid wiki report template:
- Basic Function: starts, functions implemented, unique icon
- Policy Compliance: no policy violations, categories set properly, no extra terms
- Permissions: no unnecessary runtime permissions, no unnecessary MANAGE_EXTERNAL_STORAGE
- Network Connections (only when INTERNET): connection observed, connects on start, auto update check, unnecessary connections, tracking domains, unclear connections, in-app webview
- Language Support: English support
- Security Scan: VirusTotal verdict (optional)

All items as checkboxes; screenshots referenced by relative path; notes appended per item.

### SKILL.md workflow

1. **Prerequisites** — check adb, connected devices, aapt2, python3; report missing; halt if essentials missing.
2. **Device selection** — if multiple devices, ask user; verify minSdk ≤ device API level, else halt with reason.
3. **Fetch MR** — run `fetch_mr.py <iid>`; show summary card (package, version, permissions, INTERNET flag, description summary).
4. **Install** — `adb install -r`; on signature conflict ask user before uninstalling existing.
5. **Launch & baseline** — launch, screenshot; verify start + unique icon.
6. **Feature testing** — uiautomator navigation through description's main functions; screenshot each screen; on crash capture logcat → FAIL.
7. **Permissions** — flag runtime perms needed at start vs on-demand; flag MANAGE_EXTERNAL_STORAGE.
8. **Network capture** (INTERNET only) — PCAPdroid if installed (start capture → open app → stop → export), else root tcpdump, else record "capture not performed". Analyze destinations: on-start connections, update checks, tracking domains.
9. **Language** — verify English support.
10. **VirusTotal (optional)** — use `.tokens/virustotal.key` if present; else ask user or skip.
11. **Report** — run `report.py`, display report, user copy-pastes manually.
12. **Cleanup** — ask before uninstalling; keep work/ artifacts.

## Error handling

- Pipeline failed / no build job → report "cannot test" and stop.
- APK missing from artifacts → report and stop.
- No device / minSdk not met → halt with explicit reason.
- Signature conflict → user confirmation before uninstall.
- Crash on launch → logcat to `work/<iid>/logcat.txt`, FAIL in report, continue remaining possible checks.
- No PCAPdroid + no root → "Network capture not performed" note.
- Invalid VT key → skip, keep report valid.

## Out of scope (YAGNI)

- Auto-posting reports to GitLab (manual copy-paste by user).
- Batch/multi-MR mode.
- Maintainer-side checks (metadata templates, categories validation, Code Quality warnings) — Categories remains a manual report item.

## Testing

- fetch_mr.py on 2 real MRs (one with INTERNET permission, one without) — proven on 45475.
- report.py golden-output check against wiki template.
- Dry-run on OnePlus Pad 2: install Kinetica APK, launch/screenshot/navigate, verify screenshots land in work/.
