#!/usr/bin/env python3
"""Materialize storyboard scene assets before rendering.

The renderer needs local files. This script turns missing, flagged, or remote
scene assets into inspectable files under a bridge job folder, then updates
``project.json`` so downstream renderers use those files.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
OPENMONTAGE_ROOT = Path(os.environ.get("OPENMONTAGE_ROOT", r"C:\Workspace\Repos\OpenMontage"))
REMOTE_TIMEOUT_SECONDS = 45
MAX_DOWNLOAD_BYTES = 18 * 1024 * 1024


def slugify(value: str, fallback: str = "asset") -> str:
    out = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:70] or fallback


def normalize_scene(scene: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        **scene,
        "id": str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}"),
        "title": str(scene.get("title") or scene.get("scene_description") or f"Scene {index}"),
        "asset": str(scene.get("asset") or scene.get("assetUrl") or scene.get("asset_url") or "").strip(),
        "asset_state": str(scene.get("asset_state") or scene.get("assetState") or "candidate").strip(),
        "status": str(scene.get("status") or "").strip(),
        "narration": str(scene.get("narration") or scene.get("script") or "").strip(),
        "notes": str(scene.get("notes") or scene.get("prompt_notes") or "").strip(),
    }


def scene_prompt(scene: dict[str, Any], style: str) -> str:
    parts = [
        scene["title"],
        scene.get("notes", ""),
        scene.get("narration", ""),
        style,
        "vertical 9:16 cinematic frame, documentary explainer still, no legible text, strong subject separation",
    ]
    return ". ".join(part.strip() for part in parts if part and str(part).strip())


def load_project(project_path: Path) -> dict[str, Any]:
    return json.loads(project_path.read_text(encoding="utf-8"))


def payload_ref(project: dict[str, Any]) -> dict[str, Any]:
    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    if isinstance(payload.get("storyboard"), dict):
        return payload["storyboard"]
    return payload


def collect_scenes(project: dict[str, Any]) -> list[dict[str, Any]]:
    payload = payload_ref(project)
    return [normalize_scene(scene, index) for index, scene in enumerate(payload.get("scenes") or [], start=1)]


def update_scene_assets(project: dict[str, Any], manifest_items: list[dict[str, Any]]) -> None:
    asset_by_id = {item["scene_id"]: item["asset"] for item in manifest_items if item.get("asset")}
    payload = payload_ref(project)
    for index, scene in enumerate(payload.get("scenes") or [], start=1):
        scene_id = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
        asset = asset_by_id.get(scene_id)
        if asset:
            scene["asset"] = asset
            scene["assetUrl"] = asset
            scene["asset_url"] = asset
            scene["asset_state"] = "materialized"
            scene["assetState"] = "materialized"
    if isinstance(project.get("payload"), dict) and project["payload"] is not payload and "scenes" in project["payload"]:
        # Non-storyboard normalized payloads store scenes directly.
        for index, scene in enumerate(project["payload"].get("scenes") or [], start=1):
            scene_id = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
            asset = asset_by_id.get(scene_id)
            if asset:
                scene["asset"] = asset
                scene["asset_state"] = "materialized"


def write_scene_art_svg(path: Path, scene: dict[str, Any], index: int, prompt: str) -> None:
    palettes = [
        ("#101820", "#e2b044", "#f8f4e8"),
        ("#15201c", "#59c49a", "#f4fbf6"),
        ("#1f1721", "#d76ebc", "#fff4fb"),
        ("#141b2b", "#6ca8ff", "#f3f7ff"),
    ]
    bg, accent, fg = palettes[(index - 1) % len(palettes)]
    title = html.escape(scene["title"])
    prompt_label = html.escape(prompt[:130])
    width, height = 1080, 1920
    path.write_text(
        f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{bg}"/>
      <stop offset="1" stop-color="#07090d"/>
    </linearGradient>
    <radialGradient id="glow" cx="70%" cy="18%" r="65%">
      <stop offset="0" stop-color="{accent}" stop-opacity=".55"/>
      <stop offset=".42" stop-color="{accent}" stop-opacity=".14"/>
      <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="100%" height="100%" fill="url(#bg)"/>
  <rect width="100%" height="100%" fill="url(#glow)"/>
  <path d="M0 {height * .73:.0f} C {width * .23:.0f} {height * .60:.0f}, {width * .52:.0f} {height * .84:.0f}, {width} {height * .66:.0f} L {width} {height} L 0 {height} Z" fill="{accent}" opacity=".16"/>
  <circle cx="{width * .20:.0f}" cy="{height * .24:.0f}" r="{width * .14:.0f}" fill="none" stroke="{accent}" stroke-width="10" opacity=".22"/>
  <circle cx="{width * .78:.0f}" cy="{height * .70:.0f}" r="{width * .22:.0f}" fill="{accent}" opacity=".11"/>
  <rect x="72" y="1160" width="936" height="470" rx="30" fill="#000" opacity=".28"/>
  <text x="88" y="1238" fill="{accent}" font-family="Arial, sans-serif" font-size="34" font-weight="800">GENERATED SCENE ART · {index:02d}</text>
  <text x="88" y="1335" fill="{fg}" font-family="Arial, sans-serif" font-size="78" font-weight="900">{title}</text>
  <text x="88" y="1430" fill="{fg}" font-family="Arial, sans-serif" font-size="28" opacity=".82">{prompt_label}</text>
</svg>
""",
        encoding="utf-8",
    )


def download_remote(asset_url: str, destination: Path) -> tuple[bool, str | None]:
    try:
        request = urllib.request.Request(asset_url, headers={"User-Agent": "storyboard-video-studio/0.1"})
        with urllib.request.urlopen(request, timeout=REMOTE_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("Content-Type", "")
            if not content_type.startswith("image/"):
                return False, f"remote content type is not image/*: {content_type}"
            data = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(data) > MAX_DOWNLOAD_BYTES:
                return False, "remote image exceeded size limit"
        destination.write_bytes(data)
        return True, None
    except Exception as exc:
        return False, str(exc)


def copy_local(asset: str, project_path: Path, destination: Path) -> tuple[bool, str | None]:
    raw = Path(asset)
    candidates = [raw, project_path.parent / asset, project_path.parent / "assets" / "images" / asset]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            shutil.copy2(candidate, destination.with_suffix(candidate.suffix or destination.suffix))
            return True, None
    return False, "local file not found"


def run_openmontage_provider(provider: str, prompt: str, output_path: Path, aspect_ratio: str) -> tuple[bool, str | None]:
    provider_map = {
        "openai": ("tools.graphics.openai_image", "OpenAIImage", {"size": "1024x1536", "quality": "low"}),
        "google_imagen": ("tools.graphics.google_imagen", "GoogleImagen", {"aspect_ratio": aspect_ratio}),
        "grok": ("tools.graphics.grok_image", "GrokImage", {"aspect_ratio": aspect_ratio, "resolution": "1k"}),
    }
    if provider not in provider_map:
        return False, f"unsupported OpenMontage provider: {provider}"
    if not OPENMONTAGE_ROOT.exists():
        return False, f"OpenMontage root not found: {OPENMONTAGE_ROOT}"

    module_name, class_name, extra = provider_map[provider]
    script = f"""
import json, sys
from pathlib import Path
sys.path.insert(0, r'{OPENMONTAGE_ROOT}')
from {module_name} import {class_name}
tool = {class_name}()
inputs = {json.dumps({"prompt": prompt, "output_path": str(output_path)})}
inputs.update({json.dumps(extra)})
result = tool.execute(inputs)
print(json.dumps({{"success": result.success, "error": result.error, "data": result.data}}, default=str))
sys.exit(0 if result.success else 2)
"""
    import subprocess

    completed = subprocess.run([sys.executable, "-c", script], text=True, capture_output=True, timeout=240)
    if completed.returncode == 0 and output_path.exists():
        return True, None
    detail = completed.stdout.strip() or completed.stderr.strip() or f"provider exited {completed.returncode}"
    return False, detail


def choose_provider(preferred: str) -> str:
    if preferred != "auto":
        return preferred
    if os.environ.get("XAI_API_KEY"):
        return "grok"
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return "google_imagen"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "local"


def materialize(project_path: Path, provider: str, style: str, fallback: bool) -> dict[str, Any]:
    project_path = project_path.resolve()
    project = load_project(project_path)
    scenes = collect_scenes(project)
    if not scenes:
        raise ValueError("No scenes found in project payload")

    selected_provider = choose_provider(provider)
    job_dir = project_path.parent
    asset_dir = job_dir / "assets" / "images" / "materialized"
    asset_dir.mkdir(parents=True, exist_ok=True)
    manifest_items: list[dict[str, Any]] = []

    for index, scene in enumerate(scenes, start=1):
        prompt = scene_prompt(scene, style)
        stem = f"{index:03d}-{slugify(scene['id'])}"
        asset = scene.get("asset", "")
        state = scene.get("asset_state", "")
        status = scene.get("status", "")
        needs_replacement = not asset or state in {"needs-image", "missing", "replace-later"} or status == "flagged"
        item = {
            "scene_id": scene["id"],
            "title": scene["title"],
            "prompt": prompt,
            "provider": selected_provider,
            "source_asset": asset,
            "status": "pending",
            "asset": "",
            "notes": "",
        }

        if asset.startswith(("http://", "https://")) and not needs_replacement:
            suffix = Path(asset.split("?", 1)[0]).suffix.lower()
            if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                suffix = ".jpg"
            destination = asset_dir / f"{stem}{suffix}"
            ok, err = download_remote(asset, destination)
            if ok:
                item.update({"status": "downloaded", "asset": str(destination.relative_to(job_dir))})
                manifest_items.append(item)
                continue
            item["notes"] = f"download failed: {err}"

        if asset and not asset.startswith(("http://", "https://")) and not needs_replacement:
            destination = asset_dir / f"{stem}.png"
            ok, err = copy_local(asset, project_path, destination)
            if ok:
                actual = next(asset_dir.glob(f"{stem}.*"))
                item.update({"status": "copied", "asset": str(actual.relative_to(job_dir))})
                manifest_items.append(item)
                continue
            item["notes"] = f"copy failed: {err}"

        if selected_provider in {"openai", "google_imagen", "grok"}:
            destination = asset_dir / f"{stem}.png"
            ok, err = run_openmontage_provider(selected_provider, prompt, destination, "9:16")
            if ok:
                item.update({"status": "generated", "asset": str(destination.relative_to(job_dir))})
                manifest_items.append(item)
                continue
            item["notes"] = f"{selected_provider} failed: {err}"
            if not fallback:
                raise RuntimeError(item["notes"])

        destination = asset_dir / f"{stem}.svg"
        write_scene_art_svg(destination, scene, index, prompt)
        item.update({"status": "local-generated", "provider": "local-svg", "asset": str(destination.relative_to(job_dir))})
        manifest_items.append(item)

    update_scene_assets(project, manifest_items)
    project.setdefault("asset_materialization", {})
    project["asset_materialization"] = {
        "provider_requested": provider,
        "provider_used": selected_provider,
        "fallback_enabled": fallback,
        "manifest": "exports/asset-manifest.json",
    }
    project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")

    exports_dir = job_dir / "exports"
    exports_dir.mkdir(exist_ok=True)
    manifest = {
        "ok": True,
        "project": str(project_path),
        "provider_requested": provider,
        "provider_used": selected_provider,
        "fallback_enabled": fallback,
        "assets": manifest_items,
    }
    (exports_dir / "asset-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize storyboard assets before render")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("--provider", choices=["auto", "local", "openai", "google_imagen", "grok"], default="auto")
    parser.add_argument("--style", default="cinematic weird forgotten history, rich archival mood")
    parser.add_argument("--no-fallback", action="store_true", help="Fail instead of writing local generated scene art when provider/download fails")
    args = parser.parse_args()

    try:
        manifest = materialize(args.project_json, args.provider, args.style, fallback=not args.no_fallback)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
