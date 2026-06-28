#!/usr/bin/env python3
"""
storyboard_to_config.py
========================
Reads a filled-in storyboard CSV and writes a valid job_config.json
that feeds directly into process_images.py and the HyperFrames pipeline.

Usage:
    python scripts/storyboard_to_config.py storyboard.csv
    python scripts/storyboard_to_config.py storyboard.csv --preview
    python scripts/storyboard_to_config.py storyboard.csv --open-folder

Outputs:
    videos/<job_id>/job_config.json
    videos/<job_id>/assets/images/src/   (folder created, ready for images)
    videos/<job_id>/storyboard.csv       (copy saved for reference)

CSV Format (two sections separated by blank line):
    Section 1 (row 1 = headers, row 2 = values): job-level settings
    Section 2 (row 1 = headers, rows 2+ = panels): per-panel image/scene data
"""

import csv, json, sys, os, shutil, argparse
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
VALID_MODES      = {"fit", "fill", "pad", "stretch"}
MAX_DURATION     = 179
DEFAULT_RES      = (1080, 1920)
DEFAULT_CODEC    = "libx264"
DEFAULT_CRF      = 18
DEFAULT_PRESET   = "veryfast"
# ─────────────────────────────────────────────────────────────────────────────


def parse_storyboard_csv(csv_path: Path):
    """Parse two-section storyboard CSV. Returns (job_meta dict, panels list)."""
    lines = csv_path.read_text(encoding="utf-8").splitlines()

    # Split on blank line
    sections = []
    current = []
    for line in lines:
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append(line)
    if current:
        sections.append(current)

    if len(sections) < 2:
        raise ValueError("CSV must have two sections separated by a blank line. "
                         "See storyboard_template.csv for format.")

    # Section 1: job metadata (header row + value row)
    job_reader  = list(csv.DictReader(sections[0]))
    if not job_reader:
        raise ValueError("Job metadata section is empty.")
    job_meta = job_reader[0]

    # Section 2: panels
    panels = list(csv.DictReader(sections[1]))
    if not panels:
        raise ValueError("Panel section is empty — add at least one panel row.")

    return job_meta, panels


def build_job_config(job_meta: dict, panels: list) -> dict:
    """Convert parsed CSV rows into a validated job_config dict."""

    job_id = job_meta.get("job_id", "").strip()
    if not job_id:
        raise ValueError("job_id is required in the job metadata row.")

    target_dur = float(job_meta.get("target_duration_seconds", 60))
    if target_dur > MAX_DURATION:
        raise ValueError(f"target_duration_seconds ({target_dur}) exceeds max {MAX_DURATION}s.")

    w = int(job_meta.get("resolution_w", DEFAULT_RES[0]))
    h = int(job_meta.get("resolution_h", DEFAULT_RES[1]))

    # Build script from narration column (joined panels)
    script_lines = [p["narration_text"].strip() for p in panels if p.get("narration_text","").strip()]
    full_script  = " ".join(script_lines)

    # Build images array
    images = []
    for i, panel in enumerate(panels, start=1):
        fname = panel.get("image_filename","").strip()
        if not fname:
            print(f"  WARNING: Panel {i} has no image_filename — skipping image entry.")
            continue

        mode = panel.get("image_mode","pad").strip().lower()
        if mode not in VALID_MODES:
            print(f"  WARNING: Panel {i} mode '{mode}' invalid — defaulting to 'pad'.")
            mode = "pad"

        try:
            fx = float(panel.get("focal_x", 0.5))
            fy = float(panel.get("focal_y", 0.5))
        except ValueError:
            fx, fy = 0.5, 0.5

        allow_up_raw = panel.get("allow_upscale","false").strip().lower()
        allow_upscale = allow_up_raw in ("true","1","yes")

        hold = panel.get("hold_seconds","").strip()

        entry = {
            "panel":        i,
            "filename":     fname,
            "mode":         mode,
            "focal_point":  {"x_pct": fx, "y_pct": fy},
            "allow_upscale": allow_upscale,
            "scene_description": panel.get("scene_description","").strip(),
            "narration":    panel.get("narration_text","").strip(),
            "notes":        panel.get("notes","").strip(),
        }
        if hold:
            try:
                entry["hold_seconds"] = float(hold)
            except ValueError:
                pass

        images.append(entry)

    config = {
        "job_id":                   job_id,
        "title":                    job_meta.get("title", job_id).strip(),
        "input_text":               full_script,
        "target_duration_seconds":  target_dur,
        "resolution":               {"width": w, "height": h},
        "aspect_ratio":             job_meta.get("aspect_ratio","9:16").strip(),
        "image_folder":             f"videos/{job_id}/assets/images/src",
        "images":                   images,
        "output_format": {
            "container": "mp4",
            "codec":     job_meta.get("codec", DEFAULT_CODEC).strip(),
            "hw_accel":  None,
            "crf":       int(job_meta.get("crf",  DEFAULT_CRF)),
            "preset":    job_meta.get("preset", DEFAULT_PRESET).strip()
        }
    }
    return config


def build_job_config_from_bridge_project(project: dict) -> dict:
    """Convert bridge project.json into the same render config shape as CSV input."""
    payload = project.get("payload", project)
    scenes = payload.get("scenes") or []
    job_id = project.get("job_id") or payload.get("job_id") or payload.get("project_title") or "storyboard-job"
    job_id = str(job_id).strip().replace(" ", "-").lower()
    target = project.get("pipeline_target") or payload.get("pipeline_target") or "short-shorts"
    target_duration = float(payload.get("target_duration_seconds") or sum(float(s.get("duration", 0) or 0) for s in scenes) or 30)
    script_lines = [str(scene.get("narration", "")).strip() for scene in scenes if str(scene.get("narration", "")).strip()]

    images = []
    for i, scene in enumerate(scenes, start=1):
        images.append({
            "panel": i,
            "filename": str(scene.get("asset") or scene.get("image_filename") or f"scene-{i:03d}.jpg").strip(),
            "mode": str(scene.get("image_mode") or "fill").lower(),
            "focal_point": {"x_pct": float(scene.get("focal_x", 0.5) or 0.5), "y_pct": float(scene.get("focal_y", 0.5) or 0.5)},
            "allow_upscale": bool(scene.get("allow_upscale", False)),
            "scene_description": str(scene.get("title") or scene.get("scene_description") or "").strip(),
            "narration": str(scene.get("narration") or "").strip(),
            "notes": str(scene.get("notes") or "").strip(),
            "hold_seconds": float(scene.get("duration", scene.get("hold_seconds", 0)) or 0),
            "motion": str(scene.get("motion") or "slow Ken Burns").strip(),
        })

    return {
        "job_id": job_id,
        "title": str(payload.get("project_title") or project.get("project_title") or job_id).strip(),
        "input_text": " ".join(script_lines),
        "target_duration_seconds": target_duration,
        "resolution": {"width": DEFAULT_RES[0], "height": DEFAULT_RES[1]},
        "aspect_ratio": str(payload.get("aspect_ratio") or project.get("aspect_ratio") or "9:16"),
        "pipeline_target": target,
        "image_folder": "assets/images/src",
        "images": images,
        "output_format": {
            "container": "mp4",
            "codec": DEFAULT_CODEC,
            "hw_accel": None,
            "crf": DEFAULT_CRF,
            "preset": DEFAULT_PRESET,
        },
    }


def scaffold_job_folder(config: dict, src_csv: Path, base_dir: Path | None = None, source_format: str = "csv"):
    """Create job folder structure and write job_config.json + image src folder."""
    job_id = config["job_id"]
    if base_dir is not None:
        job_dir = base_dir
    elif source_format == "json":
        job_dir = src_csv.parent
    else:
        job_dir = Path(f"videos/{job_id}")
    img_src = job_dir / "assets" / "images" / "src"
    img_proc = job_dir / "assets" / "images" / "processed"
    out_dir = job_dir / "out"
    logs_dir = job_dir / "logs"
    exports_dir = job_dir / "exports"
    handoff_dir = job_dir / "editor-handoff"

    for d in [img_src, img_proc, out_dir, logs_dir, exports_dir, handoff_dir]:
        d.mkdir(parents=True, exist_ok=True)

    cfg_path = (exports_dir / "job_config.json") if source_format == "json" else (job_dir / "job_config.json")
    cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    if source_format == "json":
        storyboard_dir = job_dir / "storyboard"
        storyboard_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(src_csv, storyboard_dir / "source-project.json")
    else:
        shutil.copy(src_csv, job_dir / "storyboard.csv")

    checklist_lines = [
        f"# Image Checklist for: {config['title']}",
        f"# Place each image in:  {img_src}",
        f"# Config:              {cfg_path}",
        "",
        f"{'Panel':<6} {'Filename':<30} {'Mode':<8} {'Focal X':<9} {'Focal Y':<9} Scene",
        "-" * 90,
    ]
    for img in config["images"]:
        checklist_lines.append(
            f"{img['panel']:<6} {img['filename']:<30} {img['mode']:<8} "
            f"{img['focal_point']['x_pct']:<9} {img['focal_point']['y_pct']:<9} "
            f"{img['scene_description'][:40]}"
        )
    checklist_lines += [
        "",
        "# Next steps:",
        f"# 1. Drop your images into:  {img_src}",
        f"# 2. Process images/render using the pipeline command in launch-command.txt",
        f"# 3. Editor handoff:        {exports_dir / 'editor-handoff.md'}",
    ]
    (job_dir / "IMAGE_CHECKLIST.txt").write_text("\n".join(checklist_lines), encoding="utf-8")

    handoff_lines = [
        f"# Editor Handoff: {config['title']}",
        "",
        f"Pipeline: {config.get('pipeline_target', 'short-shorts')}",
        f"Aspect ratio: {config.get('aspect_ratio', '9:16')}",
        f"Target duration: {config.get('target_duration_seconds')}s",
        "",
        "## Scenes",
    ]
    for img in config["images"]:
        handoff_lines += [
            "",
            f"### {img['panel']}. {img.get('scene_description', '')}",
            f"- Asset: {img.get('filename', '')}",
            f"- Duration: {img.get('hold_seconds', '')}s",
            f"- Motion: {img.get('motion', 'slow Ken Burns')}",
            f"- Narration: {img.get('narration', '')}",
        ]
    (exports_dir / "editor-handoff.md").write_text("\n".join(handoff_lines) + "\n", encoding="utf-8")

    return job_dir, cfg_path, img_src


def print_preview(config: dict):
    """Print a human-readable summary of what will be built."""
    print("\n" + "="*60)
    print(f"  JOB PREVIEW: {config['title']}")
    print("="*60)
    print(f"  job_id:    {config['job_id']}")
    print(f"  duration:  {config['target_duration_seconds']}s  (max 179s)")
    print(f"  res:       {config['resolution']['width']}x{config['resolution']['height']}")
    print(f"  panels:    {len(config['images'])}")
    print()
    print(f"  {'#':<4} {'Image':<30} {'Mode':<8} {'Focal':<12} Scene")
    print(f"  {'-'*4} {'-'*30} {'-'*8} {'-'*12} {'-'*30}")
    for img in config["images"]:
        focal = f"({img['focal_point']['x_pct']},{img['focal_point']['y_pct']})"
        scene = img["scene_description"][:30]
        print(f"  {img['panel']:<4} {img['filename']:<30} {img['mode']:<8} {focal:<12} {scene}")
    print()
    total_hold = sum(i.get("hold_seconds",0) for i in config["images"])
    if total_hold > 0:
        print(f"  Total panel hold time: {total_hold}s")
    print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Convert storyboard CSV/bridge JSON to job_config.json")
    parser.add_argument("storyboard_file", help="Path to storyboard CSV or bridge project.json file")
    parser.add_argument("--target", choices=["short-shorts", "longer-shorts", "montage"],
                        help="Override pipeline target for bridge JSON input")
    parser.add_argument("--preview", "--dry-run", action="store_true", dest="preview",
                        help="Print a preview table without writing files")
    parser.add_argument("--open-folder", action="store_true",
                        help="Open the image folder in Explorer/Finder after creation (Windows/Mac)")
    args = parser.parse_args()

    source_path = Path(args.storyboard_file)
    if not source_path.exists():
        print(f"ERROR: File not found: {source_path}")
        sys.exit(1)

    print(f"\nReading storyboard: {source_path}")
    if source_path.suffix.lower() == ".json":
        project = json.loads(source_path.read_text(encoding="utf-8"))
        if args.target:
            project["pipeline_target"] = args.target
            project.setdefault("payload", {})["pipeline_target"] = args.target
        config = build_job_config_from_bridge_project(project)
        source_format = "json"
    else:
        job_meta, panels = parse_storyboard_csv(source_path)
        config = build_job_config(job_meta, panels)
        if args.target:
            config["pipeline_target"] = args.target
        source_format = "csv"

    print_preview(config)

    if args.preview:
        print("Preview only — no files written. Remove --preview/--dry-run to generate.")
        sys.exit(0)

    job_dir, cfg_path, img_src = scaffold_job_folder(config, source_path, source_format=source_format)

    print(f"✓  job_config.json  →  {cfg_path}")
    print(f"✓  Image src folder →  {img_src}")
    print(f"✓  Checklist        →  {job_dir}/IMAGE_CHECKLIST.txt")
    print(f"✓  Editor handoff   →  {job_dir}/exports/editor-handoff.md")
    print()
    print(f"  NEXT: Drop your images into  {img_src}")
    print(f"  THEN: continue with launch-command.txt or live renderer command")
    print()

    if args.open_folder:
        if sys.platform == "win32":
            os.startfile(str(img_src))
        elif sys.platform == "darwin":
            os.system(f"open \"{img_src}\"")
        else:
            os.system(f"xdg-open \"{img_src}\"")


if __name__ == "__main__":
    main()
