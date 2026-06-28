# Test Results

Run date: 2026-06-28 on BEAST repo path `C:\Workspace\Repos\storyboard-video-studio`.

## Automated tests

| Test | Command | Result |
|---|---|---|
| Bridge contract tests | `python -m unittest tests.test_bridge_workflow -v` | PASS, including nested Ultimate Workflow payload |
| Storyboard converter JSON tests | `python -m unittest tests.test_storyboard_to_config -v` | PASS |
| Full Python test set | `python -m unittest tests.test_storyboard_to_config tests.test_bridge_workflow tests.test_montage_handoff -v` | PASS, 7 tests |
| Asset materializer test set | `python -m unittest tests.test_materialize_assets tests.test_bridge_workflow tests.test_storyboard_to_config tests.test_montage_handoff -v` | PASS, 8 tests |
| UI contract/pure logic test | `node tests/storyboard_ui_contract.test.js` | PASS |
| Python compile sweep | `python -m py_compile scripts\bridge_server.py scripts\storyboard_to_config.py scripts\render_hyperframes_job.py scripts\prepare_montage_handoff.py scripts\studio_paths.py scripts\build_dashboard.py` | PASS |
| Asset materializer compile sweep | `python -m py_compile scripts\materialize_assets.py scripts\bridge_server.py scripts\render_hyperframes_job.py` | PASS |

## Manual/smoke tests

| Feature | Method | Result |
|---|---|---|
| UI sanity check | Served with `python -m http.server 8128 --bind 127.0.0.1 --directory storyboard`; opened `http://127.0.0.1:8128/` in browser | PASS |
| Scene reorder | Node contract test `moveScene()` plus UI Up/Down controls present | PASS |
| Timeline resize | Browser rendered duration range/number controls; Node fit/resize contract tested | PASS |
| Validation success | Browser displayed `PASS: storyboard validation succeeded.` | PASS |
| Validation failure | Node validation test with missing title/narration/duration; bridge malformed request test | PASS |
| Narration fields | Browser rendered narration textareas for each scene | PASS |
| VO auto-fill | Browser button exercised; Node `autoFillVoTiming()` tested | PASS |
| Fit durations | Browser button exercised; Node `fitDurations()` tested | PASS |
| Export bundle | Node `buildExportBundle()` tested; UI button present | PASS |
| Editor handoff export | Browser generated `# Editor Handoff: Forgotten Weird History Dry Run` | PASS |
| Bridge health | `curl -s http://127.0.0.1:8788/api/health` | PASS |
| Bridge send | Browser `Send bridge` returned `status: dry_run` and wrote a job folder | PASS |
| Ultimate Workflow nested payload send | Browser `Send to bridge` wrote `bridge-jobs/20260628-054614-storyboard-ultimate-001/`; converter preview succeeded | PASS |
| Bridge status/poll endpoint | `GET /api/status` returns service state plus recent jobs for the Ultimate Workflow poll button | PASS |
| Send + execute behavior | Browser `Send + execute` with execute checked returned `status: dry_run` while live gate disabled | PASS |
| Direct HyperFrames live render | `python scripts/render_hyperframes_job.py bridge-jobs/20260628-054612-codex-ui-smoke/project.json --target longer-shorts --quality draft --skip-validate` | PASS; wrote `exports/final.mp4` |
| HyperFrames generated workspace validate | `npx --yes hyperframes validate --no-contrast` inside the generated workspace | PASS; no console errors |
| End-to-end bridge live render | Bridge restarted with `STORYBOARD_BRIDGE_LIVE=1`; `POST /api/launch` sent with `execute: true` | PASS; returned `status: executed` and wrote `exports/final.mp4` |
| Image replacement / flagged asset case | `node tests/storyboard_ui_contract.test.js` exercises `flagBadAssets()` and `buildReplacementPlan()` | PASS |
| Browser replacement-plan payload | Chrome DevTools on `http://127.0.0.1:8128/?refresh=20260628-0645`; changed selected scene asset state to `needs-image` | PASS; payload included one `replacement_plan` item for `scene-01` |
| Browser import/apply + asset assignment | Chrome DevTools on `http://127.0.0.1:8128/?refresh=20260628-1255`; added an asset, assigned it, edited payload JSON, and applied it | PASS; selected scene asset changed and imported payload reduced scene list to one edited scene |
| Asset materialization proof | `python scripts/materialize_assets.py bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/project.json --provider auto` | PASS; wrote 3 generated local SVG assets and `exports/asset-manifest.json` |
| Generated-asset HyperFrames render | `python scripts/render_hyperframes_job.py bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/project.json --target short-shorts --quality draft` | PASS; wrote `exports/final.mp4` using materialized scene assets |
| OpenMontage handoff unit | `python -m unittest tests.test_montage_handoff -v` | PASS |
| End-to-end OpenMontage handoff | `POST /api/launch` with montage payload and `execute: true` | PASS; returned `status: executed` and wrote bridge + OpenMontage handoff files |
| UI HTTP sanity | `Invoke-WebRequest http://127.0.0.1:8128/` | PASS, 200 OK |
| Path registry | `python scripts/studio_paths.py` | PASS, all five linked paths exist |
| Dashboard rebuild | `python scripts/build_dashboard.py` | PASS |

## Pipeline dry-runs

| Target | Payload | Result |
|---|---|---|
| short-shorts | `tests/launch_payload_short.json` | PASS; wrote `bridge-jobs/20260628-051019-short-shorts-dry-run/` |
| longer-shorts | `tests/launch_payload_longer.json` | PASS; wrote `bridge-jobs/20260628-051019-longer-shorts-dry-run/` |
| montage | `tests/launch_payload_montage.json` | PASS; wrote `bridge-jobs/20260628-051019-montage-dry-run/` |

## OpenMontage handoff outputs

- Bridge job: `bridge-jobs/20260628-063336-montage-dry-run/`
- Bridge handoff JSON: `bridge-jobs/20260628-063336-montage-dry-run/exports/openmontage-handoff.json`
- Bridge editor handoff: `bridge-jobs/20260628-063336-montage-dry-run/exports/editor-handoff.md`
- Shotcut notes: `bridge-jobs/20260628-063336-montage-dry-run/editor-handoff/shotcut-notes.txt`
- Resolve timing CSV: `bridge-jobs/20260628-063336-montage-dry-run/editor-handoff/resolve-timeline.csv`
- OpenMontage working copy: `C:\Workspace\Repos\OpenMontage\projects\20260628-063336-montage-dry-run-openmontage-handoff`
- OpenMontage storyboard package: `C:\Workspace\Repos\OpenMontage\projects\20260628-063336-montage-dry-run-openmontage-handoff\storyboard\storyboard-handoff.json`

## Converter dry-runs

Command:

```bat
python scripts/storyboard_to_config.py bridge-jobs/20260628-051019-short-shorts-dry-run/project.json --target short-shorts --dry-run
python scripts/storyboard_to_config.py bridge-jobs/20260628-051019-longer-shorts-dry-run/project.json --target longer-shorts --dry-run
python scripts/storyboard_to_config.py bridge-jobs/20260628-051019-montage-dry-run/project.json --target montage --dry-run
```

Result: PASS for all three; each printed a valid preview table with 1080x1920 vertical config and expected panels.

## Live render outputs

- `bridge-jobs/20260628-054612-codex-ui-smoke/exports/final.mp4`: H.264, 1080x1920, 30fps, 6.4s.
- `bridge-jobs/20260628-060834-codex-live-render-smoke/exports/final.mp4`: H.264, 1080x1920, 30fps, 2.0s.
- `bridge-jobs/20260628-074528-generated-assets-hyperframes-proof/exports/final.mp4`: H.264, 1080x1920, 30fps, 6.0s; scenes use materialized generated SVG assets.

## Browser QA note

Chrome DevTools reported no JavaScript console errors after refresh. Remaining browser issue is accessibility labeling polish: `No label associated with a form field (count: 25)`.

## Known test limitation

The current no-key proof uses generated local SVG scene art. OpenMontage cloud/image-provider generation is wired but not proven in this shell because the relevant API keys are not visible. OpenMontage is proven as a handoff package, not yet as a fully automated OpenMontage MP4 render.
