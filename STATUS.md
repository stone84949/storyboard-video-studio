# STATUS

Current state: storyboard-to-render workflow is integrated for safe dry-runs, asset materialization, and first live HyperFrames renders on BEAST.

## What works now

- Primary storyboard UI: `storyboard/index.html` with Ultimate Workflow console logic in `storyboard/ultimate-workflow.js` and reusable simple-UI logic retained in `storyboard/storyboard.js`.
- UI supports scene reorder, duration resize, JSON import/apply, asset library assignment, validation, narration fields, VO auto-fill, fit durations, export bundle, editor handoff export, bridge status ping/poll, bridge send, and send + execute request.
- Local bridge: `scripts/bridge_server.py` exposes `GET /api/health`, `GET /api/status`, and `POST /api/launch`.
- Windows launcher: `start-bridge.bat` starts the bridge at `127.0.0.1:8788` by default.
- Shared path registry: `studio_paths.json` links this repo, OpenMontage, and the existing content-factory output folders.
- Bridge writes inspectable job folders under `bridge-jobs/` with `project.json`, `STATUS.md`, `activity.md`, `scenes/*.json`, `storyboard/payload.json`, and `launch-command.txt`.
- Pipeline targets are mapped for `short-shorts`, `longer-shorts`, and `montage`.
- `scripts/storyboard_to_config.py` now accepts bridge `project.json` input and can preview or write render config/handoff artifacts.
- `scripts/render_hyperframes_job.py` turns bridge jobs into a self-contained HyperFrames workspace and writes `exports/final.mp4`.
- `scripts/materialize_assets.py` runs before HyperFrames jobs. It downloads usable remote images, copies local files, can call OpenMontage image providers when credentials are available, and falls back to generated local SVG scene art.
- `short-shorts` and `longer-shorts` bridge commands now materialize assets and then call the HyperFrames live renderer when the live gate is enabled.
- `scripts/prepare_montage_handoff.py` turns montage bridge jobs into OpenMontage/editor handoff packages.
- Storyboard exports include an image replacement plan for missing/flagged assets.
- Browser payload preview was verified to emit a `replacement_plan` item when a scene is marked `needs-image`.

## Dry-run proof

- Python bridge/unit tests: pass.
- Node storyboard UI contract test: pass.
- Browser UI sanity check at `http://127.0.0.1:8128/`: pass.
- Bridge health/API test at `http://127.0.0.1:8788`: pass.
- Ultimate Workflow browser bridge send created `bridge-jobs/20260628-054614-storyboard-ultimate-001/`.
- Send + execute from Ultimate Workflow stayed safely in `dry_run` without `STORYBOARD_BRIDGE_LIVE=1`.
- Dry-run launch jobs created for all three pipeline targets.
- Validation failure behavior tested through unit/API paths.

## Live render proof

- Direct renderer smoke: `python scripts/render_hyperframes_job.py bridge-jobs/20260628-054612-codex-ui-smoke/project.json --target longer-shorts --quality draft --skip-validate`
  - Output: `bridge-jobs/20260628-054612-codex-ui-smoke/exports/final.mp4`
  - Verified with `ffprobe`: H.264, 1080x1920, 30fps, 6.4s.
  - HyperFrames validate: PASS, no console errors.
- End-to-end bridge live smoke:
  - Bridge restarted with `STORYBOARD_BRIDGE_LIVE=1`.
  - `POST /api/launch` with `execute: true` returned `status: executed`.
  - Output: `bridge-jobs/20260628-060834-codex-live-render-smoke/exports/final.mp4`
  - Verified with `ffprobe`: H.264, 1080x1920, 30fps, 2.0s.
- Generated-asset HyperFrames proof:
  - Command: `python scripts/materialize_assets.py bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/project.json --provider auto` then `python scripts/render_hyperframes_job.py bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/project.json --target short-shorts --quality draft`
  - Asset manifest: `bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/exports/asset-manifest.json`
  - Output: `bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/exports/final.mp4`
  - Verified with `ffprobe`: H.264, 1080x1920, 30fps, 6.0s.
- Real-image end-to-end bridge proof:
  - Bridge executed with `STORYBOARD_BRIDGE_LIVE=1` and `execute: true`.
  - Job: `bridge-jobs/20260628-142850-real-image-e2e-proof/`
  - Asset materializer downloaded three remote JPEG scene images into `assets/images/materialized/` and copied them into the generated HyperFrames workspace.
  - Output: `bridge-jobs/20260628-142850-real-image-e2e-proof/exports/final.mp4`
  - Proof frame: `bridge-jobs/20260628-142850-real-image-e2e-proof/exports/proof-frame-2s.jpg`
  - Verified with `ffprobe`: H.264, 1080x1920, 30fps, 7.0s, 3,539,333 bytes.
- End-to-end OpenMontage handoff smoke:
  - `POST /api/launch` with `pipeline_target: montage` and `execute: true` returned `status: executed`.
  - Job output: `bridge-jobs/20260628-063336-montage-dry-run/exports/openmontage-handoff.json`
  - OpenMontage working copy: `C:\Workspace\Repos\OpenMontage\projects\20260628-063336-montage-dry-run-openmontage-handoff`
  - Produced `storyboard/storyboard-handoff.json`, `editor-handoff/editor-handoff.md`, `editor-handoff/shotcut-notes.txt`, and `editor-handoff/resolve-timeline.csv`.

## Definition of Done status

- Storyboard UI usable as main control surface: done.
- Story understandable at a glance: done through scene cards, preview, inspector, notes, and payload preview.
- Scene image swap: done through Asset URL inspector field.
- Asset library assignment: done through the Asset Library panel.
- Scene reorder: done through draggable scene cards and tested reusable logic.
- Scene duration editing: done through duration field and timeline clip resize.
- Scene timeline editing: done through recalculated starts, timeline resize, and editor exports with start/duration.
- Narration fields: done.
- VO auto-fill: done and tested.
- Fit durations: done and tested.
- Validation blocks bad launches: done in Ultimate Workflow for failures/flagged/needs-image states and tested at logic/API levels.
- Image failure/replacement path: done as clear flags plus `replacement_plan`, `materialize_assets.py`, and an inspectable asset manifest.
- Bridge write: done.
- Execute/dry-run execute: done.
- HyperFrames receives a working copy: done; live MP4 produced.
- OpenMontage receives a working copy: done; handoff project produced.
- Short shorts path: tested.
- Longer shorts path: tested.
- Montage path: tested.
- Editor handoff export: done and tested.
- Duplicate workflow snapshots: archived under `archive/storyboard-snapshots/2026-06-28/`.
- Docs updated for next human/agent: done.

## Live execution gate

Live command execution is disabled unless the bridge process is started with:

```text
STORYBOARD_BRIDGE_LIVE=1
```

Without that flag, `execute: true` still writes the job folder but returns `status: dry_run` and does not run shell commands.

## Known limitations

- Current live HyperFrames renderer can create a real visual MP4 from downloaded or generated scene images, but it does not yet mux narration, voiceover, music, or SFX into the final file.
- Cloud/AI image generation through OpenMontage providers is wired by provider name, but not proven in this shell because OpenAI, Google/Gemini, xAI/Grok, FAL, Pexels, Pixabay, and Unsplash keys are not visible in the environment. OpenMontage registry discovery also needs its Python dependencies installed for full selector use.
- OpenMontage path currently proves a validated handoff/working-copy package, not a full OpenMontage-rendered MP4.
- UI is a static local control layer, not yet mounted into Mission Control.
- Accessibility labels still need polish; Chrome currently flags unlabeled form fields, but there are no JavaScript console errors in the verified browser smoke.
