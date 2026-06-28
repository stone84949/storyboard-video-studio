# Storyboard Video Studio

Storyboard-first video workflow for 2+ minute explainer videos.

This repo is intentionally separate from the existing shorts pipeline. The shorts
pipeline is good at fast, stylized vertical shorts. This project is for longer
videos where the hard parts are different: sourced images, image licensing,
asset review, talking-head or character styles, and scene-by-scene storyboard
control.

## Initial Focus

MVP 1 is a sourced-image explainer workflow:

1. Write a storyboard.
2. Build an asset board for every real image or screenshot.
3. Approve sources, crops, focal points, and replacements.
4. Generate a HyperFrames-ready video folder.
5. Render a 2+ minute MP4.

## Repo Layout

```text
docs/
  prototype-storyboard-workflow.md   Original workflow notes from the prototype
prototype/
  Raw downloaded prototype files, preserved for reference
scripts/
  studio_paths.py                    Validates shared local repo/output paths
  storyboard_to_config.py            Current prototype converter
  render_hyperframes_job.py          First live HyperFrames finish-layer renderer
  hermes-bridge.ps1                  Shared Hermes CLI wrapper
  hermes-producer-brief.ps1          Producer / storyboard prompt wrapper
  hermes-asset-research-plan.ps1     Asset Researcher planning wrapper
  hermes-open-design-template-review.ps1  Open Design template-review wrapper
templates/
  storyboards/
    basic-storyboard.csv             Starting CSV storyboard template
```

## Hermes Bridge Wrappers

These wrappers let the repo control the prompt contract while Hermes handles the
actual agent work from inside `C:\Workspace\Repos\storyboard-video-studio`.

## Storyboard Control Layer

The primary local storyboard UI is the Ultimate Workflow console:

```text
storyboard/index.html
```

Run the safe local bridge, then serve the UI:

```bat
start-bridge.bat
python -m http.server 8128 --bind 127.0.0.1 --directory storyboard
```

Open:

```text
http://127.0.0.1:8128/
```

The UI validates scenes, estimates VO timing, fits durations, exports bundles,
exports editor handoffs, and sends jobs to `POST /api/launch` on the bridge.
Bridge jobs are written under `bridge-jobs/` as markdown/json folders. For
`short-shorts` and `longer-shorts`, live mode renders a draft HyperFrames MP4 to
`exports/final.mp4`. Live command execution is disabled unless
`STORYBOARD_BRIDGE_LIVE=1` is set before starting the bridge.

First live render command shape:

```bat
python scripts/render_hyperframes_job.py bridge-jobs/<job-id>/project.json --target short-shorts --quality draft
```

See:

- [STATUS.md](STATUS.md)
- [PIPELINE_MAP.md](PIPELINE_MAP.md)
- [TEST_RESULTS.md](TEST_RESULTS.md)
- [NEXT_ACTIONS.md](NEXT_ACTIONS.md)

## Connected Local Paths

The shared path registry is:

```text
studio_paths.json
```

It links the control repo, OpenMontage repo, and existing content-factory output
folders. Validate the links with:

```bat
python scripts/studio_paths.py
```

## Local Dashboard

The dashboard is the visual control board for the broader workflow: video cards, stage
status, missing asset notes, render links, and the next action for each project.

Build the data snapshot:

```powershell
python scripts\build_dashboard.py
```

Serve it locally:

```powershell
python -m http.server 8127 --bind 127.0.0.1 --directory dashboard
```

Open:

```text
http://127.0.0.1:8127/
```

Examples:

```powershell
# raw bridge smoke test
powershell -ExecutionPolicy Bypass -File scripts/hermes-bridge.ps1 -Prompt "Reply with exactly: HERMES_BRIDGE_OK"

# producer brief to stdout
powershell -ExecutionPolicy Bypass -File scripts/hermes-producer-brief.ps1 -VideoSlug ai-agents-2026 -Topic "How AI coding agents help ship faster" -StdoutOnly

# asset research planning pass
powershell -ExecutionPolicy Bypass -File scripts/hermes-asset-research-plan.ps1 -VideoSlug ai-agents-2026

# Open Design template review after asset-board.csv exists
powershell -ExecutionPolicy Bypass -File scripts/hermes-open-design-template-review.ps1 -VideoSlug ai-agents-2026
```

Helpful switches:

- `-StdoutOnly` returns the deliverable in chat instead of asking Hermes to write files.
- `-PrintPrompt` prints the exact prompt without invoking Hermes.
- `-Yolo` passes `--yolo` through to Hermes when you explicitly want open-lane execution.


## Design Rule

Do not turn this into a jack-of-all-trades video factory. Add a style only when
it has a repeatable workflow and its own template contract.

Planned style lanes:

- Sourced-image documentary explainer
- Talking-head plus motion graphics
- Character-host explainer
- Pure motion-graphics explainer

## Next Build Slice

The first practical improvement should be an asset board, because the prior
workflow struggled most when using real internet images rather than generated
images.

The asset board should track:

- scene or panel number
- intended use
- source URL
- local filename
- license or usage status
- crop mode and focal point
- approval status
- credit or caption text
- replacement notes

Before the first real test run, complete the plugin and skill preflight in
[docs/first-test-preflight.md](docs/first-test-preflight.md).

Open Design is also available locally and should be used as a design/style
source before choosing the first template lane. See
[docs/open-design-integration.md](docs/open-design-integration.md).

Use Open Design's built-in video templates as the first style discovery surface.
See [docs/template-discovery-plan.md](docs/template-discovery-plan.md).

For sourced-image videos, use a dedicated Asset Researcher role before assembly.
See [docs/asset-researcher-agent.md](docs/asset-researcher-agent.md) and
[docs/agent-workflow.md](docs/agent-workflow.md). Ready-to-use prompts are in
[docs/asset-researcher-runbook.md](docs/asset-researcher-runbook.md).
