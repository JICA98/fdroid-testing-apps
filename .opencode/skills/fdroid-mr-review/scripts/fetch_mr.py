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
    for name in zip_names:
        if name.startswith("tmp/signed/") and name.endswith(".signed.apk"):
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
    sdk = re.search(r"(?:minSdkVersion|sdkVersion):'(\d+)'", output)
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
