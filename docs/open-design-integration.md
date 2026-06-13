# Open Design Integration

Open Design is installed on this machine and should be considered a major
supporting tool for the storyboard video studio.

## Current Local Status

Observed on 2026-06-13:

- Open Design app is running from:
  `C:\Users\jston\AppData\Local\Programs\Open Design\Open Design.exe`
- The `od` CLI is not currently on PATH in this shell.
- The daemon is reachable through local HTTP ports exposed by the app.
- Working health endpoint:
  `http://127.0.0.1:58991/api/health`
- The daemon reported version `0.10.1`.
- MCP install info is available at:
  `http://127.0.0.1:58991/api/mcp/install-info`

The MCP snippet from the daemon uses the packaged app as the command:

```json
{
  "command": "C:\\Users\\jston\\AppData\\Local\\Programs\\Open Design\\Open Design.exe",
  "args": [
    "C:\\Users\\jston\\AppData\\Local\\Programs\\Open Design\\resources\\app\\prebundled\\daemon\\daemon-cli.mjs",
    "mcp"
  ]
}
```

## Why It Matters Here

Open Design gives this repo a reusable design and motion library without forcing
the longer-video workflow to become a catch-all pipeline.

Use it for:

- picking visual directions before a first pilot
- browsing video-specific skills and templates
- generating or prototyping HyperFrames-compatible motion scenes
- comparing style lanes such as documentary, character explainer, talking head,
  data explainer, and editorial motion
- pulling design-system guidance before building a template

## Relevant Built-In Skills Found

Video and motion candidates:

- `video-hyperframes`
- `8-bit-orbit-video-template`
- `after-hours-editorial-template`
- `digits-fintech-swiss-template`
- `field-notes-editorial-template`
- `swiss-creative-mode-template`
- `swiss-user-research-video-template`
- `frame-data-chart-nyt`
- `frame-flowchart-sticky`
- `frame-glitch-title`
- `frame-light-leak-cinema`
- `frame-logo-outro`
- `vfx-text-cursor`

Talking-head / generated-video candidates:

- `fal-lip-sync`
- `fal-kling-o3`
- `fal-video-edit`
- `sora`
- `venice-video`

Supporting design candidates:

- `brandkit`
- `color-expert`
- `creative-director`
- `design-taste-frontend`
- `theme-factory`
- `web-design-guidelines`

## First Pilot Recommendation

Before building a custom template from scratch, use Open Design to inspect two
or three candidate style lanes:

1. Sourced-image documentary explainer.
2. Editorial/data explainer.
3. Talking-head plus motion graphics.

Then choose one lane for the first 2+ minute pilot. Do not attempt all lanes in
the first implementation.

## Useful Verification Commands

Use HTTP while `od` is not on PATH:

```powershell
curl.exe -s http://127.0.0.1:58991/api/health
curl.exe -s http://127.0.0.1:58991/api/skills
curl.exe -s http://127.0.0.1:58991/api/design-systems
curl.exe -s http://127.0.0.1:58991/api/mcp/install-info
```

If the packaged CLI is later added to PATH, prefer:

```powershell
od doctor
od status --json
od skills list --json
od design-systems list --json
```
