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
