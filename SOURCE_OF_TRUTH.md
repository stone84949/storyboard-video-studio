# Source of Truth

Last audited: 2026-06-28.

This repo is the canonical working copy:

```text
C:\Workspace\Repos\storyboard-video-studio
```

## Current App

Use these files as the active storyboard app:

```text
C:\Workspace\Repos\storyboard-video-studio\storyboard\index.html
C:\Workspace\Repos\storyboard-video-studio\storyboard\ultimate-workflow.js
```

Open it through the local static server:

```powershell
cd C:\Workspace\Repos\storyboard-video-studio
python -m http.server 8128 --bind 127.0.0.1 --directory storyboard
```

Then open:

```text
http://127.0.0.1:8128/
```

The repo app is newer than the one-file HTML exports and includes later fixes:

- split `index.html` plus `ultimate-workflow.js`
- `pipeline_target`
- `replacement_plan`
- import/apply JSON controls
- asset library assignment controls
- bridge compatibility changes
- cache-busted script include

## Duplicate HTML Snapshots

These six files were identical snapshots of the older one-file Ultimate Workflow
HTML. They have been moved into the repo archive:

```text
C:\Workspace\Repos\storyboard-video-studio\archive\storyboard-snapshots\2026-06-28
```

Shared SHA256:

```text
138FF2708959DCECF283B37C0FDE128D1C76D0F6916B456F6BEC87A59F4DBF0F
```

## Older Topline Snapshot

These two files were identical to each other and appear older/different from the
Ultimate Workflow version. They have been moved into the repo archive:

```text
C:\Workspace\Repos\storyboard-video-studio\archive\storyboard-snapshots\2026-06-28\vault-storyboard-topline-workflow.html
C:\Workspace\Repos\storyboard-video-studio\archive\storyboard-snapshots\2026-06-28\downloads-storyboard-topline-workflow.html
```

Shared SHA256:

```text
2F7740726F2B9006C53C6FD8C4DEED0F6113FE6E9662D08B148F2F1D21D121BB
```

Treat them as archived design references unless a specific UI idea needs to be
recovered from them.

## Exported Storyboard Bundles

These are exported storyboard data, not app source code. They have been moved
into the repo archive:

```text
C:\Workspace\Repos\storyboard-video-studio\archive\storyboard-snapshots\2026-06-28\downloads-storyboard-ultimate-001-bundle-publish.json
C:\Workspace\Repos\storyboard-video-studio\archive\storyboard-snapshots\2026-06-28\downloads-storyboard-ultimate-001-bundle-plan.json
```

The non-`(1)` bundle says `workflow_stage: "publish"`.
The `(1)` bundle says `workflow_stage: "plan"` despite being newer on disk.
Do not use filename timestamp alone to decide which exported storyboard is more
advanced.

## Rule Going Forward

- Edit app code only in `C:\Workspace\Repos\storyboard-video-studio`.
- Treat Downloads and `.hermes/desktop-attachments` files as imports/archives.
- If a downloaded HTML looks newer, compare it against this note before replacing
  anything in the repo.
- When a useful external snapshot is imported, record it here and update
  `activity.md`.
