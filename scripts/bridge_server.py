#!/usr/bin/env python3
"""Local storyboard bridge server.

POST /api/launch accepts storyboard payloads from the static UI and writes an
inspectable job folder. Live execution is intentionally gated behind
STORYBOARD_BRIDGE_LIVE=1 so UI tests and agent dry-runs cannot accidentally run
render commands.
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import re
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS_ROOT = REPO_ROOT / "bridge-jobs"
VIDEOS_ROOT = REPO_ROOT / "videos"
MAX_UPLOAD_BYTES = 30 * 1024 * 1024
UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"}
VALID_TARGETS = {"short-shorts", "longer-shorts", "long-shorts", "montage"}
VALID_ENGINES = {"hyperframes", "remotion", "openmontage"}
REQUIRED_FIELDS = ("machine", "engine", "run_label", "execute", "payload")

MATERIALIZE_CMD = "python scripts/materialize_assets.py {job_dir}/project.json --provider auto"
RENDER_HYPERFRAMES_CMD = "python scripts/render_hyperframes_job.py {job_dir}/project.json --target {target} --quality draft"
RENDER_REMOTION_CMD = "python scripts/render_remotion_job.py {job_dir}/project.json --target {target} --quality draft"
MONTAGE_CMD = "python scripts/prepare_montage_handoff.py {job_dir}/project.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, fallback: str = "storyboard-job") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or fallback


def validate_launch_request(request: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in request]
    if missing:
        raise ValueError(f"Missing required launch field(s): {', '.join(missing)}")
    if not isinstance(request["payload"], dict):
        raise ValueError("payload must be an object")
    scenes = normalized_storyboard_payload(request["payload"]).get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("payload.scenes or payload.storyboard.scenes must be a non-empty list")
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            raise ValueError(f"payload.scenes[{index}] must be an object")


def pipeline_target(payload: dict[str, Any]) -> str:
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else {}
    target = str(payload.get("pipeline_target") or storyboard.get("pipeline_target") or payload.get("pipeline") or "short-shorts").strip().lower()
    aliases = {
        "short": "short-shorts",
        "shorts": "short-shorts",
        "short_short": "short-shorts",
        "short-shorts": "short-shorts",
        "longer": "longer-shorts",
        "longer-short": "longer-shorts",
        "longer-shorts": "longer-shorts",
        "long": "long-shorts",
        "long-short": "long-shorts",
        "long-shorts": "long-shorts",
        "long-form": "long-shorts",
        "montage": "montage",
    }
    normalized = aliases.get(target, target)
    if normalized not in VALID_TARGETS:
        raise ValueError(f"Unsupported pipeline target '{target}'. Expected one of: {', '.join(sorted(VALID_TARGETS))}")
    return normalized


def normalize_scene(scene: dict[str, Any]) -> dict[str, Any]:
    """Normalize scene aliases from simple and Ultimate Workflow UI payloads."""
    return {
        **scene,
        "id": scene.get("id") or scene.get("scene_id"),
        "title": scene.get("title") or scene.get("shot_name") or scene.get("scene_description") or "Untitled scene",
        "asset": scene.get("asset") or scene.get("assetUrl") or scene.get("asset_url") or scene.get("image_filename") or "",
        "narration": scene.get("narration") or scene.get("script") or scene.get("narration_text") or "",
        "motion": scene.get("motion") or scene.get("motionPreset") or scene.get("motion_preset") or "slow Ken Burns",
        "vo_seconds": scene.get("vo_seconds") or scene.get("duration"),
    }


def normalized_storyboard_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept both simple UI payloads and nested Ultimate Workflow payloads."""
    if isinstance(payload.get("storyboard"), dict):
        storyboard = payload["storyboard"]
        launcher = payload.get("launcher") if isinstance(payload.get("launcher"), dict) else {}
        normalized = dict(payload)
        normalized.update(
            {
                "project_title": storyboard.get("title") or payload.get("project_title") or "Storyboard Ultimate Workflow",
                "aspect_ratio": storyboard.get("aspect_ratio") or payload.get("aspect_ratio") or "9:16",
                "pipeline_target": storyboard.get("pipeline_target") or payload.get("pipeline_target") or "short-shorts",
                "target_duration_seconds": storyboard.get("total_duration_sec") or payload.get("target_duration_seconds"),
                "scenes": [normalize_scene(scene) for scene in storyboard.get("scenes", [])],
                "launcher": launcher,
            }
        )
        return normalized
    normalized = dict(payload)
    normalized["scenes"] = [normalize_scene(scene) for scene in payload.get("scenes", [])]
    return normalized


def normalize_engine(engine: str) -> str:
    value = str(engine or "").strip().lower()
    aliases = {"hyperframe": "hyperframes", "hyper-frames": "hyperframes", "remotion-studio": "remotion", "open-montage": "openmontage", "montage": "openmontage"}
    return aliases.get(value, value) or "hyperframes"


def build_materialize_command(job_dir: str) -> str:
    return MATERIALIZE_CMD.format(job_dir=job_dir)


def build_render_command(job_dir: str, target: str, engine: str = "hyperframes") -> str:
    target = pipeline_target({"pipeline_target": target})
    engine = normalize_engine(engine)
    if target == "montage" or engine == "openmontage":
        return MONTAGE_CMD.format(job_dir=job_dir)
    if engine == "remotion":
        render_target = target if target != "montage" else "long-shorts"
        return RENDER_REMOTION_CMD.format(job_dir=job_dir, target=render_target)
    render_target = target if target != "montage" else "longer-shorts"
    return RENDER_HYPERFRAMES_CMD.format(job_dir=job_dir, target=render_target)


def build_launch_command(target: str, job_id: str, execute: bool, job_dir: str | None = None, engine: str = "hyperframes") -> str:
    target = pipeline_target({"pipeline_target": target})
    engine = normalize_engine(engine)
    job_dir_value = job_dir or f"bridge-jobs/{job_id}"

    if target == "montage" or engine == "openmontage":
        command = build_render_command(job_dir_value, target, engine)
    else:
        command = build_materialize_command(job_dir_value) + " && " + build_render_command(job_dir_value, target, engine)

    if execute:
        return command
    return f"DRY RUN only for {engine}/{target}: {command}"


def scene_filename(index: int, scene: dict[str, Any]) -> str:
    scene_id = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
    return f"{index:03d}-{slugify(scene_id, f'scene-{index:03d}')}.json"


def create_launch_job(request: dict[str, Any], jobs_root: Path = DEFAULT_JOBS_ROOT) -> dict[str, Any]:
    validate_launch_request(request)
    original_payload = request["payload"]
    payload = normalized_storyboard_payload(original_payload)
    target = pipeline_target(payload)
    label = str(request.get("run_label") or payload.get("project_title") or "storyboard job")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_id = f"{timestamp}-{slugify(label)}"
    job_dir = jobs_root / job_id
    scenes_dir = job_dir / "scenes"
    exports_dir = job_dir / "exports"
    handoff_dir = job_dir / "editor-handoff"
    logs_dir = job_dir / "logs"
    storyboard_dir = job_dir / "storyboard"
    for folder in (scenes_dir, exports_dir, handoff_dir, logs_dir, storyboard_dir):
        folder.mkdir(parents=True, exist_ok=True)

    execute_requested = bool(request.get("execute"))
    live_execution_enabled = os.environ.get("STORYBOARD_BRIDGE_LIVE") == "1"
    should_execute = execute_requested and live_execution_enabled
    engine = normalize_engine(request.get("engine"))
    command = build_launch_command(target, job_id, execute=should_execute, job_dir=str(job_dir), engine=engine)

    project = {
        "job_id": job_id,
        "created_at": utc_now(),
        "machine": request["machine"],
        "engine": engine,
        "run_label": label,
        "execute_requested": execute_requested,
        "live_execution_enabled": live_execution_enabled,
        "pipeline_target": target,
        "aspect_ratio": payload.get("aspect_ratio", "9:16"),
        "project_title": payload.get("project_title") or label,
        "payload": payload,
        "source_payload": original_payload,
        "folders": {
            "storyboard": "storyboard/",
            "scenes": "scenes/",
            "exports": "exports/",
            "editor_handoff": "editor-handoff/",
            "logs": "logs/",
        },
    }
    (job_dir / "project.json").write_text(json.dumps(project, indent=2), encoding="utf-8")
    for index, scene in enumerate(payload["scenes"], start=1):
        scene_payload = {"index": index, **scene}
        (scenes_dir / scene_filename(index, scene)).write_text(json.dumps(scene_payload, indent=2), encoding="utf-8")

    (job_dir / "STATUS.md").write_text(
        f"# {project['project_title']}\n\n"
        f"Status: {'executed' if should_execute else 'dry-run'}\n"
        f"Pipeline: {target}\n"
        f"Created: {project['created_at']}\n\n"
        "## Live execution\n"
        "Set STORYBOARD_BRIDGE_LIVE=1 before starting the bridge to allow execute=true to run the command in launch-command.txt.\n",
        encoding="utf-8",
    )
    (job_dir / "activity.md").write_text(
        f"# Activity\n\n- {project['created_at']} — Bridge wrote storyboard job for {target}; execute_requested={execute_requested}; live={live_execution_enabled}.\n",
        encoding="utf-8",
    )
    (job_dir / "launch-command.txt").write_text(command + "\n", encoding="utf-8")
    (storyboard_dir / "payload.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (storyboard_dir / "source-payload.json").write_text(json.dumps(original_payload, indent=2), encoding="utf-8")

    execution = {"ran": False, "returncode": None, "stdout": "", "stderr": ""}
    if should_execute:
        completed = subprocess.run(command, cwd=REPO_ROOT, shell=True, text=True, capture_output=True, timeout=900)
        execution = {
            "ran": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (logs_dir / "execution.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")

    return {
        "ok": True,
        "status": "executed" if should_execute else "dry_run",
        "job_id": job_id,
        "job_dir": str(job_dir),
        "pipeline_target": target,
        "command": command,
        "execution": execution,
    }


def decode_upload_data(data: str) -> bytes:
    payload = data.strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")
    return base64.b64decode(payload, validate=False)


def safe_extension(filename: str, fallback: str = ".png") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext == ".jpg":
        ext = ".jpg"
    return ext if ext in UPLOAD_EXTENSIONS else fallback


def create_asset_upload(request: dict[str, Any]) -> dict[str, Any]:
    project_id = slugify(str(request.get("project_id") or ""), "untitled-project")
    scene_id = slugify(str(request.get("scene_id") or "scene"), "scene")
    filename = str(request.get("filename") or "image.png")
    data = request.get("data")
    if not isinstance(data, str) or not data:
        raise ValueError("upload requires base64 'data'")

    raw = decode_upload_data(data)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("upload exceeds size limit")

    project_dir = (VIDEOS_ROOT / project_id).resolve()
    if not str(project_dir).startswith(str(VIDEOS_ROOT.resolve())):
        raise ValueError("invalid project path")
    uploads_dir = project_dir / "assets" / "images" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    ext = safe_extension(filename)
    stem = slugify(Path(filename).stem, "image")
    name = f"{scene_id}-{stem}{ext}"
    dest = uploads_dir / name
    dest.write_bytes(raw)

    rel_path = f"assets/images/uploads/{name}"
    return {
        "ok": True,
        "project_id": project_id,
        "scene_id": scene_id,
        "path": rel_path,
        "abs": str(dest),
        "url": f"/assets/{project_id}/{rel_path}",
        "bytes": len(raw),
    }


def resolve_served_asset(path: str) -> Path | None:
    rel = unquote(path[len("/assets/"):]).lstrip("/")
    if not rel:
        return None
    target = (VIDEOS_ROOT / rel).resolve()
    root = str(VIDEOS_ROOT.resolve())
    if not str(target).startswith(root) or not target.is_file():
        return None
    return target


class BridgeHandler(BaseHTTPRequestHandler):
    jobs_root = DEFAULT_JOBS_ROOT

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json(200, {"ok": True})

    def _send_file(self, path: Path) -> None:
        data = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/assets/"):
            target = resolve_served_asset(self.path.split("?", 1)[0])
            if target is None:
                self._send_json(404, {"ok": False, "error": "asset not found"})
                return
            self._send_file(target)
            return
        if self.path in {"/api/health", "/api/status"}:
            jobs = []
            if self.jobs_root.exists():
                job_dirs = sorted((p for p in self.jobs_root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
                for job_dir in job_dirs[-20:]:
                    jobs.append({"job": job_dir.name, "path": str(job_dir), "status": "written"})
            self._send_json(200, {"ok": True, "service": "storyboard-bridge", "jobs_root": str(self.jobs_root), "jobs": jobs})
            return
        self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path not in {"/api/launch", "/api/asset-upload"}:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/asset-upload":
                result = create_asset_upload(request)
            else:
                result = create_launch_job(request, self.jobs_root)
            self._send_json(200, result)
        except Exception as exc:  # keep local bridge failures visible to UI
            self._send_json(400, {"ok": False, "error": str(exc)})

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{utc_now()}] {self.address_string()} {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Storyboard Video Studio bridge server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--jobs-root", type=Path, default=DEFAULT_JOBS_ROOT)
    args = parser.parse_args()

    BridgeHandler.jobs_root = args.jobs_root
    args.jobs_root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), BridgeHandler)
    print(f"Storyboard bridge listening on http://{args.host}:{args.port}")
    print(f"Jobs root: {args.jobs_root}")
    print(f"Live execution enabled: {os.environ.get('STORYBOARD_BRIDGE_LIVE') == '1'}")
    server.serve_forever()


if __name__ == "__main__":
    main()
