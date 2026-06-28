# Agent Workflow

This project should use narrow agents with file-based handoffs.

## Recommended Roles

1. Producer / Storyboard Agent
   - creates the concept, angle, outline, and scene storyboard
   - owns `storyboard.md`

2. Asset Researcher Agent
   - finds and organizes real images, clips, screenshots, articles, and source material
   - owns `asset-board.csv` and `sources/`
   - see [asset-researcher-agent.md](asset-researcher-agent.md)

3. Open Design / Template Agent
   - browses Open Design templates and recommends the best visual lane
   - owns template notes and sample artifacts

4. Assembler Agent
   - turns storyboard plus approved assets into a video folder
   - owns generated HyperFrames or renderer-ready files

5. Verifier Agent
   - checks source risk, visual quality, credits, render output, and missing assets
   - owns QA notes

## Where To Run Agents

Use Codex from here for:

- creating repo structure
- writing contracts and templates
- building scripts
- verifying files
- committing changes

Use Hermes/CLI for:

- running repeatable producer/researcher workflows
- calling Open Design HTTP automation
- coordinating multiple agents over the same file contract
- using repo wrappers such as `scripts/hermes-producer-brief.ps1`,
  `scripts/hermes-asset-research-plan.ps1`, and
  `scripts/hermes-open-design-template-review.ps1`

Use Open Design for:

- browsing templates
- generating sample visual directions
- testing style lanes
- inspecting design systems

## First Practical Automation

Start with a CLI command or prompt that runs only the Asset Researcher role:

```text
You are the Asset Researcher Agent for storyboard-video-studio.

Input:
- videos/<slug>/storyboard.md

Output:
- videos/<slug>/asset-board.csv
- videos/<slug>/sources/source-notes.md
- videos/<slug>/sources/credits.md
- organized scene folders under videos/<slug>/assets/

Follow docs/asset-researcher-agent.md.
Do not write the script, edit the template, or render the video.
```

This is a good early test because it targets the old pipeline's weak point:
using real internet images safely and coherently.

Ready-to-use prompts and command patterns live in
[asset-researcher-runbook.md](asset-researcher-runbook.md).
