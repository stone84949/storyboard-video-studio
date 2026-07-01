# Review-Before-Render Gate — Design

Date: 2026-07-01
Status: Approved for planning
Owner: storyboard-video-studio

## Problem

The studio already generates scene images (via `flux` through the OpenMontage
provider) and renders a valid vertical H.264 video end-to-end. Proven output:
`bridge-jobs/20260630-081334-fwh-04-kaharumi-death-square/exports/final.mp4`
(1080x1920, 30fps, 2m07s, images `status: generated / provider: flux`).

The gap is control, not capability. Today the pipeline runs
`materialize && render` as a single chained command
([bridge_server.py:139](../../../scripts/bridge_server.py)), so the operator
never sees the generated images before ~2 minutes of render is committed. When a
story depends on the *real* look of a specific place (e.g. an obscure
archaeological site), auto-generated images drift into inaccurate/far-fetched
territory and the video is unusable — which is the owner's core, long-standing
pain: bad images force manual re-edits.

## Goal

Insert a human review checkpoint between image generation and render:

```
Build storyboard → GENERATE images → 🛑 REVIEW BOARD → approve / swap each → RENDER (locked until all approved) → final.mp4
```

The operator sees every scene's actual image, approves the good ones, and swaps
the bad ones for a real photo (drag-drop a file, or paste an image URL) before
any render happens.

## Non-Goals (explicitly deferred)

- **In-app image search / one-click regenerate** — Phase 2. Phase 1 swaps use
  the existing drag-drop and URL-paste paths.
- **Audio (narration / music / SFX) in the final MP4** — Phase 3. The rendered
  video remains silent for now.
- **Video clips / GIFs playing in-scene** — later. Phase 1 is stills only, with
  the existing Ken Burns motion.
- **Touching the render engine or the generation providers** — both work; this
  design only adds a pause between them and a review surface.

## Current Architecture (as-is)

- **UI**: `storyboard/index.html` + `storyboard/ultimate-workflow.js` — scene
  cards (draggable reorder), a large preview, an inspector with an `Asset URL`
  field, `Ready / Approve / Flag` buttons, drag-drop image upload, and
  `Send to bridge` / `Send + execute`.
- **Bridge**: `scripts/bridge_server.py`
  - `POST /api/launch` — creates a job folder and (if `execute:true` **and**
    `STORYBOARD_BRIDGE_LIVE=1`) runs the chained `materialize && render` command.
  - `POST /api/asset-upload` — saves an uploaded image under
    `videos/<project_id>/assets/images/uploads/` and returns a `/assets/...` URL.
  - `GET /api/health`, `GET /api/status` — list recent jobs.
  - `GET /assets/<project>/...` — static file serving rooted at `videos/`
    (path-traversal guarded).
- **Materialize**: `scripts/materialize_assets.py` — for each scene, downloads a
  remote URL, copies a local file, or generates via provider (`flux`/`openai`/
  `google_imagen`/`grok`/`opendesign`), else writes fallback SVG. Writes images
  to `bridge-jobs/<job>/assets/images/materialized/` and rewrites `project.json`
  scene assets to those local paths. **Idempotent**: an already-materialized
  local asset is copied, not regenerated.
- **Render**: `scripts/render_hyperframes_job.py` — builds a HyperFrames
  workspace from `project.json` and writes `exports/final.mp4`.

### Two blocking gaps for a review board

1. **Materialize and render are one command.** They must become two separately
   triggerable actions.
2. **Generated images live under `bridge-jobs/`, but `/assets/` only serves from
   `videos/`.** The browser currently cannot display materialized images. A job
   read + a job-scoped static route are required.

## Design (to-be)

### Data flow

```
1. UI: operator builds/imports storyboard, clicks "Generate images"
2. Bridge: create job folder + run materialize ONLY (provider auto → flux)
   → returns { job_id, scenes: [{ scene_id, image_url, status }] }
3. UI: Review Board loads each scene image (served from the job folder)
   → each scene = needs-review; operator Approves or Swaps
      - Swap by drag-drop  → POST /api/asset-upload → new image_url
      - Swap by URL paste  → scene.asset = pasted URL
4. Render button unlocks only when every scene is Approved
5. UI: clicks "Render" → sends reviewed payload for that job_id
6. Bridge: writes reviewed scenes into the job's project.json,
   re-runs materialize (idempotent: only fetches newly-swapped assets),
   then runs render → exports/final.mp4
7. UI: shows a link / status for the finished video
```

Re-running materialize at step 6 is safe: approved scenes already hold local
materialized paths and are copied, not regenerated; only newly swapped
URLs/uploads are fetched.

### Bridge changes (`scripts/bridge_server.py`)

- **Split the command builder** so `materialize` and `render` can run
  independently. Introduce an `action` on `POST /api/launch` (or dedicated
  endpoints — decide in planning):
  - `action: "materialize"` → create/locate job, run `MATERIALIZE_CMD` only,
    return per-scene image URLs + statuses from `exports/asset-manifest.json`.
  - `action: "render"` → locate existing job by `job_id`, write the reviewed
    payload into `project.json`, run `MATERIALIZE_CMD` (idempotent) then the
    engine `RENDER_*_CMD`.
  - No `action` → preserve current combined behavior (back-compat).
- **Add `GET /api/job?id=<job_id>`** — return the job's `project.json` payload
  and `asset-manifest.json` (scene → local image path + status) so the UI can
  rebuild the Review Board for an existing job.
- **Add a job-scoped static route** `GET /jobs/<job_id>/...` rooted at
  `bridge-jobs/` with the same path-traversal guard as `resolve_served_asset`,
  so materialized images render in the browser. (Alternatively extend `/assets/`
  to also resolve job dirs — decide in planning; a separate route is cleaner.)
- **Keep the live-execution gate** (`STORYBOARD_BRIDGE_LIVE=1`) for both actions.

### UI changes (`storyboard/index.html`, `storyboard/ultimate-workflow.js`)

- **"Generate images" button**: sends the current storyboard with
  `action: materialize`. On response, populate each scene card with its returned
  `image_url` and set state `needs-review`.
- **Review Board state per scene**: `needs-review` → `approved` | `flagged`.
  Reuse existing `Approve` / `Flag` controls; track a per-scene `reviewApproved`
  boolean in `state`. Show a visible badge and a large-enough image to judge.
- **Swap paths** (already built, wire into the board): drag-drop a file
  (`/api/asset-upload`) and paste into the `Asset URL` field. A swapped scene
  returns to `needs-review` until re-approved.
- **Render button**: disabled with a clear reason until every scene is
  `approved`; on click, sends `action: render` with `job_id` + the reviewed
  payload. Surface the resulting `final.mp4` path/link and any render error.

### Error handling

- Materialize/generation failure for a scene → the manifest already records a
  `status` and `notes`; surface that on the scene card as an error state the
  operator can resolve by swapping. Never leave the board blank/ambiguous.
- Missing `PEXELS_/provider` keys are irrelevant to Phase 1 (swaps are
  drag-drop/URL). Provider failures fall back to the existing SVG placeholder,
  which the operator will see and can replace.
- Render errors → show `execution.returncode` + stderr tail from the bridge
  response; keep the job folder for inspection (unchanged behavior).
- All bridge failures continue to return `{ ok: false, error }` with HTTP 400 so
  the UI can display them (existing pattern).

### Testing

Follow the existing separate test layout and fast-contract style:

- **Bridge unit tests**: `action: materialize` runs materialize only (mock
  subprocess) and returns scene image URLs; `action: render` writes the reviewed
  payload into `project.json` before rendering; `GET /api/job` returns payload +
  manifest; `/jobs/<job_id>/...` serves a file and blocks path traversal.
- **UI contract test**: generating populates review state; Render stays locked
  until all scenes approved; a swap resets a scene to `needs-review`.
- **Manual live smoke** (with `STORYBOARD_BRIDGE_LIVE=1`): generate → swap one
  scene with a real image → render → confirm `final.mp4` uses the swapped image
  (verify via `ffprobe` + a proof frame).

## Rollout / phasing

- **Phase 1 (this spec)**: the gate — split pipeline, job read + job static
  route, Review Board, approval-locked render.
- **Phase 2**: in-app image search (web/stock) + one-click regenerate per scene,
  to remove manual image hunting.
- **Phase 3**: audio track (narration/music) muxed into `final.mp4` for true
  post-ready output.

## Open decisions for planning

1. `action` on `/api/launch` vs. dedicated `/api/materialize` + `/api/render`
   endpoints.
2. Separate `/jobs/<job_id>/...` static route vs. extending `/assets/`.
3. Whether `action: render` enforces "all approved" server-side or trusts the UI
   (client-side lock) plus the existing live gate.
