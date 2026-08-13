#!/usr/bin/env python3
"""List open fdroiddata MRs ready for testing and not yet reviewed."""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

GITLAB_API = "https://gitlab.com/api/v4"
UPSTREAM_PROJECT = "fdroid%2Ffdroiddata"
REVIEW_LABEL = "review-requested"
TESTER_MARKER = "Tester review"
TOKEN_PATH = Path(".tokens/gitlab.token")


def api_get(url: str, token: str = None):
    headers = {"PRIVATE-TOKEN": token} if token else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def list_mrs(per_page: int = 20, token: str = None) -> list:
    url = (
        f"{GITLAB_API}/projects/{UPSTREAM_PROJECT}/merge_requests"
        f"?state=opened&labels={REVIEW_LABEL}&sort=asc&order_by=created_at&per_page={per_page}"
    )
    return api_get(url, token)


def get_mr(iid: int, token: str = None) -> dict:
    return api_get(f"{GITLAB_API}/projects/{UPSTREAM_PROJECT}/merge_requests/{iid}", token)


def get_mr_notes(iid: int, token: str = None) -> list:
    return api_get(
        f"{GITLAB_API}/projects/{UPSTREAM_PROJECT}/merge_requests/{iid}/notes", token
    )


def load_token(path: Path = TOKEN_PATH) -> str:
    if not path.exists():
        return None
    token = path.read_text().strip()
    return token or None


def is_ready(mr: dict) -> bool:
    head = mr.get("head_pipeline")
    return bool(head) and head.get("status") == "success"


def is_tested(notes: list) -> bool:
    return any(TESTER_MARKER in note.get("body", "") for note in notes)


def format_row(row: dict) -> str:
    tested = row["tested"]
    if tested is None:
        tested_label = "unknown"
    else:
        tested_label = "yes" if tested else "no"
    return (
        f"!{row['iid']} {row['title']}"
        f" | pipeline: {row['pipeline']} | tested: {tested_label}"
    )


def summarize(rows: list) -> list:
    return [row["iid"] for row in rows if row["ready"] and row["tested"] is False]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List open fdroiddata MRs ready for testing"
    )
    parser.add_argument("--per-page", type=int, default=20, help="MRs to inspect (default: 20)")
    parser.add_argument("--token", default=None, help="token file (default: .tokens/gitlab.token)")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    token = load_token(Path(args.token) if args.token else TOKEN_PATH)
    if not token:
        print(
            "WARNING: no GitLab token found; 'tested' status will be unknown "
            "(MR notes require auth). Use .tokens/gitlab.token for accurate detection.",
            file=sys.stderr,
        )

    print(f"Fetching open MRs labeled '{REVIEW_LABEL}' ...", file=sys.stderr)
    mrs = list_mrs(args.per_page, token)
    if not mrs:
        print("No open MRs found.", file=sys.stderr)
        return 1

    rows = []
    for mr in mrs:
        detail = get_mr(mr["iid"], token)
        pipeline = (detail.get("head_pipeline") or {}).get("status")
        ready = pipeline == "success"
        tested = None
        if ready:
            try:
                tested = is_tested(get_mr_notes(mr["iid"], token))
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    print(
                        f"WARNING: cannot read notes for !{mr['iid']} "
                        f"(HTTP {exc.code}); 'tested' unknown.",
                        file=sys.stderr,
                    )
                    tested = None
                else:
                    raise
        rows.append(
            {
                "iid": mr["iid"],
                "title": mr["title"],
                "pipeline": pipeline,
                "ready": ready,
                "tested": tested,
            }
        )

    candidates = summarize(rows)
    if args.json:
        print(json.dumps({"rows": rows, "candidates": candidates}, indent=2))
        return 0

    print(f"\n# Open MRs ({REVIEW_LABEL}): {len(rows)}")
    for row in rows:
        print(format_row(row))
    print(f"\n# Ready and not yet tested: {len(candidates)}")
    for iid in candidates:
        print(f"!{iid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
