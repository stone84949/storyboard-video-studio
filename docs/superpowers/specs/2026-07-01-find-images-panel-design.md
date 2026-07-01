# Find-Images Panel (Phase 2) — Design

Date: 2026-07-01
Status: Approved for planning
Depends on: the review-before-render gate (Phase 1, branch `feature/review-before-render-gate`)

## Problem

Phase 1 lets the operator review generated scene images and swap the bad ones —
but swapping still means *leaving the app* to hunt for a photo and drag it in.
Finding good images was the operator's original #1 pain. Generation works, but
its prompt is auto-derived from scene text, so scenes with similar text produce
similar images and there's no way to steer it.

## Goal

An in-app **Find images** panel, per scene, with three sources the operator
chooses between depending on the scene:

- **Generate** — an editable prompt (pre-filled from the scene) + a Regenerate
  button, so the operator can steer the AI and get variations. Best for scenes
  that explain a concept with no real photo.
- **Stock** — search free stock libraries (Pexels). Best for common subjects
  (cities, nature, people).
- **Web** — search the open web for real photos (Google Custom Search image
  results). Best for accuracy on specific/obscure real places.

Every source funnels into the **same Phase 1 gate**: a chosen image drops into
the scene as `needs-review`; the operator approves; render is unlocked only when
all scenes are approved.

## Non-Goals

- Video clips / GIFs (still images only; deferred).
- Audio (Phase 3).
- Bulk "find images for every scene at once" — the panel is per-scene.
- Storing/curating a searchable library of past picks beyond the current job.

## Design principle: isolation

Each source is an independent bridge endpoint. A missing key or a flaky provider
in one source must never break the others or the gate. Build order is by
reliability so the tool stays stable at every step:

1. **Generate + Regenerate** (backend already proven via flux) — lowest risk.
2. **Stock** (Pexels, free key).
3. **Web** (Google Custom Search, key + engine id) — most fragile, built last
   and isolated.

## Current architecture this builds on

- Bridge `scripts/bridge_server.py`: serves the UI's job/asset routes; already
  has `POST /api/asset-upload` (saves an image, returns `{abs, url}`) and the
  Phase 1 materialize/render actions.
- `scripts/materialize_assets.py`: already contains provider plumbing —
  `choose_provider(preferred)`, `run_openmontage_provider(provider, prompt,
  output_path, aspect_ratio)`, `run_opendesign_provider(...)`, and
  `scene_prompt(scene, style)`. The generate endpoint reuses these rather than
  duplicating provider logic.
- `storyboard/review-gate.js`: pure review-state module; the panel reuses
  `resetOnSwap` so a chosen/generated image returns the scene to `needs-review`.
- Assign mechanism: a scene carries `assetUrl` (used for render) and a transient
  `previewUrl` (browser display), exactly as `uploadImageToScene` already does.

## To-be architecture

### Bridge endpoints (each isolated, each key-guarded)

- **`POST /api/generate-image`** → body `{prompt, aspect_ratio?}`. Calls
  `choose_provider("auto")` + `run_openmontage_provider`/`run_opendesign_provider`
  (imported from `materialize_assets`) to render ONE image into a per-session
  library folder under `bridge-jobs/_library/<timestamp-slug>/`. Returns
  `{ok, abs, url, provider}` where `url` is a `/jobs/_library/...` browser URL
  (served by the existing job static route) and `abs` is the local path for
  render fidelity. On provider failure/missing key: `{ok:false, error}` (HTTP
  400) with a human message; never writes a placeholder here (the operator asked
  for a real image — a failure should say so, not silently substitute).
- **`GET /api/search-stock?q=...&per_page=15`** → calls the Pexels photo search
  API with `PEXELS_API_KEY`. Returns `{ok, results:[{thumb, full, source_url,
  credit}]}`. Missing key → `{ok:false, error:"set PEXELS_API_KEY", need_key:
  "PEXELS_API_KEY"}`.
- **`GET /api/search-web?q=...&num=10`** → calls Google Custom Search JSON API
  (`searchType=image`) with `GOOGLE_CSE_KEY` + `GOOGLE_CSE_ID`. Returns the same
  `{ok, results:[{thumb, full, source_url, credit}]}` shape. Missing key(s) →
  `{ok:false, error, need_key}`.

All three return the **same result shape** so the UI grid is source-agnostic.
Network calls use stdlib `urllib` with a short timeout and are wrapped so a
provider error becomes a clean `{ok:false, error}` rather than a 500.

### Pure logic module (`storyboard/find-images.js`, UMD, Node-tested)

- `parseResults(source, raw)` → normalizes each source's response into
  `[{thumb, full, source_url, credit}]` (defensive against missing fields).
- `assignPick(scene, pick, source, bridgeBase)` → returns a scene copy with:
  - for **generate**: `assetUrl = pick.abs` (local path, render fidelity),
    `previewUrl = bridgeBase + pick.url`.
  - for **stock/web**: `assetUrl = pick.full` (the external URL — render
    downloads it, which is correct for a genuine external image),
    `previewUrl = pick.full`.
  - `reviewState = 'needs-review'` (via `resetOnSwap` semantics).
- `defaultQueryForScene(scene)` → builds the initial search/prompt string from
  the scene's title/notes/narration (same inputs `scene_prompt` uses).

### Panel UI (`storyboard/index.html` + `ultimate-workflow.js`)

- A **Find images** button on the scene inspector opens a panel (a section or
  modal) with three tabs: Generate / Stock / Web.
- Shared parts: a text box pre-filled via `defaultQueryForScene`, a submit
  button, a results grid, and a status line.
- **Generate tab**: box is the prompt; submit = Generate; a Regenerate button
  re-runs with the same prompt for a fresh variation. Each result appears in the
  grid; clicking assigns via `assignPick(..., 'generate', ...)`.
- **Stock / Web tabs**: box is a search query; submit fetches results; clicking
  a thumbnail assigns via `assignPick(..., 'stock'|'web', ...)`.
- After any assign: `renderAll()` re-runs, the scene shows `needs-review`, and
  the Phase 1 render lock re-evaluates.
- If an endpoint returns `need_key`, the tab shows a plain "Add `<KEY>` to enable
  this source" message and stays disabled; the other tabs keep working.

## Error handling

- Missing/invalid keys → per-tab message, no crash, other tabs unaffected.
- Provider/network failure → the tab shows the error string from the bridge;
  the operator can retry, switch tabs, or drag-drop as before.
- Generate failure does NOT fall back to a placeholder image (unlike the render
  materializer) — a "find me an image" action that failed must say so.
- All bridge endpoints return `{ok:false, error}` + HTTP 400 on failure, matching
  the existing bridge convention.

## Testing

- **Pure module** (`tests/find_images.test.js`, Node): `parseResults` for each
  source shape (including malformed/empty), `assignPick` for generate vs
  stock/web (correct assetUrl/previewUrl + `needs-review`), `defaultQueryForScene`.
- **Bridge** (`tests/test_find_images.py`, unittest): each endpoint with the
  provider/HTTP call mocked — success returns normalized results; missing key
  returns `need_key`; provider error returns `{ok:false}`. No test hits a real
  external API.
- **Manual live smoke** per source as its key becomes available: search returns a
  grid, a pick lands in the scene as `needs-review`, approve → render uses it.

## Required configuration (env)

- Generate: existing flux/provider setup (already working).
- Stock: `PEXELS_API_KEY` (free signup at pexels.com/api).
- Web: `GOOGLE_CSE_KEY` (Google Cloud API key) + `GOOGLE_CSE_ID` (Programmable
  Search Engine id, image search enabled).

Keys are read from the environment / the existing `.env` load; absence degrades
one tab gracefully, never blocks the app.

## Rollout

- **2a**: Find-images panel shell + Generate/Regenerate (reuses flux). Shippable.
- **2b**: Stock tab (Pexels).
- **2c**: Web tab (Google Custom Search).
Each sub-phase leaves the app fully working.

## Open decisions for planning

1. Library folder location for generated picks: `bridge-jobs/_library/...` served
   by the existing `/jobs/` route (chosen) vs a new `videos/_library` under the
   `/assets/` route. Confirm the `/jobs/` route resolves a `_library` sibling of
   real jobs without collision.
2. Panel as an inline section vs a modal overlay — a UI detail for the plan.
