# Background Music & Captions (Phase 3b) — Design

Date: 2026-07-01
Status: Approved for planning
Depends on: Phase 3 (narration audio, `scripts/add_narration.py`)

## Problem

The render is now narrated but has no **background music** and no **on-screen
captions**. Captions materially lift watch time on faceless short-form channels,
and a ducked music bed is the production polish these videos expect.

## Goal

Extend the post-render "finish" step (where narration already lives) to
optionally:

1. **Burn in captions** synced to the narration — **karaoke** word-highlight
   (default) or **simple** line style, or off.
2. **Mix a ducked background-music bed** from a local `music/` folder under the
   narration.

Both are **optional and guarded**: no music tracks → no music; captions failure
or missing whisper → fall back or skip; the render is never broken.

## Dependency reality (from `hyperframes doctor`)

- ✓ ffmpeg, ✓ Kokoro TTS (Phase 3), ✓ MusicGen deps — all present.
- ✗ whisper-cpp — needed for **word-level** timing (karaoke). A cmake build
  (https://github.com/ggml-org/whisper.cpp#building). Optional.

Design consequence:

- **Simple captions and music need NO new dependency** (text + scene timing +
  ffmpeg). Always available.
- **Karaoke captions need whisper-cpp.** When it's absent, karaoke gracefully
  **falls back to simple** captions (logged), so captions always appear.

## Design decisions

- **Captions are burned in (hardsubs).** Social feeds don't show soft subtitles
  and karaoke isn't possible with them. Burning requires a **video re-encode**
  (libx264) — slower than Phase 3's stream-copy, but only when captions are on.
- **Karaoke default, `simple`/`off` selectable.** `--captions karaoke|simple|off`.
- **Karaoke word timing comes from HyperFrames `transcribe`** (Whisper) run on the
  generated narration wavs — forced alignment of known text to audio. If
  `transcribe` returns `whisper_unavailable`, fall back to simple.
- **Simple captions need no transcription** — each scene's `narration` line is
  shown across that scene's time window (chunked to ~4–6 word cues so lines aren't
  wall-to-wall).
- **Music: a local `music/` folder** (repo root) the owner fills with
  royalty-free tracks; a per-video override `videos/<id>/music/` or `--music
  <path>` wins. Selection: explicit path → first track in per-video folder →
  random track in `music/`. Empty → no music. **Owner owns licensing.**
  (HyperFrames MusicGen is available as a future "generate a track" alternative,
  but local-folder is the chosen v1 source.)
- **Ducking:** music is looped/trimmed to the video length and **sidechain-ducked**
  by the narration (`sidechaincompress`) so it dips under speech and swells in the
  gaps, then mixed at a low base level.
- **Style (both caption modes):** centered, center-safe (bottom third above the
  safe area), large bold sans, thick outline + shadow for legibility on any image;
  karaoke highlights the active word(s). Encoded as an **ASS** subtitle (ffmpeg
  `subtitles` filter) for full styling + karaoke `\k` support.

## Architecture

Everything stays in the isolated **post-render finish** lane (extends
`scripts/add_narration.py` into the finish step; render path untouched).

### New/changed pieces

- **`scripts/lib/captions.py`** (create; pure, unit-tested):
  - `simple_cues(scenes) -> [{start_ms, end_ms, text}]` — chunk each scene's
    narration across its window (no transcription).
  - `karaoke_cues(transcript) -> [{start_ms, end_ms, words:[{t0,t1,word}]}]` —
    from `transcribe --json` word timestamps.
  - `build_ass(cues, mode, width, height, style) -> str` — the ASS document
    (styling + optional `\k` karaoke tags).
- **`scripts/lib/music.py`** (create; pure where possible):
  - `select_track(music_dirs, explicit) -> Path | None` — deterministic pick
    order; `None` when no tracks.
  - `build_audio_filter(narration_items, music_index, duck) -> str` — the
    `adelay/amix` narration mix (from Phase 3) plus, when music present,
    `aloop`+`atrim` to length and `sidechaincompress` ducking then a final mix.
- **`scripts/add_narration.py`** (extend → the finish step):
  - After building the narration wavs, optionally: transcribe (karaoke), select
    music, build the ASS, and assemble ONE ffmpeg command that mixes audio and
    (if captions on) burns the ASS with `subtitles=` while re-encoding video
    (`libx264`); captions off keeps `-c:v copy`.
  - Keep the Phase 3 guarantees: idempotent (narrate/finish from the silent
    master, preserve `final-silent.mp4`), exit 0 + keep prior output on any
    failure.
- **`scripts/bridge_server.py`**: thread `--captions` (default `karaoke`) and
  `--music` through `NARRATION_CMD`/`build_narration_command` (allowlist-validated
  like `--voice`).

### Data flow

```
(render → silent final.mp4)  →  finish step:
   TTS per scene (Phase 3)
   → [karaoke] transcribe wavs → word cues   |  [simple] cues from scene text
   → build ASS (styled, center-safe)
   → select music track (or none)
   → ffmpeg: mix narration (+ ducked music) ; burn ASS if captions on
   → final.mp4 (with voice, music, captions) ; final-silent.mp4 preserved
```

## Error handling

- No music tracks → skip music, mix narration only.
- `--captions karaoke` but whisper unavailable → fall back to `simple` (log).
- transcribe/ASS/ffmpeg failure → keep the previous best `final.mp4`, log, exit 0.
- Captions off AND no music → identical to Phase 3 (stream-copy narration only).

## Testing

- **Unit** (`tests/test_captions.py`): `simple_cues` (chunking, windows, skips
  empties), `karaoke_cues` (word grouping from a sample transcribe JSON),
  `build_ass` (has `[Script Info]`/`Dialogue`, center style, `\k` in karaoke,
  none in simple).
- **Unit** (`tests/test_music.py`): `select_track` order (explicit > per-video >
  random-from-root > None); `build_audio_filter` includes `sidechaincompress`
  when music present, omits it when not.
- **Bridge unit**: `build_narration_command` passes/validates `--captions` and
  `--music`.
- **Live smoke**: simple captions burned onto the Hegra video (ffprobe shows
  re-encoded video; visual check); music mix with a test track (MusicGen-generated
  for the demo, since the folder is empty) shows ducking; karaoke once whisper-cpp
  is built.

## Required configuration

- Captions (simple) + music: none beyond Phase 3.
- Karaoke: build **whisper-cpp** (cmake). Document in NEXT_ACTIONS; `--optional`
  transcribe means its absence just yields simple captions.
- Music: drop royalty-free tracks into `music/` (gitignored). CyberPower same.

## Rollout / phasing (build order)

1. **Music** (ffmpeg duck/mix; no dependency).
2. **Simple captions** (no dependency; always-works caption floor).
3. **Karaoke captions** (whisper-cpp; enhancement with simple fallback).

Each step leaves the finish step working and guarded.

## Open decisions (safe defaults chosen)

1. Caption default = `karaoke` with automatic `simple` fallback when whisper is
   absent.
2. Music base level / duck amount — start at music ≈ -18 dB with
   `sidechaincompress` threshold tuned so speech clearly wins; expose as constants.
3. `music/` at repo root (gitignored) with optional per-video override.
