# Pipeline Map

The storyboard UI is now the front-end control layer. It emits one reusable bundle shape, then the bridge maps that bundle into target-specific job folders and command paths.

Local repo/output links are recorded in `studio_paths.json`:

- Control repo: `C:\Workspace\Repos\storyboard-video-studio`
- OpenMontage repo: `C:\Workspace\Repos\OpenMontage`
- Existing content-factory repo: `G:\My Drive\Projects\Active\content-factory-render`
- Existing content-factory outputs: `G:\My Drive\Projects\Active\content-factory-render\out`

## Shared input contract

`POST /api/launch` accepts:

```json
{
  "machine": "BEAST",
  "engine": "storyboard-ui",
  "run_label": "example run",
  "execute": false,
  "payload": {
    "project_title": "Example",
    "pipeline_target": "short-shorts",
    "aspect_ratio": "9:16",
    "target_duration_seconds": 30,
    "scenes": []
  }
}
```

## Shared bridge output structure

```text
bridge-jobs/<timestamp-run-label>/
  project.json
  STATUS.md
  activity.md
  launch-command.txt
  storyboard/
    payload.json
  scenes/
    001-scene-001.json
    002-scene-002.json
  exports/
  editor-handoff/
  logs/
```

For image failures, storyboard payloads may include:

```json
{
  "replacement_plan": [
    {
      "scene_id": "scene-001",
      "reason": "asset marked needs-image",
      "search_prompt": "scene title plus notes",
      "fallback_asset": "generated-fallback-001.svg",
      "status": "needs-replacement"
    }
  ]
}
```

## 1. short-shorts

- Expected input: 3-8 scenes, vertical 9:16, concise narration, still images, slow Ken Burns motion.
- Asset step: `scripts/materialize_assets.py` resolves scene assets before render and writes `exports/asset-manifest.json`.
- Transform step: `project.json` -> `scripts/render_hyperframes_job.py` -> HyperFrames workspace -> MP4.
- Output files: bridge job folder, per-scene JSON, materialized assets, `hyperframes/index.html`, `exports/asset-manifest.json`, `exports/final.mp4`, `exports/render-summary.json`, and render logs.
- Command path:

```text
python scripts/materialize_assets.py <job_dir>/project.json --provider auto
python scripts/render_hyperframes_job.py <job_dir>/project.json --target short-shorts --quality draft
```

- Dry-run test result: PASS using `tests/launch_payload_short.json` and converter `--dry-run`.
- Live render result: PASS via bridge live smoke, wrote `exports/final.mp4`.
- Known limitations: no-key proof uses generated local SVG scene art; OpenMontage cloud image providers require visible credentials.

## 2. longer-shorts

- Expected input: 6+ scenes, stronger narration pacing, vertical 9:16, validation warnings watched closely.
- Transform step: storyboard bundle -> bridge job -> asset materialization -> HyperFrames workspace -> MP4.
- Output files: same bridge structure plus materialized assets, `hyperframes/`, `exports/asset-manifest.json`, `exports/final.mp4`, and render logs.
- Command path:

```text
python scripts/materialize_assets.py <job_dir>/project.json --provider auto
python scripts/render_hyperframes_job.py <job_dir>/project.json --target longer-shorts --quality draft
```

- Dry-run test result: PASS using `tests/launch_payload_longer.json` and converter `--dry-run`.
- Direct live render result: PASS, wrote `bridge-jobs/20260628-054612-codex-ui-smoke/exports/final.mp4`.
- Known limitations: pacing checks are warnings, not hard blockers; richer 2+ minute layout/timing polish is still needed.

## 3. montage

- Expected input: image sequences, narration timing, transition/motion notes, finishing notes for Shotcut/Resolve.
- Transform step: storyboard bundle -> bridge job -> OpenMontage/editor handoff package.
- Output files: bridge job folder, per-scene JSON, editor handoff markdown, Shotcut notes, Resolve-friendly timing CSV, and OpenMontage project copy.
- Command path:

```text
python scripts/prepare_montage_handoff.py <job_dir>/project.json
```

- Dry-run test result: PASS using `tests/launch_payload_montage.json`; bridge wrote the job folder and command path.
- Live handoff result: PASS via bridge `execute: true`, wrote `bridge-jobs/20260628-063336-montage-dry-run/` and `C:\Workspace\Repos\OpenMontage\projects\20260628-063336-montage-dry-run-openmontage-handoff`.
- Known limitations: OpenMontage receives a validated working copy; full OpenMontage render automation remains a later layer.

## Live mode rule

The bridge never runs commands just because the UI sends `execute: true`. It only runs when both are true:

1. Request has `execute: true`.
2. Bridge was started with `STORYBOARD_BRIDGE_LIVE=1`.
