#!/usr/bin/env python3
"""Build dashboard data for Storyboard Video Studio.

The dashboard is intentionally static. This script scans the repo's `videos/`
folder plus known local finish-layer handoffs and writes
`dashboard/data/projects.json`.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from studio_paths import path_for  # noqa: E402

VIDEOS_DIR = REPO_ROOT / "videos"
DASHBOARD_DATA = REPO_ROOT / "dashboard" / "data" / "projects.json"
OPENMONTAGE_ROOT = path_for("openmontage_root", Path(r"C:\Workspace\Repos\OpenMontage"))
CONTENT_FACTORY_ROOT = path_for("content_factory_root", Path(r"G:\My Drive\Projects\Active\content-factory-render"))
CONTENT_FACTORY_OUT = path_for("content_factory_out", CONTENT_FACTORY_ROOT / "out")

STAGES = [
    ("idea", "Idea"),
    ("script", "Script"),
    ("storyboard", "Storyboard"),
    ("assets", "Asset research"),
    ("design", "Open Design"),
    ("assemble", "Assemble"),
    ("render", "Render"),
    ("qa", "QA"),
]


def file_info(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def count_storyboard_scenes(path: Path) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8", errors="ignore")
    return sum(1 for line in text.splitlines() if line.strip().lower().startswith("## scene"))


def read_asset_board(path: Path) -> dict[str, Any]:
    summary = {
        "total": 0,
        "approved": 0,
        "needs_review": 0,
        "missing_local": 0,
        "malformed_rows": 0,
        "statuses": {},
    }
    if not path.exists():
        return summary

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summary["total"] += 1
            status = (row.get("status") or "unknown").strip().lower() or "unknown"
            if status not in {
                "approved",
                "candidate",
                "needs-review",
                "needs review",
                "rejected",
                "downloaded",
                "missing",
                "unknown",
            }:
                summary["malformed_rows"] += 1
                status = "needs-review"
            summary["statuses"][status] = summary["statuses"].get(status, 0) + 1
            if status == "approved":
                summary["approved"] += 1
            if status in {"candidate", "needs-review", "needs review", "unknown"}:
                summary["needs_review"] += 1
            local_path = (row.get("local_path") or "").strip()
            if not local_path:
                summary["missing_local"] += 1
    return summary


def parse_handoff(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for i, line in enumerate(lines):
        lowered = line.strip().lower()
        if lowered.startswith("c:\\") and "openmontage" in lowered:
            if "renders" in lowered and "final.mp4" in lowered:
                result["render_path"] = line.strip()
            elif "projects" in lowered:
                result.setdefault("openmontage_project", line.strip())
        if "final draft render" in lowered:
            for candidate in lines[i + 1 : i + 6]:
                stripped = candidate.strip()
                if stripped.lower().startswith("c:\\"):
                    result["render_path"] = stripped
                    break
    return result


def stage_status(video_dir: Path, handoff: dict[str, str], asset_summary: dict[str, Any]) -> dict[str, str]:
    storyboard = video_dir / "storyboard.md"
    asset_board = video_dir / "asset-board.csv"
    design_notes = video_dir / "open-design-notes.md"
    render_path = Path(handoff["render_path"]) if handoff.get("render_path") else None
    openmontage_project = (
        Path(handoff["openmontage_project"]) if handoff.get("openmontage_project") else None
    )

    statuses = {key: "missing" for key, _ in STAGES}
    if storyboard.exists():
        statuses["idea"] = "done"
        statuses["script"] = "partial"
        statuses["storyboard"] = "done"
    if asset_board.exists():
        statuses["assets"] = "review" if asset_summary["needs_review"] else "done"
    if design_notes.exists():
        statuses["design"] = "done"
    elif handoff:
        statuses["design"] = "partial"
    if openmontage_project and openmontage_project.exists():
        statuses["assemble"] = "done"
    if render_path and render_path.exists():
        statuses["render"] = "done"
        statuses["qa"] = "partial"
    return statuses


def next_action(statuses: dict[str, str], asset_summary: dict[str, Any]) -> str:
    if statuses["storyboard"] == "missing":
        return "Create or import the storyboard."
    if statuses["assets"] == "missing":
        return "Run the Asset Researcher planning pass."
    if asset_summary["malformed_rows"]:
        return f"Fix {asset_summary['malformed_rows']} malformed asset-board row(s)."
    if asset_summary["needs_review"]:
        return f"Review {asset_summary['needs_review']} asset candidate(s)."
    if asset_summary["missing_local"]:
        return f"Attach or approve local files for {asset_summary['missing_local']} asset row(s)."
    if statuses["design"] == "missing":
        return "Pick an Open Design template lane."
    if statuses["render"] == "missing":
        return "Send the approved storyboard and assets to OpenMontage."
    if statuses["qa"] != "done":
        return "Review the render and mark QA notes."
    return "Ready for publishing prep."


def project_for(video_dir: Path) -> dict[str, Any]:
    slug = video_dir.name
    storyboard = video_dir / "storyboard.md"
    asset_board = video_dir / "asset-board.csv"
    handoff_file = video_dir / "finish-layer-handoff.md"
    handoff = parse_handoff(handoff_file)
    asset_summary = read_asset_board(asset_board)
    statuses = stage_status(video_dir, handoff, asset_summary)
    render_path = Path(handoff["render_path"]) if handoff.get("render_path") else None
    openmontage_project = (
        Path(handoff["openmontage_project"]) if handoff.get("openmontage_project") else None
    )
    hyperframes_dir = openmontage_project / "hyperframes" if openmontage_project else None

    return {
        "slug": slug,
        "title": slug.replace("-", " ").title(),
        "path": str(video_dir),
        "updated": datetime.fromtimestamp(video_dir.stat().st_mtime, timezone.utc).isoformat(),
        "scene_count": count_storyboard_scenes(storyboard),
        "stage_status": statuses,
        "next_action": next_action(statuses, asset_summary),
        "files": {
            "storyboard": file_info(storyboard),
            "asset_board": file_info(asset_board),
            "handoff": file_info(handoff_file),
            "render": file_info(render_path) if render_path else None,
            "hyperframes_index": file_info(hyperframes_dir / "index.html") if hyperframes_dir else None,
        },
        "asset_summary": asset_summary,
        "links": {
            "hyperframes_preview": "http://localhost:3017/#project/hyperframes"
            if slug == "weird-forgotten-history-hyperframes-pilot"
            else "",
            "openmontage_project": str(openmontage_project) if openmontage_project else "",
            "render_path": str(render_path) if render_path else "",
        },
    }


def main() -> None:
    projects = []
    if VIDEOS_DIR.exists():
        for video_dir in sorted(p for p in VIDEOS_DIR.iterdir() if p.is_dir()):
            projects.append(project_for(video_dir))

    done_counts = {key: 0 for key, _ in STAGES}
    for project in projects:
        for key, status in project["stage_status"].items():
            if status == "done":
                done_counts[key] += 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(REPO_ROOT),
        "openmontage_root": str(OPENMONTAGE_ROOT),
        "content_factory_root": str(CONTENT_FACTORY_ROOT),
        "content_factory_out": str(CONTENT_FACTORY_OUT),
        "stages": [{"key": key, "label": label} for key, label in STAGES],
        "summary": {
            "project_count": len(projects),
            "rendered_count": sum(1 for p in projects if p["stage_status"]["render"] == "done"),
            "needs_asset_review": sum(
                1 for p in projects if p["asset_summary"]["needs_review"] > 0
            ),
            "done_counts": done_counts,
        },
        "projects": projects,
    }
    DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DATA.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {DASHBOARD_DATA}")


if __name__ == "__main__":
    main()
