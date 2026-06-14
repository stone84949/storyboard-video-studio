# Asset Researcher Runbook

This file contains ready-to-use prompts and command patterns for running an
Asset Researcher agent. The agent should do the research later; this repo
defines how to ask for it and what files it must produce.

## When To Use

Run this after a storyboard exists and before Open Design/template assembly.

Minimum input:

```text
videos/<slug>/storyboard.md
```

Expected output:

```text
videos/<slug>/asset-board.csv
videos/<slug>/sources/source-notes.md
videos/<slug>/sources/credits.md
videos/<slug>/assets/scene-XX/candidates/
videos/<slug>/assets/scene-XX/approved/
```

## Prompt: Planning-Only Asset Research Pass

Use this when you want search terms, source strategy, and risk assessment, but
do not want downloads yet.

```text
You are the Asset Researcher Agent for storyboard-video-studio.

Read:
- docs/asset-researcher-agent.md
- videos/<slug>/storyboard.md

Task:
Create a planning-only asset research pass for this video.

Deliver:
1. videos/<slug>/asset-board.csv
2. videos/<slug>/sources/source-notes.md
3. videos/<slug>/sources/credits.md

Rules:
- Do not download files yet.
- Do not render video.
- Do not rewrite the script.
- For each scene, propose 2-4 asset candidates or source strategies.
- Include search terms, preferred source types, source URLs when found, license/usage risk, and notes.
- Mark each row status as candidate, needs-review, missing, or rejected.
- Prefer stable/public sources: Wikimedia Commons, Library of Congress, official press kits, government archives, official product pages, and reputable libraries.
- If licensing is unclear, mark needs-review or high risk.

End with:
Asset Research Handoff
- Video:
- Scenes covered:
- Candidate assets:
- Needs review:
- Missing assets:
- Highest risk:
- Recommended next step:
```

## Prompt: Candidate Download Pass

Use this only after the planning pass looks useful.

```text
You are the Asset Researcher Agent for storyboard-video-studio.

Read:
- docs/asset-researcher-agent.md
- videos/<slug>/storyboard.md
- videos/<slug>/asset-board.csv

Task:
Download or save only low-risk candidate assets for each scene.

Deliver:
1. Place files under videos/<slug>/assets/scene-XX/candidates/
2. Update videos/<slug>/asset-board.csv local_path values
3. Update videos/<slug>/sources/source-notes.md
4. Update videos/<slug>/sources/credits.md

Rules:
- Do not download high-risk or unclear-license files.
- For screenshots, record capture URL, date, and reason.
- Keep filenames stable and boring:
  scene-01-asset-a-short-description.jpg
- Do not modify the video template or render.
- If a scene has no safe asset, mark it missing and explain the replacement strategy.
```

## Prompt: Approval Cleanup Pass

Use this after a human or lead agent chooses which candidates are usable.

```text
You are the Asset Researcher Agent for storyboard-video-studio.

Read:
- docs/asset-researcher-agent.md
- videos/<slug>/asset-board.csv
- videos/<slug>/sources/source-notes.md

Task:
Clean up the asset folder after approval decisions.

Deliver:
1. Move approved files into videos/<slug>/assets/scene-XX/approved/
2. Update asset-board.csv status and local_path
3. Move rejected notes into videos/<slug>/sources/rejected-assets.md
4. Ensure credits.md contains every approved asset that requires credit

Rules:
- Do not delete candidates unless explicitly told.
- Do not render video.
- Do not change the storyboard.
```

## Codex CLI Pattern

From the repo root:

```powershell
cd C:\Workspace\Repos\storyboard-video-studio
codex "You are the Asset Researcher Agent. Follow docs/asset-researcher-runbook.md and run the Planning-Only Asset Research Pass for videos/<slug>/storyboard.md."
```

## Hermes HTTP/Command Pattern

Use the same prompt body with Hermes or a Hermes command wrapper. The important
part is that the agent is pointed at:

```text
C:\Workspace\Repos\storyboard-video-studio
docs/asset-researcher-agent.md
docs/asset-researcher-runbook.md
videos/<slug>/storyboard.md
```

Suggested Hermes prompt:

```text
In C:\Workspace\Repos\storyboard-video-studio, run the Asset Researcher planning-only pass.

Follow:
- docs/asset-researcher-agent.md
- docs/asset-researcher-runbook.md

Input:
- videos/<slug>/storyboard.md

Output only the requested files. Do not render, download, or rewrite the script.
```

## Open Design Hand-Off Prompt

Use this after the Asset Researcher has created `asset-board.csv`.

```text
Use this storyboard and asset board to recommend an Open Design video template lane.

Inputs:
- videos/<slug>/storyboard.md
- videos/<slug>/asset-board.csv
- docs/template-discovery-plan.md

Task:
Recommend 2-3 Open Design templates or skills that fit the assets and pacing.

Do not generate the final video yet. Produce:
- recommended template lane
- why it fits
- risks with the current assets
- what sample scene should be generated first
```
