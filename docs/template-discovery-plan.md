# Template Discovery Plan

Open Design has a built-in "New project" flow for media projects, including a
Video tab with reference templates, editable timing prompts, and the
`hyperframes-html` local renderer.

This should be used before the first pilot to avoid building a custom visual
style too early.

## What We Saw

The Open Design video creation screen includes:

- media project types: Image, Video, Audio
- reference templates
- editable timed prompt blocks
- a local HyperFrames renderer option: `hyperframes-html`
- many built-in video template options

Example visible templates from the screenshot:

- `Magical Academy Storyboard Sequence`
- `Hollywood Haute Couture Fantasy Video Prompt`
- `HyperFrames HTML-in-Canvas 3D iPhone + MacBook Product Demo`
- `HyperFrames HTML-in-Canvas Cinematic Text Cursor Reveal`
- `HyperFrames HTML-in-Canvas Glass Shatter Outro`
- `HyperFrames HTML-in-Canvas Liquid Background Hero`
- `HyperFrames HTML-in-Canvas Liquid Glass Landing Reveal`
- `HyperFrames HTML-in-Canvas Magnetic Field Visualisation`

## How To Use This For The Repo

Open Design should be the template and visual-direction browser.

The repo remains the production source of truth:

- storyboard files
- asset board
- source credits
- chosen template contract
- generated video folders
- render/QA notes

## First Discovery Pass

Before the first 2+ minute pilot:

1. Open Open Design's New Project screen.
2. Choose Media -> Video.
3. Browse the built-in reference templates.
4. Select 3 candidate directions:
   - sourced-image documentary explainer
   - editorial/data explainer
   - talking-head or character-style explainer
5. Generate or inspect a small sample for each candidate.
6. Pick one lane for the first repo-backed pilot.

Do not build all style lanes at once.

## Decision Rule

Choose the first template lane based on:

- works for 2+ minute pacing
- supports real sourced images without fragile cropping
- has room for narration-led scenes
- can be represented as a repeatable storyboard schema
- can export or be recreated as HyperFrames HTML

If a template is visually impressive but depends on one-off prompt magic, do not
make it the first production lane.
