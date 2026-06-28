#!/usr/bin/env python3
"""Render a bridge storyboard job through HyperFrames.

This is the first live finish layer for the visual storyboard UI. It converts a
bridge ``project.json`` into a self-contained HyperFrames workspace, runs the
CLI, and writes the rendered MP4 back into the bridge job's exports folder.
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
VALID_TARGETS = {"short-shorts", "longer-shorts"}


def slugify(value: str, fallback: str = "scene") -> str:
    out = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:64] or fallback


def normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    duration = float(scene.get("duration") or scene.get("hold_seconds") or scene.get("vo_seconds") or 4)
    return {
        "id": str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}"),
        "title": str(scene.get("title") or scene.get("scene_description") or f"Scene {index}"),
        "asset": str(scene.get("asset") or scene.get("assetUrl") or scene.get("asset_url") or "").strip(),
        "narration": str(scene.get("narration") or scene.get("script") or "").strip(),
        "motion": str(scene.get("motion") or scene.get("motionPreset") or "slow push in").strip(),
        "duration": max(0.5, duration),
    }


def normalize_payload(project: dict[str, Any]) -> dict[str, Any]:
    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else {}
    raw_scenes = storyboard.get("scenes") if storyboard else payload.get("scenes")
    scenes = [normalize_scene(scene, i) for i, scene in enumerate(raw_scenes or [], start=1)]
    return {
        "title": storyboard.get("title") or payload.get("project_title") or project.get("project_title") or "Storyboard Render",
        "aspect_ratio": storyboard.get("aspect_ratio") or payload.get("aspect_ratio") or project.get("aspect_ratio") or "9:16",
        "pipeline_target": project.get("pipeline_target") or storyboard.get("pipeline_target") or payload.get("pipeline_target") or "short-shorts",
        "scenes": scenes,
    }


def resolve_dimensions(aspect_ratio: str) -> tuple[int, int]:
    ratio = aspect_ratio.strip()
    if ratio == "16:9":
        return 1920, 1080
    if ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def write_placeholder_svg(path: Path, title: str, index: int, width: int, height: int) -> None:
    colors = [
        ("#15191f", "#f0c35a"),
        ("#16221f", "#6fd6a4"),
        ("#201822", "#e48ad8"),
        ("#171d2b", "#7eb7ff"),
    ]
    bg, accent = colors[(index - 1) % len(colors)]
    safe_title = html.escape(title)
    path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <rect width="100%" height="100%" fill="{bg}"/>
  <circle cx="{width * 0.78:.0f}" cy="{height * 0.16:.0f}" r="{min(width, height) * 0.22:.0f}" fill="{accent}" opacity="0.18"/>
  <circle cx="{width * 0.18:.0f}" cy="{height * 0.78:.0f}" r="{min(width, height) * 0.18:.0f}" fill="{accent}" opacity="0.12"/>
  <text x="{width * 0.08:.0f}" y="{height * 0.45:.0f}" fill="#f8f4e8" font-family="Arial, sans-serif" font-size="{max(46, width // 12)}" font-weight="800">{safe_title}</text>
  <text x="{width * 0.08:.0f}" y="{height * 0.52:.0f}" fill="{accent}" font-family="Arial, sans-serif" font-size="{max(24, width // 24)}" font-weight="700">Scene {index:02d}</text>
</svg>
""",
        encoding="utf-8",
    )


def stage_asset(asset: str, scene: dict[str, Any], index: int, workspace: Path, job_dir: Path, width: int, height: int) -> str:
    assets_dir = workspace / "assets"
    if asset.startswith(("http://", "https://")):
        return asset

    candidates = []
    if asset:
        raw = Path(asset)
        candidates.extend(
            [
                raw,
                job_dir / asset,
                job_dir / "assets" / "images" / "materialized" / asset,
                job_dir / "assets" / "images" / "src" / asset,
                job_dir / "storyboard" / asset,
            ]
        )

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            dest = assets_dir / candidate.name
            if not dest.exists() or dest.stat().st_size != candidate.stat().st_size:
                shutil.copy2(candidate, dest)
            return f"assets/{dest.name}"

    placeholder = assets_dir / f"{index:03d}-{slugify(scene['id'])}.svg"
    write_placeholder_svg(placeholder, scene["title"], index, width, height)
    return f"assets/{placeholder.name}"


def generate_index_html(payload: dict[str, Any], workspace: Path, job_dir: Path) -> None:
    width, height = resolve_dimensions(payload["aspect_ratio"])
    scenes = payload["scenes"]
    if not scenes:
        raise ValueError("No scenes found in project payload")

    assets_dir = workspace / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    clips: list[str] = []
    tweens: list[str] = []
    current = 0.0
    for index, scene in enumerate(scenes, start=1):
        duration = float(scene["duration"])
        src = stage_asset(scene["asset"], scene, index, workspace, job_dir, width, height)
        clip_id = f"scene-{index:03d}"
        title = html.escape(scene["title"])
        narration = html.escape(scene["narration"])
        motion = html.escape(scene["motion"])
        clips.append(
            f"""
      <section id="{clip_id}" class="clip scene" data-start="{current:.3f}" data-duration="{duration:.3f}" data-track-index="1">
        <img class="scene-image" src="{html.escape(src, quote=True)}" crossorigin="anonymous" alt="">
        <div class="vignette"></div>
        <div class="scene-copy">
          <div class="kicker">Scene {index:02d} · {motion}</div>
          <h1>{title}</h1>
          <p>{narration}</p>
        </div>
      </section>"""
        )
        tweens.append(
            f"""
      tl.from("#{clip_id} .scene-image", {{ scale: 1.06, opacity: 0.72, duration: 0.65, ease: "power2.out" }}, {current + 0.1:.3f});
      tl.from("#{clip_id} .kicker", {{ y: 24, opacity: 0, duration: 0.45, ease: "expo.out" }}, {current + 0.25:.3f});
      tl.from("#{clip_id} h1", {{ y: 38, opacity: 0, duration: 0.6, ease: "power3.out" }}, {current + 0.38:.3f});
      tl.from("#{clip_id} p", {{ y: 28, opacity: 0, duration: 0.5, ease: "sine.out" }}, {current + 0.55:.3f});"""
        )
        current += duration

    total = max(1.0, current)
    title = html.escape(str(payload["title"]))
    (workspace / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ margin: 0; background: #11151b; color: #f8f4e8; font-family: Arial, sans-serif; }}
    [data-composition-id="root"] {{ position: relative; width: {width}px; height: {height}px; overflow: hidden; background: #11151b; }}
    .clip {{ position: absolute; inset: 0; overflow: hidden; }}
    .scene-image {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; filter: saturate(1.08) contrast(1.05); }}
    .vignette {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(0,0,0,.08), rgba(0,0,0,.62)); }}
    .scene-copy {{ position: absolute; left: 72px; right: 72px; bottom: 118px; display: flex; flex-direction: column; gap: 18px; }}
    .kicker {{ color: #f0c35a; font-size: 28px; font-weight: 800; text-transform: uppercase; }}
    h1 {{ margin: 0; max-width: 920px; color: #fffaf0; font-size: 86px; line-height: 1.02; font-weight: 900; }}
    p {{ margin: 0; max-width: 880px; color: #f1ead9; font-size: 36px; line-height: 1.24; font-weight: 700; }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
</head>
<body>
  <div data-composition-id="root" data-start="0" data-duration="{total:.3f}" data-width="{width}" data-height="{height}">
    {''.join(clips)}
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {''.join(tweens)}
      window.__timelines["root"] = tl;
    </script>
  </div>
</body>
</html>
""",
        encoding="utf-8",
    )


def run_step(args: list[str], cwd: Path, log_path: Path, timeout: int) -> None:
    resolved = shutil.which(args[0]) or args[0]
    cmd = [resolved, *args[1:]]
    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n$ {' '.join(cmd)}\n")
        completed = subprocess.run(cmd, cwd=cwd, text=True, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit {completed.returncode}: {' '.join(args)}")


def render_job(project_path: Path, target: str | None, quality: str, fps: int, skip_validate: bool) -> Path:
    project_path = project_path.resolve()
    job_dir = project_path.parent
    project = json.loads(project_path.read_text(encoding="utf-8"))
    payload = normalize_payload(project)
    render_target = target or payload["pipeline_target"]
    if render_target not in VALID_TARGETS:
        raise ValueError(f"HyperFrames live render supports {sorted(VALID_TARGETS)}, got {render_target!r}")

    exports_dir = job_dir / "exports"
    logs_dir = job_dir / "logs"
    workspace = job_dir / "hyperframes"
    exports_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    workspace.mkdir(exist_ok=True)
    (workspace / "hyperframes.json").write_text(json.dumps({"paths": {"assets": "assets"}}, indent=2), encoding="utf-8")

    generate_index_html(payload, workspace, job_dir)
    output_path = exports_dir / "final.mp4"
    log_path = logs_dir / "hyperframes-render.log"
    log_path.write_text("", encoding="utf-8")

    run_step(["npx", "--yes", "hyperframes", "lint"], workspace, log_path, timeout=180)
    if not skip_validate:
        run_step(["npx", "--yes", "hyperframes", "validate", "--no-contrast"], workspace, log_path, timeout=240)
    run_step(
        ["npx", "--yes", "hyperframes", "render", "--output", str(output_path), "--fps", str(fps), "--quality", quality],
        workspace,
        log_path,
        timeout=1800,
    )
    if not output_path.exists():
        raise RuntimeError(f"Render finished but output is missing: {output_path}")

    (exports_dir / "render-summary.json").write_text(
        json.dumps(
            {
                "ok": True,
                "target": render_target,
                "quality": quality,
                "fps": fps,
                "output": str(output_path),
                "workspace": str(workspace),
                "log": str(log_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a storyboard bridge job with HyperFrames")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("--target", choices=sorted(VALID_TARGETS))
    parser.add_argument("--quality", choices=["draft", "standard", "high"], default="draft")
    parser.add_argument("--fps", type=int, choices=[24, 30, 60], default=30)
    parser.add_argument("--skip-validate", action="store_true")
    args = parser.parse_args()

    try:
        output = render_job(args.project_json, args.target, args.quality, args.fps, args.skip_validate)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Rendered: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
