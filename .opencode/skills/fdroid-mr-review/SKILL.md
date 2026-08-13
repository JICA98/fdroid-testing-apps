# F-Droid MR Tester Review

Perform an F-Droid **Tester Review** of one new-app MR in
[fdroid/fdroiddata](https://gitlab.com/fdroid/fdroiddata) on a connected
Android device, following the official guide (F-Droid wiki, "Reviewing new
apps", Tester Review section). The report is generated locally and the user
posts it on the MR manually.

Triggered by the user with an MR number, e.g. "review MR 45475", or by a
request to pick one, e.g. "pick an open MR ready for testing".

## Phase 0: Prerequisites

Check each; if items 1-3 fail, STOP and tell the user what to fix:

1. `python3 --version`
2. `adb devices` — at least one device listed
3. `aapt2` findable: `which aapt2` or `$ANDROID_HOME/build-tools/*/aapt2`
   (`fetch_mr.py` locates it automatically)
4. Scripts present: `.opencode/skills/fdroid-mr-review/scripts/` —
   `pick_mr.py`, `fetch_mr.py`, `report.py`, `post_comment.py` (run from
   repo root)
5. Optional — PCAPdroid installed: `adb shell pm list packages | grep
   com.emanuelef.remote_capture` (needed only if the app has INTERNET)
6. Optional — VirusTotal key at `.tokens/virustotal.key`
7. GitLab token at `.tokens/gitlab.token` — required for MR picking (the
   notes check that detects already-tested MRs needs auth) and for
   auto-posting the report (Phase 12); without it the agent asks the user
   for a token (save to `.tokens/gitlab.token`, gitignored) or falls back
   to manual posting

## Phase 1: MR selection

If the user named an MR number, skip this phase and go to Phase 3.

Otherwise (e.g. "pick an open MR ready for testing which has not been
tested yet"):

1. Run from the repo root:

       python3 .opencode/skills/fdroid-mr-review/scripts/pick_mr.py

2. It queries open MRs labeled `review-requested` (oldest first), checks
   each head pipeline, and reads MR notes to detect existing tester review
   comments (`## Tester review:` marker). Output: one line per MR with
   `pipeline` and `tested` status, then the candidate list of MRs that are
   ready (pipeline success) and not yet tested.
3. Pick the first candidate (`!<iid>` at the top of the candidate list —
   the oldest untested ready MR) and show the user the summary: "Reviewing
   !<iid> <title>". If the user prefers another, take their pick.
4. `tested: unknown` (no token / notes auth failure) → warn the user that
   previously-reviewed MRs cannot be detected; still proceed with the
   oldest ready MR unless the user says otherwise.

## Phase 2: Device selection

- One device in `adb devices` → use it. Multiple → ask the user which serial.
- Device API level: `adb -s <serial> shell getprop ro.build.version.sdk`
- If `minSdk` (from `work/<iid>/metadata.json`) > device API level: STOP
  with that reason.

## Phase 3: Fetch MR

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

## Phase 4: Install

    adb -s <serial> install -r work/<iid>/apk/*.apk

- Success → proceed.
- `INSTALL_FAILED_UPDATE_INCOMPATIBLE` (existing app, different signature) →
  ask the user to confirm, then `adb -s <serial> uninstall <package>` and
  reinstall.
- Other failures → record FAIL, ask the user, skip app-dependent checks.

## Phase 5: Launch & baseline

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

## Phase 6: Feature testing

- From the MR description, list the main functions to verify.
- Walk each function using the android-emulator-skill scripts
  (`.agents/skills/android-emulator-skill/scripts/`):
  - `screen_mapper.py --serial <serial>` — inspect current UI
  - `navigator.py --find-text "..." --tap --serial <serial>` — tap
  - `navigator.py --find-class EditText --enter-text "..." --serial <serial>` — text entry
  - `gesture.py --swipe up --serial <serial>` — scroll
  - `keyboard.py --key BACK --serial <serial>` — back/home/enter
- Screenshot each reached screen: `work/<iid>/screenshots/NN-<name>.png`
- Crash during testing → logcat dump, `functions_ok: false`, note it.
- `functions_ok: true` only when all described main functions were usable.

## Phase 7: Permissions analysis

From `work/<iid>/metadata.json`:

- For each runtime (dangerous) permission: does the app prompt at first
  launch (bad — set `runtime_perms_ok: false`) or only when the feature is
  used (good)? Prompting at first launch for optional perms is a FAIL per
  the wiki guide.
- `MANAGE_EXTERNAL_STORAGE` present → `no_manage_storage: false` + note
  "suggest SAF instead".
- `has_internet` decides whether Phase 8 runs.

## Phase 8: Network capture (only if has_internet)

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

## Phase 9: Language support

English UI or description present → `english_ok: true`; otherwise
`english_ok: false` + note "English not supported; must be declared in the
description".

## Phase 10: VirusTotal (optional)

- Key exists (`.tokens/virustotal.key`):
  `curl -s --header "x-apikey: $(cat .tokens/virustotal.key)"
  "https://www.virustotal.com/api/v3/files/<sha256-of-apk>"` → set
  `virustotal_ok` from `data.attributes.last_analysis_stats` (mostly
  `undetected` → true).
- No key: ask the user to provide one (save to `.tokens/virustotal.key`,
  gitignored) or skip → leave `virustotal_ok` null.

## Phase 11: Report

Write `work/<iid>/results.json` with the schema below and
`work/<iid>/notes.txt` (one note per line), then:

    python3 .opencode/skills/fdroid-mr-review/scripts/report.py <iid> \
      --device "<serial or device name>" --results work/<iid>/results.json \
      --notes work/<iid>/notes.txt

Show `reports/<iid>-<package>.md` to the user, then ask whether to post it
as an MR comment (Phase 12) or let them post manually.

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

## Phase 12: Post comment (on user confirmation)

After showing the report in Phase 11, always ask the user first: "Post this
report as a comment on MR !<iid>?" — never post without confirmation.

1. If `.tokens/gitlab.token` is missing or empty: ask the user for a GitLab
   personal access token with `api` scope, save it to `.tokens/gitlab.token`
   (gitignored), or skip auto-posting (manual flow).
2. Post the full report:

   ```bash
   python3 .opencode/skills/fdroid-mr-review/scripts/post_comment.py <iid> \
     --report reports/<iid>-<package>.md
   ```

3. On success, show the comment URL from the output. On `401/403`: token
   invalid or missing `api` scope — tell the user, keep the manual posting
   flow.

## Phase 13: Cleanup

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
| Token missing / empty | ask user for token or skip auto-post |
| Token invalid (401/403) | tell user, post manually |

## Per-MR checklist

- [ ] Phase 0 prerequisites
- [ ] Phase 1 MR selected (or user provided iid)
- [ ] Phase 2 device + minSdk
- [ ] Phase 3 fetch + summary shown
- [ ] Phase 4 installed
- [ ] Phase 5 launch + baseline screenshots
- [ ] Phase 6 features tested + screenshots
- [ ] Phase 7 permissions analyzed
- [ ] Phase 8 network captured (if INTERNET)
- [ ] Phase 9 language checked
- [ ] Phase 10 VirusTotal (optional)
- [ ] Phase 11 report generated + shown
- [ ] Phase 12 comment posted (if user confirmed)
- [ ] Phase 13 cleanup confirmed
