#!/usr/bin/env python3
"""Post a generated report as a comment on the F-Droid MR."""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

GITLAB_API = "https://gitlab.com/api/v4"
UPSTREAM_PROJECT = "fdroid%2Ffdroiddata"
TOKEN_PATH = Path(".tokens/gitlab.token")


def get_mr(iid: int) -> dict:
    with urllib.request.urlopen(
        f"{GITLAB_API}/projects/{UPSTREAM_PROJECT}/merge_requests/{iid}", timeout=60
    ) as resp:
        return json.load(resp)


def load_token(path: Path) -> str:
    token = path.read_text().strip()
    if not token:
        raise ValueError(f"token file is empty: {path}")
    return token


def notes_url(project_id: int, iid: int) -> str:
    return f"{GITLAB_API}/projects/{project_id}/merge_requests/{iid}/notes"


def post_note(project_id: int, iid: int, body: str, token: str) -> dict:
    req = urllib.request.Request(
        notes_url(project_id, iid),
        data=json.dumps({"body": body}).encode(),
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post an F-Droid review report as an MR comment"
    )
    parser.add_argument("iid", type=int, help="MR iid, e.g. 45475")
    parser.add_argument("--report", required=True, help="report markdown file to post")
    parser.add_argument("--token", default=None, help="token file (default: .tokens/gitlab.token)")
    args = parser.parse_args()

    token_path = Path(args.token) if args.token else TOKEN_PATH
    if not token_path.exists():
        print(f"ERROR: token file not found: {token_path}", file=sys.stderr)
        return 1
    try:
        token = load_token(token_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    report = Path(args.report)
    if not report.exists():
        print(f"ERROR: report file not found: {report}", file=sys.stderr)
        return 1
    body = report.read_text()

    mr = get_mr(args.iid)
    project_id = mr["project_id"]
    print(f"Posting comment on MR !{args.iid} (project {project_id}) ...")
    note = post_note(project_id, args.iid, body, token)
    print(f"Comment posted: {note['web_url']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
