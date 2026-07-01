# Review-Before-Render Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Insert a human review checkpoint between image generation and render so the operator sees every scene image, approves or swaps each, and can only render once all scenes are approved.

**Architecture:** Split the bridge's chained `materialize && render` command into two separately triggerable actions on `POST /api/launch` (`action: "materialize"` and `action: "render"`). Add a job-scoped static route so generated images (under `bridge-jobs/`) render in the browser, plus a `GET /api/job` read endpoint. In the UI, add a "Generate images" button that fills a Review Board, wire the existing Approve/Flag/swap controls to a per-scene review state, and lock the Render button until all scenes are approved. Pure review-state logic lives in a small testable CommonJS module; the render and generation engines are untouched.

**Tech Stack:** Python 3.14 stdlib (`http.server`, `unittest`, `importlib`), plain browser JS (no bundler), CommonJS modules for Node-tested logic, existing `scripts/materialize_assets.py` + `scripts/render_hyperframes_job.py`.

## Global Constraints

- Platform: Windows. Bridge runs `python scripts/bridge_server.py --host 127.0.0.1 --port 8788`.
- No new third-party dependencies. Python is stdlib-only; JS is plain browser + CommonJS.
- JS files use lowercase-hyphen names (e.g. `review-gate.js`) and CommonJS (`module.exports`), per project Node rules.
- Preserve the live-execution gate: shell commands run only when `execute: true` **and** env `STORYBOARD_BRIDGE_LIVE == "1"`. Otherwise return `status: "dry_run"` and write the command without running it.
- Do not change `scripts/render_hyperframes_job.py` or `scripts/materialize_assets.py` behavior. This feature only re-sequences and surfaces them.
- Bridge job assets are served from the handler's `jobs_root` (default `bridge-jobs/`) with the same path-traversal guard used by `resolve_served_asset`.
- Backward compatibility: `POST /api/launch` with no `action` field keeps its current combined behavior. Existing tests in `tests/test_bridge_workflow.py` must still pass.

---

## File Structure

- `scripts/bridge_server.py` (modify) — split command builders; add job static route, `read_job` + `GET /api/job`, `action` routing, and `run_render_job`.
- `tests/test_bridge_workflow.py` (modify) — add tests for the new bridge functions alongside the existing suite.
- `storyboard/review-gate.js` (create) — pure review-state logic (UMD: `module.exports` in Node, `window.ReviewGate` in browser).
- `tests/review_gate.test.js` (create) — Node unit tests for `review-gate.js`.
- `storyboard/index.html` (modify) — include `review-gate.js`; add "Generate images" + "Render" buttons and a review badge.
- `storyboard/ultimate-workflow.js` (modify) — add `generateImages()`, `renderVideo()`, review-state wiring, and Render-button lock.

---

## Task 1: Split materialize and render command builders

**Files:**
- Modify: `scripts/bridge_server.py` (near `build_launch_command`, lines ~127-143)
- Test: `tests/test_bridge_workflow.py`

**Interfaces:**
- Produces:
  - `build_materialize_command(job_dir: str) -> str`
  - `build_render_command(job_dir: str, target: str, engine: str = "hyperframes") -> str`
  - `build_launch_command(target, job_id, execute, job_dir=None, engine="hyperframes") -> str` (unchanged signature, now delegates to the two above)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py` inside `BridgeWorkflowTests`:

```python
    def test_materialize_and_render_commands_split(self):
        bridge = load_bridge()
        mat = bridge.build_materialize_command("bridge-jobs/example")
        self.assertIn("materialize_assets.py", mat)
        self.assertIn("bridge-jobs/example", mat)
        self.assertNotIn("render_hyperframes_job.py", mat)

        render = bridge.build_render_command("bridge-jobs/example", "short-shorts", "hyperframes")
        self.assertIn("render_hyperframes_job.py", render)
        self.assertNotIn("materialize_assets.py", render)

        montage = bridge.build_render_command("bridge-jobs/example", "montage", "openmontage")
        self.assertIn("prepare_montage_handoff.py", montage)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_materialize_and_render_commands_split -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'build_materialize_command'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/bridge_server.py`, replace the existing `build_launch_command` (lines ~127-143) with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bridge_workflow -v`
Expected: PASS for the new test **and** the existing `test_pipeline_command_contracts_are_documented`.

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "refactor: split bridge materialize and render command builders"
```

---

## Task 2: Serve job images to the browser

**Files:**
- Modify: `scripts/bridge_server.py` (add resolver near `resolve_served_asset` ~289-297; wire into `do_GET` ~328-335)
- Test: `tests/test_bridge_workflow.py`

**Interfaces:**
- Consumes: handler attribute `BridgeHandler.jobs_root` (a `Path`).
- Produces:
  - `resolve_served_job_asset(path: str, jobs_root: Path) -> Path | None`
  - `GET /jobs/<job_id>/<relpath>` serves a file from within `jobs_root` (traversal-guarded).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py`:

```python
    def test_resolve_served_job_asset_guards_traversal(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "job-1" / "assets" / "images" / "materialized" / "001.png"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(b"\x89PNG\r\n")

            ok = bridge.resolve_served_job_asset(
                "/jobs/job-1/assets/images/materialized/001.png", root
            )
            self.assertIsNotNone(ok)
            self.assertEqual(ok.read_bytes(), b"\x89PNG\r\n")

            self.assertIsNone(bridge.resolve_served_job_asset("/jobs/../secret.txt", root))
            self.assertIsNone(bridge.resolve_served_job_asset("/jobs/job-1/missing.png", root))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_resolve_served_job_asset_guards_traversal -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'resolve_served_job_asset'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/bridge_server.py`, add after `resolve_served_asset` (~line 297):

```python
def resolve_served_job_asset(path: str, jobs_root: Path) -> Path | None:
    rel = unquote(path[len("/jobs/"):]).lstrip("/")
    if not rel:
        return None
    target = (jobs_root / rel).resolve()
    root = str(jobs_root.resolve())
    if not str(target).startswith(root) or not target.is_file():
        return None
    return target
```

Then in `BridgeHandler.do_GET` (after the `/assets/` block, ~line 335), add:

```python
        if self.path.startswith("/jobs/"):
            target = resolve_served_job_asset(self.path.split("?", 1)[0], self.jobs_root)
            if target is None:
                self._send_json(404, {"ok": False, "error": "job asset not found"})
                return
            self._send_file(target)
            return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_resolve_served_job_asset_guards_traversal -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "feat: serve bridge job assets over /jobs route with traversal guard"
```

---

## Task 3: Read a job back with per-scene image URLs

**Files:**
- Modify: `scripts/bridge_server.py` (add `read_job` + `job_image_url`; wire `GET /api/job`)
- Test: `tests/test_bridge_workflow.py`

**Interfaces:**
- Consumes: `create_launch_job` (Task 0/existing) to build a job folder; `resolve_served_job_asset` route from Task 2 for the returned URLs.
- Produces:
  - `job_image_url(job_id: str, rel_asset: str) -> str` → `/jobs/<job_id>/<rel>`
  - `read_job(job_id: str, jobs_root: Path) -> dict` → `{"ok": True, "job_id", "pipeline_target", "scenes": [{"scene_id","title","image_url","status","notes"}]}`
  - `GET /api/job?id=<job_id>` returns that dict.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py`:

```python
    def test_read_job_returns_scene_image_urls(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "hyperframes",
                "run_label": "read job test",
                "execute": False,
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp))
            job_id = result["job_id"]
            job_dir = Path(result["job_dir"])
            (job_dir / "exports").mkdir(exist_ok=True)
            (job_dir / "exports" / "asset-manifest.json").write_text(
                json.dumps({"assets": [
                    {"scene_id": "scene-001", "status": "generated",
                     "asset": "assets/images/materialized/001-scene-001.png", "notes": ""},
                    {"scene_id": "scene-002", "status": "downloaded",
                     "asset": "assets/images/materialized/002-scene-002.jpg", "notes": ""},
                ]}), encoding="utf-8")

            out = bridge.read_job(job_id, Path(tmp))
            self.assertEqual(len(out["scenes"]), 2)
            self.assertEqual(
                out["scenes"][0]["image_url"],
                f"/jobs/{job_id}/assets/images/materialized/001-scene-001.png",
            )
            self.assertEqual(out["scenes"][0]["status"], "generated")

    def test_read_job_unknown_id_raises(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                bridge.read_job("does-not-exist", Path(tmp))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_read_job_returns_scene_image_urls -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'read_job'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/bridge_server.py`, add above the `BridgeHandler` class (~line 299):

```python
def job_image_url(job_id: str, rel_asset: str) -> str:
    rel = str(rel_asset or "").replace("\\", "/").lstrip("/")
    return f"/jobs/{job_id}/{rel}" if rel else ""


def read_job(job_id: str, jobs_root: Path) -> dict[str, Any]:
    job_dir = (jobs_root / job_id).resolve()
    root = str(jobs_root.resolve())
    if not job_id or not str(job_dir).startswith(root) or not job_dir.is_dir():
        raise ValueError(f"unknown job: {job_id!r}")
    project = json.loads((job_dir / "project.json").read_text(encoding="utf-8"))
    manifest_path = job_dir / "exports" / "asset-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"assets": []}
    asset_by_id = {str(a.get("scene_id")): a for a in manifest.get("assets", [])}

    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else payload
    scenes_out: list[dict[str, Any]] = []
    for index, scene in enumerate(storyboard.get("scenes") or [], start=1):
        sid = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
        entry = asset_by_id.get(sid, {})
        scenes_out.append({
            "scene_id": sid,
            "title": scene.get("title") or scene.get("shot_name") or f"Scene {index}",
            "image_url": job_image_url(job_id, entry.get("asset") or ""),
            "status": entry.get("status") or "pending",
            "notes": entry.get("notes") or "",
        })
    return {
        "ok": True,
        "job_id": job_id,
        "pipeline_target": project.get("pipeline_target"),
        "scenes": scenes_out,
    }
```

Then in `BridgeHandler.do_GET`, before the final 404 (~line 344), add:

```python
        if self.path.startswith("/api/job"):
            from urllib.parse import urlparse, parse_qs
            job_id = (parse_qs(urlparse(self.path).query).get("id") or [""])[0]
            try:
                self._send_json(200, read_job(job_id, self.jobs_root))
            except Exception as exc:
                self._send_json(404, {"ok": False, "error": str(exc)})
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bridge_workflow -v`
Expected: PASS (all tests, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "feat: add read_job and GET /api/job returning scene image urls"
```

---

## Task 4: Materialize-only action (generate, then stop)

**Files:**
- Modify: `scripts/bridge_server.py` (`create_launch_job` gains `action` kwarg; `do_POST` routes on `action`)
- Test: `tests/test_bridge_workflow.py`

**Interfaces:**
- Consumes: `build_materialize_command` (Task 1), `read_job` (Task 3).
- Produces: `create_launch_job(request, jobs_root=DEFAULT_JOBS_ROOT, action="full") -> dict`. When `action == "materialize"`, the returned dict includes `"scenes"` (from `read_job`) and the written `launch-command.txt` contains only the materialize command (no render).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py`:

```python
    def test_materialize_action_writes_materialize_only_command(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "hyperframes",
                "run_label": "materialize action",
                "execute": False,
                "action": "materialize",
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp), action="materialize")
            self.assertEqual(result["status"], "dry_run")
            self.assertIn("scenes", result)
            self.assertEqual(len(result["scenes"]), 2)
            command = (Path(result["job_dir"]) / "launch-command.txt").read_text(encoding="utf-8")
            self.assertIn("materialize_assets.py", command)
            self.assertNotIn("render_hyperframes_job.py", command)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_materialize_action_writes_materialize_only_command -v`
Expected: FAIL with `TypeError: create_launch_job() got an unexpected keyword argument 'action'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/bridge_server.py`, change the `create_launch_job` signature (line ~151) to:

```python
def create_launch_job(request: dict[str, Any], jobs_root: Path = DEFAULT_JOBS_ROOT, action: str = "full") -> dict[str, Any]:
```

Replace the command-building line (~line 172) with:

```python
    if action == "materialize":
        base_command = build_materialize_command(str(job_dir))
        command = base_command if should_execute else f"DRY RUN only for {engine}/{target} (materialize): {base_command}"
    else:
        command = build_launch_command(target, job_id, execute=should_execute, job_dir=str(job_dir), engine=engine)
```

At the end of `create_launch_job`, before `return {`, add:

```python
    if action == "materialize":
        try:
            materialized = read_job(job_id, jobs_root)["scenes"]
        except Exception:
            materialized = []
```

Then add `"scenes"` to the returned dict (in the `return {...}` near line 228):

```python
    return {
        "ok": True,
        "status": "executed" if should_execute else "dry_run",
        "job_id": job_id,
        "job_dir": str(job_dir),
        "pipeline_target": target,
        "command": command,
        "execution": execution,
        "scenes": materialized if action == "materialize" else [],
    }
```

Finally, route in `BridgeHandler.do_POST` (~line 353-356). Replace the `else` branch that calls `create_launch_job`:

```python
            if self.path == "/api/asset-upload":
                result = create_asset_upload(request)
            elif request.get("action") == "materialize":
                result = create_launch_job(request, self.jobs_root, action="materialize")
            elif request.get("action") == "render":
                result = run_render_job(request, self.jobs_root)
            else:
                result = create_launch_job(request, self.jobs_root)
```

(`run_render_job` is added in Task 5; if implementing strictly in order, temporarily leave the `render` branch out and add it in Task 5. The materialize branch works now.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bridge_workflow -v`
Expected: PASS (all, including the existing dry-run job test which uses `action="full"` default).

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "feat: add materialize-only action to bridge launch endpoint"
```

---

## Task 5: Render action (apply reviewed images, then render)

**Files:**
- Modify: `scripts/bridge_server.py` (add `run_render_job`; ensure `do_POST` `render` branch is present)
- Test: `tests/test_bridge_workflow.py`

**Interfaces:**
- Consumes: `normalized_storyboard_payload` (existing), `build_materialize_command` + `build_render_command` (Task 1).
- Produces: `run_render_job(request, jobs_root=DEFAULT_JOBS_ROOT) -> dict`. Reads `request["job_id"]`, overwrites the job's `project.json` scene assets from `request["payload"]` (reviewed swaps), writes a `launch-command.txt` of `materialize && render`, runs it only under the live gate, and returns `{"ok","status","job_id","job_dir","command","final_video","execution"}`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py`:

```python
    def test_render_action_applies_reviewed_asset_and_builds_render_command(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            created = bridge.create_launch_job(
                {
                    "machine": "BEAST",
                    "engine": "hyperframes",
                    "run_label": "render action",
                    "execute": False,
                    "payload": self.realistic_payload(),
                },
                Path(tmp),
            )
            job_id = created["job_id"]

            reviewed = {
                "job_id": job_id,
                "engine": "hyperframes",
                "execute": False,
                "payload": {
                    "storyboard": {
                        "id": "x",
                        "title": "x",
                        "aspect_ratio": "9:16",
                        "scenes": [
                            {"id": "scene-001", "title": "Cold open", "assetUrl": "https://real.example/site.jpg", "duration": 3.4},
                            {"id": "scene-002", "title": "Reveal", "assetUrl": "lab-notes.jpg", "duration": 4.1},
                        ],
                    }
                },
            }
            result = bridge.run_render_job(reviewed, Path(tmp))
            self.assertEqual(result["status"], "dry_run")
            self.assertIn("render_hyperframes_job.py", result["command"])

            project = json.loads((Path(created["job_dir"]) / "project.json").read_text(encoding="utf-8"))
            payload = project["payload"]
            storyboard = payload.get("storyboard", payload)
            self.assertEqual(storyboard["scenes"][0]["asset"], "https://real.example/site.jpg")

    def test_render_action_unknown_job_raises(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                bridge.run_render_job({"job_id": "nope", "payload": {}}, Path(tmp))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_render_action_applies_reviewed_asset_and_builds_render_command -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'run_render_job'`

- [ ] **Step 3: Write minimal implementation**

In `scripts/bridge_server.py`, add above the `BridgeHandler` class (near `read_job`):

```python
def run_render_job(request: dict[str, Any], jobs_root: Path = DEFAULT_JOBS_ROOT) -> dict[str, Any]:
    job_id = str(request.get("job_id") or "")
    job_dir = (jobs_root / job_id).resolve()
    root = str(jobs_root.resolve())
    if not job_id or not str(job_dir).startswith(root) or not job_dir.is_dir():
        raise ValueError(f"unknown job for render: {job_id!r}")

    project_path = job_dir / "project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))

    reviewed = request.get("payload") or {}
    reviewed_scenes: dict[str, dict[str, Any]] = {}
    if isinstance(reviewed, dict) and (reviewed.get("scenes") or reviewed.get("storyboard")):
        norm = normalized_storyboard_payload(reviewed)
        for scene in norm.get("scenes", []):
            sid = str(scene.get("id") or scene.get("scene_id") or "")
            if sid:
                reviewed_scenes[sid] = scene

    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    storyboard = payload.get("storyboard") if isinstance(payload.get("storyboard"), dict) else payload
    for index, scene in enumerate(storyboard.get("scenes") or [], start=1):
        sid = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
        reviewed_scene = reviewed_scenes.get(sid)
        new_asset = reviewed_scene.get("asset") if reviewed_scene else ""
        if new_asset:
            scene["asset"] = new_asset
            scene["assetUrl"] = new_asset
            scene["asset_url"] = new_asset
            scene["asset_state"] = "approved"
            scene["assetState"] = "approved"
    project_path.write_text(json.dumps(project, indent=2), encoding="utf-8")

    target = project.get("pipeline_target") or "short-shorts"
    engine = normalize_engine(project.get("engine") or request.get("engine") or "hyperframes")
    execute_requested = bool(request.get("execute"))
    live = os.environ.get("STORYBOARD_BRIDGE_LIVE") == "1"
    should_execute = execute_requested and live

    command = build_materialize_command(str(job_dir)) + " && " + build_render_command(str(job_dir), target, engine)
    (job_dir / "launch-command.txt").write_text(command + "\n", encoding="utf-8")

    execution = {"ran": False, "returncode": None, "stdout": "", "stderr": ""}
    if should_execute:
        (job_dir / "logs").mkdir(exist_ok=True)
        completed = subprocess.run(command, cwd=REPO_ROOT, shell=True, text=True, capture_output=True, timeout=1800)
        execution = {
            "ran": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        (job_dir / "logs" / "render-execution.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")

    final = job_dir / "exports" / "final.mp4"
    return {
        "ok": True,
        "status": "executed" if should_execute else "dry_run",
        "job_id": job_id,
        "job_dir": str(job_dir),
        "command": command,
        "final_video": f"/jobs/{job_id}/exports/final.mp4" if final.exists() else "",
        "execution": execution,
    }
```

Confirm the `render` branch added in Task 4's `do_POST` is present:

```python
            elif request.get("action") == "render":
                result = run_render_job(request, self.jobs_root)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bridge_workflow -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "feat: add render action that applies reviewed images then renders"
```

---

## Task 6: Pure review-state logic module

**Files:**
- Create: `storyboard/review-gate.js`
- Test: `tests/review_gate.test.js`

**Interfaces:**
- Produces (`window.ReviewGate` in browser, `module.exports` in Node):
  - `reviewStateFor(scene) -> "needs-review" | "approved" | "flagged"`
  - `allApproved(scenes) -> boolean`
  - `applyMaterializeResult(scenes, result, bridgeBase) -> scenes[]` (sets `previewUrl`, `assetUrl`, `reviewState="needs-review"`, `materializeStatus` for scenes present in `result.scenes`)
  - `markReviewed(scenes, sceneId, stateValue) -> scenes[]`
  - `resetOnSwap(scene) -> scene` (returns a copy with `reviewState="needs-review"`)

- [ ] **Step 1: Write the failing test**

Create `tests/review_gate.test.js`:

```javascript
const assert = require('assert');
const gate = require('../storyboard/review-gate.js');

// allApproved
assert.strictEqual(gate.allApproved([]), false, 'empty is not approved');
assert.strictEqual(
  gate.allApproved([{ id: 'a', reviewState: 'approved' }, { id: 'b', reviewState: 'needs-review' }]),
  false,
  'one pending blocks approval'
);
assert.strictEqual(
  gate.allApproved([{ id: 'a', reviewState: 'approved' }, { id: 'b', reviewState: 'approved' }]),
  true,
  'all approved passes'
);

// applyMaterializeResult
const applied = gate.applyMaterializeResult(
  [{ id: 'a', assetUrl: 'old' }],
  { scenes: [{ scene_id: 'a', image_url: '/jobs/j/assets/001.png', status: 'generated' }] },
  'http://127.0.0.1:8788'
);
assert.strictEqual(applied[0].previewUrl, 'http://127.0.0.1:8788/jobs/j/assets/001.png', 'preview url set');
assert.strictEqual(applied[0].reviewState, 'needs-review', 'materialized scenes need review');
assert.strictEqual(applied[0].materializeStatus, 'generated', 'status carried through');

// markReviewed
const marked = gate.markReviewed(applied, 'a', 'approved');
assert.strictEqual(marked[0].reviewState, 'approved', 'approve sets state');

// resetOnSwap
assert.strictEqual(gate.resetOnSwap({ id: 'a', reviewState: 'approved' }).reviewState, 'needs-review', 'swap resets review');

console.log('review-gate tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/review_gate.test.js`
Expected: FAIL with `Cannot find module '../storyboard/review-gate.js'`

- [ ] **Step 3: Write minimal implementation**

Create `storyboard/review-gate.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ReviewGate = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  function reviewStateFor(scene) {
    if (!scene) return 'needs-review';
    return scene.reviewState || 'needs-review';
  }

  function allApproved(scenes) {
    return Array.isArray(scenes) && scenes.length > 0 &&
      scenes.every(function (s) { return reviewStateFor(s) === 'approved'; });
  }

  function applyMaterializeResult(scenes, result, bridgeBase) {
    var base = String(bridgeBase || '');
    var byId = {};
    ((result && result.scenes) || []).forEach(function (r) { byId[r.scene_id] = r; });
    return (scenes || []).map(function (s) {
      var r = byId[s.id];
      if (!r) return s;
      var copy = Object.assign({}, s);
      if (r.image_url) {
        copy.previewUrl = base + r.image_url;
        copy.assetUrl = base + r.image_url;
      }
      copy.reviewState = 'needs-review';
      copy.materializeStatus = r.status || '';
      return copy;
    });
  }

  function markReviewed(scenes, sceneId, stateValue) {
    return (scenes || []).map(function (s) {
      if (s.id !== sceneId) return s;
      var copy = Object.assign({}, s);
      copy.reviewState = stateValue;
      return copy;
    });
  }

  function resetOnSwap(scene) {
    var copy = Object.assign({}, scene);
    copy.reviewState = 'needs-review';
    return copy;
  }

  return {
    reviewStateFor: reviewStateFor,
    allApproved: allApproved,
    applyMaterializeResult: applyMaterializeResult,
    markReviewed: markReviewed,
    resetOnSwap: resetOnSwap,
  };
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/review_gate.test.js`
Expected: `review-gate tests passed`

- [ ] **Step 5: Commit**

```bash
git add storyboard/review-gate.js tests/review_gate.test.js
git commit -m "feat: add pure review-gate state module with node tests"
```

---

## Task 7: Wire the Review Board into the UI

**Files:**
- Modify: `storyboard/index.html` (include `review-gate.js`; add Generate + Render buttons; scene-card review badge)
- Modify: `storyboard/ultimate-workflow.js` (`generateImages`, `renderVideo`, review-state wiring, Render lock)

**Interfaces:**
- Consumes: `window.ReviewGate` (Task 6); bridge `POST /api/launch` with `action:"materialize"` and `action:"render"`, and `GET /jobs/...` (Tasks 2, 4, 5).
- Produces: user-facing generate → review → render loop. No new exported symbols.

- [ ] **Step 1: Add the module include and buttons to `index.html`**

In `storyboard/index.html`, immediately before the existing
`<script src="ultimate-workflow.js?v=..."></script>` line, add:

```html
    <script src="review-gate.js?v=20260701-1"></script>
```

Find the bridge action button row containing `id="sendBridgeBtn"` and
`id="sendExecuteBtn"`. Add two buttons in that same row:

```html
      <button id="generateImagesBtn" class="btn">Generate images</button>
      <button id="renderVideoBtn" class="btn" disabled>Render video</button>
```

- [ ] **Step 2: Add `generateImages()` and `renderVideo()` to `ultimate-workflow.js`**

In `storyboard/ultimate-workflow.js`, add these functions just before the
`toggleTheme` definition (~line 147):

```javascript
    async function generateImages(){
      const issues=validateScenes();
      if(issues.some(x=>x.status==='fail')){ q('responseBox').value=JSON.stringify({ok:false,message:'Fix validation failures before generating.',validation:issues},null,2); addEvent('Generate blocked by validation.'); return; }
      const base=q('bridgeUrlInput').value.trim();
      const body={machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim()||'storyboard-ultimate-001',execute:true,action:'materialize',payload:payload()};
      try{
        const res=await fetch(base+'/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const out=await res.json();
        q('responseBox').value=JSON.stringify(out,null,2);
        if(!out.ok){throw new Error(out.error||'generate failed');}
        state.currentJobId=out.job_id;
        if(Array.isArray(out.scenes)&&out.scenes.length){ state.scenes=ReviewGate.applyMaterializeResult(state.scenes,out,base); }
        state.project.workflow_stage='approve';
        addEvent(`Generated images for ${out.job_id}. Review each scene.`);
        renderAll();
      }catch(err){ q('responseBox').value=String(err); addEvent('Generate failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).'); }
    }

    async function renderVideo(){
      if(!ReviewGate.allApproved(state.scenes)){ q('responseBox').value=JSON.stringify({ok:false,message:'Approve every scene before rendering.'},null,2); addEvent('Render blocked: not all scenes approved.'); return; }
      if(!state.currentJobId){ q('responseBox').value=JSON.stringify({ok:false,message:'Generate images first so there is a job to render.'},null,2); return; }
      const base=q('bridgeUrlInput').value.trim();
      const body={machine:state.selectedMachineId,engine:q('engineSelect').value,run_label:q('runLabelInput').value.trim()||'storyboard-ultimate-001',execute:true,action:'render',job_id:state.currentJobId,payload:payload()};
      try{
        const res=await fetch(base+'/api/launch',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
        const out=await res.json();
        q('responseBox').value=JSON.stringify(out,null,2);
        if(!out.ok){throw new Error(out.error||'render failed');}
        state.project.workflow_stage='render';
        addEvent(out.final_video?`Rendered: ${out.final_video}`:'Render requested (dry-run or pending).');
        renderAll();
      }catch(err){ q('responseBox').value=String(err); addEvent('Render failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).'); }
    }
```

- [ ] **Step 3: Wire buttons, review state, and the Render lock**

In `storyboard/ultimate-workflow.js`:

(a) After the existing `q('sendExecuteBtn').onclick=...` wiring (~line 150), add:

```javascript
    q('generateImagesBtn').onclick=generateImages; q('renderVideoBtn').onclick=renderVideo;
```

(b) Change the Approve/Flag/Ready handlers (~line 154) to also set `reviewState`:

```javascript
    q('readyBtn').onclick=()=>updateScene({status:'ready'}); q('approveBtn').onclick=()=>updateScene({status:'approved',reviewState:'approved'}); q('flagBtn').onclick=()=>updateScene({status:'flagged',reviewState:'flagged'});
```

(c) In `uploadImageToScene` (~line 31), after `sc.assetState='approved';`, add a review reset:

```javascript
        sc.reviewState='needs-review';
```

(d) In the inspector `assetUrlInput` wiring (the `[['assetUrlInput','assetUrl'], ...]` block, ~line 152), a URL swap must reset review. Replace the generic loop's handling for `assetUrl` by adding this line right after that `.forEach(...)` block:

```javascript
    q('assetUrlInput').addEventListener('change',()=>updateScene({reviewState:'needs-review'}));
```

(e) In `renderAll` (~line 48), after `updateBridgeStatusText();`, add the lock:

```javascript
    if(q('renderVideoBtn')) q('renderVideoBtn').disabled=!ReviewGate.allApproved(state.scenes);
```

(f) In `renderScenes` (~line 42), add a review badge. In the scene-card
`innerHTML`, inside the row of `<span class="pill">` badges, add a review pill
after the `${s.assetState}` pill:

```javascript
<span class="pill">${ReviewGate.reviewStateFor(s)}</span>
```

- [ ] **Step 4: Manual smoke test (servers running)**

Ensure the bridge is running with the live gate:

```bash
STORYBOARD_BRIDGE_LIVE=1 python scripts/bridge_server.py --host 127.0.0.1 --port 8788
```

and the UI server: `python -m http.server 8128 --bind 127.0.0.1 --directory storyboard`.

In the browser at `http://127.0.0.1:8128/`:
1. Click **Generate images** → each scene card fills with its generated image; every scene shows a `needs-review` pill; **Render video** stays disabled.
2. Click a scene, paste a real image URL into **Asset URL** (or drag-drop a file) → that scene returns to `needs-review`.
3. Click **Approve** on each scene → when the last one is approved, **Render video** enables.
4. Click **Render video** → response shows `final_video: /jobs/<id>/exports/final.mp4`.
5. Open `http://127.0.0.1:8788/jobs/<id>/exports/final.mp4` and confirm it plays; run `ffprobe` on the file under `bridge-jobs/<id>/exports/final.mp4` to confirm H.264 1080x1920.

Expected: Render is impossible until all scenes are approved; a swapped image appears in the rendered output.

- [ ] **Step 5: Run the full test suite**

Run:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
node tests/review_gate.test.js
node tests/storyboard_ui_contract.test.js
```
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add storyboard/index.html storyboard/ultimate-workflow.js
git commit -m "feat: add generate/review/render gate to storyboard UI"
```

---

## Self-Review Notes

- **Spec coverage:** split pipeline (Tasks 1, 4, 5) ✓; job read + job static route so images show in browser (Tasks 2, 3) ✓; Review Board with per-scene state and swap-resets-review (Tasks 6, 7) ✓; Render locked until all approved (Tasks 6 `allApproved`, 7 step 3e) ✓; live-execution gate preserved (Tasks 4, 5 honor `STORYBOARD_BRIDGE_LIVE`) ✓; engines untouched ✓.
- **Deferred (out of scope, per spec):** in-app image search / regenerate (Phase 2), audio mux (Phase 3), video clips (later).
- **Open decisions resolved:** (1) `action` field on `/api/launch` rather than new endpoints; (2) separate `/jobs/<id>/...` static route; (3) render enforcement is client-side lock (`allApproved`) plus the existing live gate — `run_render_job` trusts the reviewed payload and does not re-enforce server-side, keeping it simple.
- **Type consistency:** `build_materialize_command`/`build_render_command` names match across Tasks 1, 4, 5; `read_job` return shape (`scenes[].image_url/status`) matches `applyMaterializeResult`'s expected `result.scenes[].image_url/status` in Task 6; `reviewState` values (`needs-review`/`approved`/`flagged`) are consistent across Tasks 6 and 7.
