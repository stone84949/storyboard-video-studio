# Narration Audio (Phase 3) — Design

Date: 2026-07-01
Status: Approved by owner for autonomous build (owner away; decisions documented here for review)
Depends on: Phase 1 (review-before-render gate) + Phase 2 (find-images panel)

## Problem

The pipeline produces a finished *visual* vertical video, but it is **silent**. To
post, the owner still has to add narration by hand in an editor. That's the last
gap between "renders" and "post-ready."

Each scene already stores a `narration` line (written during storyboarding), and
scene `start`/`duration` times are computed. So the video already knows what
should be said and when.

## Goal

Automatically turn each scene's `narration` text into spoken audio and mux it
onto the rendered video, timed to the scene, so `final.mp4` comes out **with a
voice track** — no editor step.

## Design decisions (owner was away; these are the choices made)

- **TTS engine: HyperFrames `tts` (Kokoro-82M), local, no API key.** Confirmed
  working on this machine (`kokoro-onnx` + `soundfile` installed; produced clean
  24 kHz WAV). This keeps Phase 3 key-free like the Generate default and reuses
  the render engine's own tooling.
- **Voice: default `bm_george`** (British male, documentary tone); configurable
  via a `--voice` flag / env. Other Kokoro voices available (af_heart, am_michael,
  etc.).
- **Timing: each scene's narration starts at that scene's `start` time.** The
  storyboard durations already have headroom over narration length (e.g. Hegra:
  14–16 s scenes vs ~5–9 s of speech), so lines sit inside their scene without
  overlap. No time-stretching in v1.
- **Music: OUT of scope (Phase 3b).** Background music needs a source/licensing
  choice that's the owner's call. Phase 3 core is narration only.
- **Muxing: ffmpeg** (already installed). Keep the proven silent render as
  `exports/final-silent.mp4`; write the narrated version to `exports/final.mp4`.
- **Graceful + logged, never breaks the render.** If no scene has narration, or
  TTS/ffmpeg fails, keep the silent `final.mp4`, log the reason to
  `logs/narration.log`, and exit 0 so the render still "succeeds."
- **Runs as part of the render action**, after render, so the narrated video is
  the natural output of the existing approve→render gate. Honors the same
  `STORYBOARD_BRIDGE_LIVE` gate (it's inside the render action).

## Architecture

### New script: `scripts/add_narration.py`

CLI: `python scripts/add_narration.py <job_dir>/project.json [--voice bm_george] [--speed 1.0]`

Steps:
1. Read `project.json`; collect scenes with non-empty `narration` and their
   `start` times (fall back to cumulative durations if `start` missing).
2. For each such scene, run `npx --yes hyperframes tts "<narration>" -o
   <job>/audio/narration/<idx>-<scene_id>.wav -v <voice> -s <speed>`.
3. Build one ffmpeg `filter_complex` that `adelay`s each scene wav to
   `round(start*1000)` ms and `amix`es them (`normalize=0`), then muxes onto
   `exports/final.mp4`:
   - `-map 0:v -c:v copy` (no video re-encode — fast, lossless),
   - `-map "[a]" -c:a aac -shortest` (trim audio to video length).
   - Output to a temp file, then move: silent `final.mp4` → `final-silent.mp4`,
     narrated temp → `final.mp4`.
4. Write `exports/narration-summary.json` (`{ok, voice, scenes_voiced, output}`)
   and append to `logs/narration.log`.
5. On any failure after render exists: log, leave `final.mp4` (silent) in place,
   exit 0.

Pure, unit-testable helpers (no subprocess) so tests don't hit TTS/ffmpeg:
- `collect_narration(project) -> [{scene_id, index, text, start_ms}]`
- `build_ffmpeg_filter(items) -> str` (the `adelay/amix` filter_complex string)
- `build_ffmpeg_command(video, wavs, filter, out) -> list[str]`

### Bridge wiring (`scripts/bridge_server.py`)

- Add `NARRATION_CMD = "python scripts/add_narration.py {job_dir}/project.json --voice {voice}"`.
- Add `build_narration_command(job_dir, voice="bm_george") -> str`.
- In `run_render_job`, append narration to the render chain for the HyperFrames /
  Remotion engines (not montage): command becomes
  `materialize && render && add_narration`. Montage (editor handoff) is unchanged.
- Because `add_narration.py` exits 0 on failure, a TTS/ffmpeg problem never fails
  the render; the operator still gets the silent video plus a logged reason.

### UI (optional, minimal)

No required UI change for v1 — narration happens automatically on render. A later
enhancement could add a voice picker; not needed to be "post-ready."

## Error handling

- Missing `kokoro-onnx` → `hyperframes tts` prints an install hint; `add_narration`
  catches the non-zero exit, logs it, keeps the silent video, exits 0.
- A scene whose TTS fails → skip that scene's audio, still mux the rest.
- ffmpeg failure → keep silent `final.mp4`, log, exit 0.
- No narration anywhere → write summary `{ok:true, scenes_voiced:0}`, leave silent
  video, exit 0.

## Testing

- **Unit** (`tests/test_add_narration.py`, unittest): `collect_narration` (skips
  empty, computes start_ms, falls back to cumulative durations),
  `build_ffmpeg_filter` (correct `adelay=<ms>` + `amix=inputs=N:normalize=0`),
  `build_ffmpeg_command` (maps, `-c:v copy`, `-shortest`). No subprocess.
- **Bridge unit** (extend `tests/test_bridge_workflow.py`): `build_narration_command`
  shape; `run_render_job` render chain includes `add_narration.py` for hyperframes.
- **Live smoke** (controller): run `add_narration.py` on the Hegra job → `final.mp4`
  gains an AAC audio stream (~video length); `ffprobe` confirms; keep
  `final-silent.mp4`.

## Required configuration

- Python packages `kokoro-onnx` + `soundfile` (installed on this machine). Document
  in NEXT_ACTIONS / a note so CyberPower installs them (`pip install kokoro-onnx
  soundfile`). First `hyperframes tts` run downloads the Kokoro model (~a few MB
  voice data) once.

## Rollout

- **Phase 3 (this)**: automatic narration muxed into the render.
- **Phase 3b (later)**: background music bed (owner picks source/licensing);
  optional voice picker in the UI; optional word-level captions (HyperFrames
  `transcribe` already exists).

## Open decisions (deferred, safe defaults chosen)

1. Voice default `bm_george` — trivially changeable later.
2. Narrated `final.mp4` replaces silent (silent kept as `final-silent.mp4`) — vs
   a separate filename. Chose replace so the gate's output is post-ready by default.
