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
  storyboard_to_config.py            Current prototype converter
templates/
  storyboards/
    basic-storyboard.csv             Starting CSV storyboard template
```

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
