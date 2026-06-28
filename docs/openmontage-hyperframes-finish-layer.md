# OpenMontage HyperFrames Finish Layer

OpenMontage is the finish layer for 2+ minute videos. This repo remains the planning layer: topic, research brief, storyboard, asset board, Open Design/template notes, and QA handoffs.

## Locked First Choice

- Renderer: OpenMontage
- Runtime: HyperFrames
- Pipeline fit: `animated-explainer`
- Composition mode: `atelier` for the first Weird Forgotten History pilot

Why: the channel needs kinetic typography, archival cards, map-like motion, evidence-board layouts, and strong editorial transitions. Remotion stays available as a fallback or for component-heavy explainers, but HyperFrames is the first style lane.

## Working Pilot

Local OpenMontage pilot:

```text
C:\Workspace\Repos\OpenMontage\projects\weird-forgotten-history-hyperframes-pilot
```

Rendered MP4:

```text
C:\Workspace\Repos\OpenMontage\projects\weird-forgotten-history-hyperframes-pilot\renders\final.mp4
```

Verified:

- `npx --yes hyperframes lint`: 0 errors, 1 maintainability warning for keeping all scenes in one file.
- `npx --yes hyperframes validate --no-contrast`: no console errors.
- `npx --yes hyperframes inspect --samples 8`: 0 layout issues.
- `ffprobe`: 1920x1080, H.264, 30fps, 34 seconds.

## Rebuild Commands

Run from:

```powershell
cd C:\Workspace\Repos\OpenMontage\projects\weird-forgotten-history-hyperframes-pilot\hyperframes
```

Then:

```powershell
npx --yes hyperframes lint
npx --yes hyperframes validate --no-contrast
npx --yes hyperframes inspect --samples 8
npx --yes hyperframes render --output ..\renders\final.mp4 --fps 30 --quality draft
```

## Next Real Test

The next test should not be another pure render demo. It should prove the weak point from the old workflow:

1. Pick one Weird Forgotten History topic.
2. Produce a 2-minute storyboard in this repo.
3. Run the Asset Researcher Agent to collect real images/clips/articles into the video folder.
4. Review the Open Design visual lane.
5. Send the approved storyboard and asset board into OpenMontage HyperFrames for the first full render.
