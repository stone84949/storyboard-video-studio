#!/usr/bin/env python3
"""Prepare a storyboard bridge job for OpenMontage/manual montage finishing."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from studio_paths import path_for


VALID_TARGET = "montage"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "montage-handoff") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or fallback


def normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    duration = float(scene.get("duration") or scene.get("hold_seconds") or scene.get("vo_seconds") or 4)
    vo_seconds = float(scene.get("vo_seconds") or scene.get("duration") or duration)
    return {
        "index": index,
        "id": str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}"),
        "title": str(scene.get("title") or scene.get("shot_name") or scene.get("scene_description") or f"Scene {index}"),
        "asset": str(scene.get("asset") or scene.get("assetUrl") or scene.get("asset_url") or scene.get("image_filename") or "").strip(),
        "duration": max(0.5, duration),
        "vo_seconds": max(0.0, vo_seconds),
        "transition": str(scene.get("transition") or "crossfade"),
        "motion": str(scene.get("motion") or scene.get("motionPreset") or scene.get("motion_preset") or "slow push in"),
        "caption_mode": str(scene.get("caption_mode") or scene.get("captionMode") or "lower-third"),
        "narration": str(scene.get("narration") or scene.get("script") or scene.get("narration_text") or "").strip(),
        "notes": str(scene.get("notes") or "").strip(),
        "asset_state": str(scene.get("asset_state") or scene.get("assetState") or ("needs-image" if not scene.get("asset") else "candidate")),
    }


def normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else {}
    raw_scenes = storyboard.get("scenes") if storyboard else payload.get("scenes")
    scenes = [normalize_scene(scene, i) for i, scene in enumerate(raw_scenes or [], start=1)]
    current = 0.0
    for scene in scenes:
        scene["start"] = round(current, 3)
        scene["end"] = round(current + scene["duration"], 3)
        current += scene["duration"]
    return {
        "job_id": project.get("job_id") or slugify(str(payload.get("project_title") or "montage-handoff")),
        "project_title": storyboard.get("title") or payload.get("project_title") or project.get("project_title") or "Montage Handoff",
        "aspect_ratio": storyboard.get("aspect_ratio") or payload.get("aspect_ratio") or project.get("aspect_ratio") or "9:16",
        "pipeline_target": project.get("pipeline_target") or storyboard.get("pipeline_target") or payload.get("pipeline_target") or VALID_TARGET,
        "target_duration_seconds": storyboard.get("total_duration_sec") or payload.get("target_duration_seconds") or round(current, 3),
        "project_notes": storyboard.get("project_notes") or payload.get("project_notes") or "",
        "voiceover_notes": storyboard.get("voiceover_notes") or payload.get("voiceover_notes") or "",
        "scenes": scenes,
    }


def write_editor_handoff(path: Path, normalized: dict[str, Any]) -> None:
    lines = [
        f"# Editor Handoff: {normalized['project_title']}",
        "",
        f"Pipeline: {normalized['pipeline_target']}",
        f"Aspect ratio: {normalized['aspect_ratio']}",
        f"Target duration: {normalized['target_duration_seconds']}s",
        f"Generated: {utc_now()}",
        "",
        "## Notes",
        "",
        normalized.get("project_notes") or "No project notes provided.",
        "",
        "## Voiceover",
        "",
        normalized.get("voiceover_notes") or "No voiceover notes provided.",
        "",
        "## Scene Timeline",
    ]
    for scene in normalized["scenes"]:
        lines.extend(
            [
                "",
                f"### {scene['index']}. {scene['title']}",
                f"- Time: {scene['start']:.1f}s - {scene['end']:.1f}s ({scene['duration']:.1f}s)",
                f"- Asset: {scene['asset'] or 'NEEDS IMAGE'}",
                f"- Asset state: {scene['asset_state']}",
                f"- Transition: {scene['transition']}",
                f"- Motion: {scene['motion']}",
                f"- Caption mode: {scene['caption_mode']}",
                f"- Narration: {scene['narration']}",
                f"- Notes: {scene['notes']}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_shotcut_notes(path: Path, normalized: dict[str, Any]) -> None:
    lines = [
        f"Shotcut / Resolve assembly notes for {normalized['project_title']}",
        "",
        "Import assets in scene order. Use the resolve-timeline.csv for timing.",
        "Treat rows with asset_state=needs-image or empty asset as replacement targets before final render.",
        "",
    ]
    for scene in normalized["scenes"]:
        lines.append(
            f"{scene['start']:.1f}-{scene['end']:.1f}s | {scene['title']} | {scene['transition']} | {scene['motion']} | {scene['asset'] or 'NEEDS IMAGE'}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_timeline_csv(path: Path, normalized: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "index",
                "scene_id",
                "title",
                "start_seconds",
                "end_seconds",
                "duration_seconds",
                "asset",
                "asset_state",
                "transition",
                "motion",
                "caption_mode",
                "narration",
                "notes",
            ],
        )
        writer.writeheader()
        for scene in normalized["scenes"]:
            writer.writerow(
                {
                    "index": scene["index"],
                    "scene_id": scene["id"],
                    "title": scene["title"],
                    "start_seconds": scene["start"],
                    "end_seconds": scene["end"],
                    "duration_seconds": scene["duration"],
                    "asset": scene["asset"],
                    "asset_state": scene["asset_state"],
                    "transition": scene["transition"],
                    "motion": scene["motion"],
                    "caption_mode": scene["caption_mode"],
                    "narration": scene["narration"],
                    "notes": scene["notes"],
                }
            )


def prepare_handoff(project_json: Path, openmontage_root: Path | None = None) -> dict[str, Any]:
    project_json = project_json.resolve()
    job_dir = project_json.parent
    project = json.loads(project_json.read_text(encoding="utf-8"))
    normalized = normalize_project(project)
    if normalized["pipeline_target"] != VALID_TARGET:
        raise ValueError(f"Expected pipeline_target={VALID_TARGET}, got {normalized['pipeline_target']!r}")
    if not normalized["scenes"]:
        raise ValueError("Montage handoff requires at least one scene")

    exports_dir = job_dir / "exports"
    editor_dir = job_dir / "editor-handoff"
    exports_dir.mkdir(exist_ok=True)
    editor_dir.mkdir(exist_ok=True)

    om_root = openmontage_root or path_for("openmontage_root")
    om_project_dir = om_root / "projects" / f"{normalized['job_id']}-openmontage-handoff"
    om_project_dir.mkdir(parents=True, exist_ok=True)
    (om_project_dir / "storyboard").mkdir(exist_ok=True)
    (om_project_dir / "editor-handoff").mkdir(exist_ok=True)
    (om_project_dir / "renders").mkdir(exist_ok=True)

    package = {
        "schema_version": "storyboard-video-studio/openmontage-handoff/v1",
        "created_at": utc_now(),
        "source_project_json": str(project_json),
        "openmontage_project_dir": str(om_project_dir),
        **normalized,
        "handoff_files": {
            "editor_handoff_md": "editor-handoff/editor-handoff.md",
            "shotcut_notes": "editor-handoff/shotcut-notes.txt",
            "resolve_timeline_csv": "editor-handoff/resolve-timeline.csv",
            "storyboard_json": "storyboard/storyboard-handoff.json",
        },
    }

    job_package_path = exports_dir / "openmontage-handoff.json"
    job_package_path.write_text(json.dumps(package, indent=2), encoding="utf-8")
    write_editor_handoff(exports_dir / "editor-handoff.md", normalized)
    write_shotcut_notes(editor_dir / "shotcut-notes.txt", normalized)
    write_timeline_csv(editor_dir / "resolve-timeline.csv", normalized)

    shutil.copy2(job_package_path, om_project_dir / "storyboard" / "storyboard-handoff.json")
    write_editor_handoff(om_project_dir / "editor-handoff" / "editor-handoff.md", normalized)
    write_shotcut_notes(om_project_dir / "editor-handoff" / "shotcut-notes.txt", normalized)
    write_timeline_csv(om_project_dir / "editor-handoff" / "resolve-timeline.csv", normalized)
    (om_project_dir / "STATUS.md").write_text(
        f"# {normalized['project_title']}\n\n"
        "Status: handoff-ready\n"
        f"Source: {project_json}\n"
        "Next: OpenMontage agent/director can turn storyboard/storyboard-handoff.json into a render plan.\n",
        encoding="utf-8",
    )

    result = {
        "ok": True,
        "status": "handoff_ready",
        "job_dir": str(job_dir),
        "openmontage_project_dir": str(om_project_dir),
        "files": {
            "job_handoff": str(job_package_path),
            "job_editor_handoff": str(exports_dir / "editor-handoff.md"),
            "job_shotcut_notes": str(editor_dir / "shotcut-notes.txt"),
            "job_resolve_timeline": str(editor_dir / "resolve-timeline.csv"),
            "openmontage_storyboard": str(om_project_dir / "storyboard" / "storyboard-handoff.json"),
        },
    }
    (exports_dir / "openmontage-summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an OpenMontage montage handoff from a bridge project.json")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("--openmontage-root", type=Path)
    args = parser.parse_args()
    try:
        result = prepare_handoff(args.project_json, args.openmontage_root)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
