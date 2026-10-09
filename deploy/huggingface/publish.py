"""Publish the Flowline online demo to Hugging Face Spaces.

    .venv/bin/python deploy/huggingface/publish.py <hf-user> bundle   # build data bundle
    .venv/bin/python deploy/huggingface/publish.py <hf-user> data     # upload bundle
    .venv/bin/python deploy/huggingface/publish.py <hf-user> space    # upload app
    .venv/bin/python deploy/huggingface/publish.py <hf-user> all      # all three

Needs `pip install huggingface_hub` and `hf auth login` (a write token). Nothing secret
is uploaded: the data bundle holds only public, CER/OSM-derived tables (no decision log,
no crew edits, no usage logs), and the app is a `git archive` of the committed code.
The Gemini key and Mapbox token are set as Space secrets in the Hugging Face UI.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT / "deploy" / "huggingface"
BUNDLE = HERE / ".bundle"
SPACE_NAME = "flowline"
DATASET_NAME = "flowline-data"

# Public, regenerable tables only. Crew tables are re-seeded as sample data in the image.
PUBLIC_TABLES = [
    "incidents",
    "incident_weather",
    "incident_embeddings",
    "incident_context",
    "ranking_incidents",
    "corridors",
    "pipelines",
    "similarity_meta",
    "waterway_crossings",
]

SPACE_CARD = """---
title: Flowline Hazard Forecast
emoji: 🛠️
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: true
short_description: Pipeline hazard forecast and emergency dispatch (demo)
---

# Flowline Hazard Forecast — online demo

Forecast the mix of pipeline hazards for any area and week from public Canada Energy
Regulator incident history, see the evidence, get the right crews ready, and in an
emergency send the nearest matching crew by real drive time.

This is a free demo by a student team. Each visitor gets **3 AI prompts per day**, and
edits and decisions stay private to your browser for 24 hours.

Code, install instructions and the honest model report:
https://github.com/ovie-d/FlowLine

Forecasts are based on historical public incident data. Flowline supports engineering
judgment; it does not certify any pipe as safe.
"""


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("$", " ".join(cmd))
    return subprocess.run(cmd, check=True, **kw)


def in_docker_group(shell_cmd: str) -> list[str]:
    """Run a docker command directly, or via `sg docker` if this shell predates the group."""
    ok = (
        subprocess.run(["docker", "info"], capture_output=True, check=False).returncode
        == 0
    )
    return ["bash", "-c", shell_cmd] if ok else ["sg", "docker", "-c", shell_cmd]


def bundle() -> None:
    """Database snapshot (public tables) + OSRM graph, into deploy/huggingface/.bundle/."""
    BUNDLE.mkdir(exist_ok=True)
    dump = BUNDLE / "flowline-db.dump"
    tables = " ".join(f"-t public.{t}" for t in PUBLIC_TABLES)
    cmd = in_docker_group(
        f"docker compose exec -T db pg_dump -U flowline -d flowline -Fc --no-owner {tables}"
    )
    with dump.open("wb") as fh:
        run(cmd, stdout=fh, cwd=ROOT)
    print(f"database snapshot: {dump.stat().st_size / 1e6:.1f} MB")

    osrm = ROOT / "osrm"
    files = sorted(p for p in osrm.glob("alberta-latest.osrm*") if p.is_file())
    if not any(p.name.endswith(".mldgr") for p in files):
        sys.exit("No OSRM graph in osrm/ (run ./start.sh once so it is built).")
    # OSRM's container writes some files as root-only; make them readable for tar.
    run(in_docker_group(f"docker run --rm -v {osrm}:/d alpine chmod a+r /d -R"))
    out = BUNDLE / "osrm-alberta.tar.zst"
    tar_cmd = [
        "tar",
        "--zstd",
        "-cf",
        str(out),
        "-C",
        str(osrm),
        *[p.name for p in files],
    ]
    run(tar_cmd)
    print(f"routing graph: {out.stat().st_size / 1e6:.1f} MB")


def _api():
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit(
            "Install the Hugging Face client first: .venv/bin/pip install huggingface_hub"
        )
    return HfApi()


def upload_data(user: str) -> None:
    api = _api()
    repo = f"{user}/{DATASET_NAME}"
    api.create_repo(repo, repo_type="dataset", private=False, exist_ok=True)
    for name in ("flowline-db.dump", "osrm-alberta.tar.zst"):
        path = BUNDLE / name
        if not path.exists():
            sys.exit(f"Missing {path}; run the 'bundle' step first.")
        print(
            f"uploading {name} ({path.stat().st_size / 1e6:.0f} MB) to datasets/{repo}…"
        )
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=name,
            repo_id=repo,
            repo_type="dataset",
        )
    api.upload_file(
        path_or_fileobj=(
            b"# Flowline online-demo data\n\nPublic, regenerable data for the Flowline "
            b"Hugging Face Space: a PostgreSQL snapshot of CER pipeline incident data "
            b"(Open Government Licence - Canada) with ECCC weather features, and an OSRM "
            b"routing graph built from OpenStreetMap (ODbL, (c) OpenStreetMap "
            b"contributors). Source code: https://github.com/ovie-d/FlowLine\n"
        ),
        path_in_repo="README.md",
        repo_id=repo,
        repo_type="dataset",
    )


def stage_space(user: str) -> Path:
    """The committed code (git archive), the Space Dockerfile at the root and the card."""
    stage = BUNDLE / "space"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    archive = BUNDLE / "space.tar"
    run(["git", "archive", "--format=tar", "-o", str(archive), "HEAD"], cwd=ROOT)
    with tarfile.open(archive) as tar:
        tar.extractall(stage, filter="data")
    archive.unlink()
    data_url = f"https://huggingface.co/datasets/{user}/{DATASET_NAME}/resolve/main"
    dockerfile = (
        (HERE / "Dockerfile")
        .read_text()
        .replace("ARG FLOWLINE_DATA_URL\n", f"ARG FLOWLINE_DATA_URL={data_url}\n")
    )
    (stage / "Dockerfile").write_text(dockerfile)
    (stage / "README.md").write_text(SPACE_CARD)
    return stage


def upload_space(user: str) -> None:
    stage = stage_space(user)
    api = _api()
    repo = f"{user}/{SPACE_NAME}"
    api.create_repo(
        repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True
    )
    api.upload_folder(
        folder_path=str(stage),
        repo_id=repo,
        repo_type="space",
        commit_message="Deploy Flowline from GitHub",
        delete_patterns=["*"],
    )
    print(f"Space: https://huggingface.co/spaces/{repo}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("user", help="Hugging Face user or organisation")
    p.add_argument("step", choices=["bundle", "data", "space", "all"])
    a = p.parse_args()
    if a.step in {"bundle", "all"}:
        bundle()
    if a.step in {"data", "all"}:
        upload_data(a.user)
    if a.step in {"space", "all"}:
        upload_space(a.user)


if __name__ == "__main__":
    main()
