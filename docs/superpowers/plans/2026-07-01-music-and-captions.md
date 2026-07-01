# Background Music & Captions (Phase 3b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the post-render finish step to optionally burn in captions (karaoke or simple) and mix a ducked background-music bed under the narration.

**Architecture:** Two pure, unit-tested helper modules (`scripts/captions.py`, `scripts/music.py`) build ASS subtitles and ffmpeg audio filters; `scripts/add_narration.py` (the finish step) orchestrates transcribe → music selection → ASS → one ffmpeg command that mixes audio and burns captions (re-encode only when captions on). Everything stays in the isolated post-render lane; the render path is untouched.

**Tech Stack:** Python stdlib, ffmpeg (audio mix + `sidechaincompress` ducking + `subtitles` burn), HyperFrames `transcribe` (Whisper, karaoke word timing — optional), ASS subtitle format.

## Global Constraints

- Platform Windows; Python stdlib only in the scripts. ffmpeg + Node/npx already present.
- **Never break the render.** No music → skip music; captions failure or whisper absent → fall back to simple / skip captions; exit 0 and keep the prior best `final.mp4`. (Inherited from Phase 3.)
- **Idempotent.** Finish reads from the true silent master (`final-silent.mp4`) when it exists and never overwrites it. (Inherited from Phase 3 `add_narration.py`.)
- Captions are **burned in (hardsubs)**; captions ON ⇒ video re-encode (`-c:v libx264`), captions OFF ⇒ `-c:v copy`.
- Caption modes: `karaoke` (default) | `simple` | `off`. `karaoke` requires whisper-cpp; when unavailable it **falls back to `simple`** (logged).
- Music source: `--music <path>` wins, else first track in `videos/<id>/music/`, else a random track in repo-root `music/`; none → no music. Owner owns licensing.
- Bridge-passed `--captions`/`--music`/`--voice` values are allowlist-validated before the `shell=True` render chain.
- ffmpeg `subtitles` filter path is Windows-hostile: run ffmpeg with `cwd = exports_dir` and reference the ASS by **basename** (`subtitles=finish.ass`); inputs/output use absolute paths.

---

## File Structure

- `scripts/music.py` (create) — track selection + the audio filter_complex (narration mix + optional ducked music). Pure/testable.
- `scripts/captions.py` (create) — cue building (simple from scene text; karaoke from transcribe JSON) + ASS document generation. Pure/testable.
- `scripts/add_narration.py` (modify) — the finish orchestrator: import the two modules, add transcribe + music + ASS + the combined ffmpeg command; keep Phase 3 guards.
- `scripts/bridge_server.py` (modify) — thread `--captions` (default karaoke) and `--music` through `NARRATION_CMD`/`build_narration_command`, allowlist-validated.
- `tests/test_music.py`, `tests/test_captions.py` (create); extend `tests/test_add_narration.py`, `tests/test_bridge_workflow.py`.

Build order (each independently reviewable + shippable): Task 1 music.py → Task 2 wire music → Task 3 captions.py simple → Task 4 wire simple captions → Task 5 captions.py karaoke → Task 6 wire karaoke+fallback → Task 7 bridge flags.

**Import note:** `add_narration.py` must `import music, captions` as siblings. At the top of `add_narration.py` add, before those imports:
`import sys as _sys; _sys.path.insert(0, str(Path(__file__).resolve().parent))`
so it resolves both when run as a script and when a test loads it via importlib. Tests load `music.py`/`captions.py` directly via importlib (not through add_narration).

---

## Task 1: Music track selection + audio filter (`scripts/music.py`)

**Files:**
- Create: `scripts/music.py`
- Test: `tests/test_music.py`

**Interfaces:**
- Produces:
  - `list_tracks(folder) -> list[Path]` (sorted; audio extensions only; `[]` if missing)
  - `select_track(root_music, per_video_music, explicit=None, rng=random) -> Path | None`
  - `build_narration_mix(items) -> list[str]` — filter statements ending in `[narr]` (items have `start_ms`)
  - `build_audio_filter(items, has_music=False, music_input_index=None, music_volume=0.5) -> str` — full filter producing `[a]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_music.py`:

```python
from __future__ import annotations

import importlib.util
import random
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("music", REPO_ROOT / "scripts" / "music.py")
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


class SelectTrackTests(unittest.TestCase):
    def test_none_when_no_tracks(self):
        m = load()
        self.assertIsNone(m.select_track(None, None))

    def test_explicit_wins(self, ):
        m = load()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "song.mp3"
            f.write_bytes(b"x")
            self.assertEqual(m.select_track(None, None, explicit=str(f)), f)

    def test_per_video_before_root(self):
        m = load()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"; pv = Path(tmp) / "pv"
            root.mkdir(); pv.mkdir()
            (root / "r.mp3").write_bytes(b"x")
            (pv / "p.mp3").write_bytes(b"x")
            self.assertEqual(m.select_track(root, pv).name, "p.mp3")

    def test_random_from_root_is_deterministic_with_seed(self):
        m = load()
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"; root.mkdir()
            for n in ("a.mp3", "b.mp3", "c.mp3"):
                (root / n).write_bytes(b"x")
            pick = m.select_track(root, None, rng=random.Random(1))
            self.assertIn(pick.name, {"a.mp3", "b.mp3", "c.mp3"})


class AudioFilterTests(unittest.TestCase):
    def test_no_music_produces_narr_as_a(self):
        m = load()
        f = m.build_audio_filter([{"start_ms": 0}, {"start_ms": 5000}], has_music=False)
        self.assertTrue(f.endswith("[a]"))
        self.assertIn("amix=inputs=2:normalize=0", f)
        self.assertNotIn("sidechaincompress", f)

    def test_music_adds_ducking(self):
        m = load()
        f = m.build_audio_filter([{"start_ms": 0}], has_music=True, music_input_index=2)
        self.assertIn("asplit", f)
        self.assertIn("sidechaincompress", f)
        self.assertIn("[2]", f)  # the music input
        self.assertTrue(f.endswith("[a]"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_music -v`
Expected: FAIL (`No module named 'music'` via importlib / `AttributeError`).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/music.py`:

```python
"""Background-music selection and the narration+music ffmpeg audio filter."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def list_tracks(folder) -> list[Path]:
    if not folder:
        return []
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXTS)


def select_track(root_music, per_video_music, explicit=None, rng=random) -> Path | None:
    if explicit:
        e = Path(explicit)
        if e.is_file():
            return e
    per_video = list_tracks(per_video_music)
    if per_video:
        return per_video[0]
    root = list_tracks(root_music)
    if root:
        return rng.choice(root)
    return None


def build_narration_mix(items: list[dict[str, Any]]) -> list[str]:
    """Filter statements that delay each voice input to its start and mix to [narr]."""
    parts: list[str] = []
    labels: list[str] = []
    for pos, item in enumerate(items):
        idx = pos + 1
        lab = f"n{idx}"
        parts.append(f"[{idx}]adelay={item['start_ms']}:all=1[{lab}]")
        labels.append(f"[{lab}]")
    if len(labels) == 1:
        parts.append(f"{labels[0]}apad[narr]")
    else:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad[narr]")
    return parts


def build_audio_filter(items, has_music=False, music_input_index=None, music_volume=0.5) -> str:
    parts = build_narration_mix(items)
    if not has_music:
        parts[-1] = parts[-1][:-len("[narr]")] + "[a]"
        return ";".join(parts)
    parts.append("[narr]asplit[narrmix][narrkey]")
    parts.append(f"[{music_input_index}]volume={music_volume}[bg]")
    parts.append("[bg][narrkey]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[bgduck]")
    parts.append("[narrmix][bgduck]amix=inputs=2:normalize=0:dropout_transition=0[a]")
    return ";".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_music -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/music.py tests/test_music.py
git commit -m "feat: music track selection and narration+ducked-music audio filter"
```

---

## Task 2: Wire music into the finish step

**Files:**
- Modify: `scripts/add_narration.py`
- Test: manual live smoke (a generated test track) + existing unit tests still green

**Interfaces:**
- Consumes: `music.build_audio_filter`, `music.select_track` (Task 1).
- Produces: `add_narration.add_narration(project_path, voice, speed, music=None)` now mixes a ducked music bed when a track is found; `build_ffmpeg_command` gains a `music` input.

- [ ] **Step 1: Add the sibling-import shim and imports**

At the top of `scripts/add_narration.py`, after the existing imports, add:

```python
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import music as music_lib  # noqa: E402
```

- [ ] **Step 2: Replace the audio filter + command build to include music**

In `add_narration`, replace the filter/command section (currently
`filt = build_ffmpeg_filter(voiced)` … `cmd = build_ffmpeg_command(source_video, wavs, filt, narrated_tmp)`) with music-aware assembly:

```python
        root_music = REPO_ROOT / "music"
        per_video_music = job_dir / "music"
        track = music_lib.select_track(root_music, per_video_music, explicit=music)
        music_input_index = len(wavs) + 1 if track else None
        filt = music_lib.build_audio_filter(voiced, has_music=bool(track), music_input_index=music_input_index)
        narrated_tmp = exports_dir / "final-narrated.tmp.mp4"
        cmd = build_ffmpeg_command(source_video, wavs, filt, narrated_tmp, music=track)
        summary["music"] = track.name if track else ""
```

Update `build_ffmpeg_command` to accept an optional looped music input:

```python
def build_ffmpeg_command(video: Path, wavs: list[Path], filter_complex: str, output: Path, music: Path | None = None) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y", "-i", str(video)]
    for wav in wavs:
        cmd += ["-i", str(wav)]
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]  # loop the track; -shortest trims to video
    cmd += [
        "-filter_complex", filter_complex,
        "-map", "0:v", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(output),
    ]
    return cmd
```

Add `--music` to `main()`'s argparse and pass it through:

```python
    parser.add_argument("--music", default=None, help="explicit music file, else music/ folders are used")
    ...
    summary = add_narration(args.project_json, args.voice, args.speed, music=args.music)
```
and change the `add_narration` signature to `def add_narration(project_path, voice, speed, music=None):` and `summary` init to include `"music": ""`.

- [ ] **Step 3: Verify unit tests still pass**

Run: `python -m unittest tests.test_add_narration tests.test_music -v`
Expected: PASS (the no-music path is unchanged; `build_audio_filter` with no music equals the prior single/multi behavior).

- [ ] **Step 4: Live smoke (controller-run)**

Generate a short test track with HyperFrames MusicGen (folder is empty, so this proves the mix without shipping copyrighted audio), drop it in `music/`, then re-run the finish on the Hegra job and confirm the audio now has music ducked under the voice:

```bash
npx --yes hyperframes bgm "slow ominous documentary drone" -o music/test-bed.mp3 || true
python scripts/add_narration.py bridge-jobs/20260701-141153-hegra-madain-salih/project.json --voice bm_george
ffprobe -v error -show_entries stream=codec_type -of csv=p=0 bridge-jobs/20260701-141153-hegra-madain-salih/exports/final.mp4
```
Expected: audio stream present; narration audible over a quieter music bed. (If `bgm` subcommand differs, generate any short mp3 for the test.)

- [ ] **Step 5: Commit**

```bash
git add scripts/add_narration.py
git commit -m "feat: mix ducked background music into the finish step"
```

---

## Task 3: Simple captions — cues + ASS (`scripts/captions.py`)

**Files:**
- Create: `scripts/captions.py`
- Test: `tests/test_captions.py`

**Interfaces:**
- Produces:
  - `simple_cues(scenes, max_words=6) -> list[dict]` — `{start_ms, end_ms, text}` chunks from each scene's `narration` across its window; skips empty.
  - `build_ass(cues, mode, width, height) -> str` — ASS document; `mode="simple"` renders plain `Dialogue` lines.

- [ ] **Step 1: Write the failing test**

Create `tests/test_captions.py`:

```python
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("captions", REPO_ROOT / "scripts" / "captions.py")
    m = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(m)
    return m


class SimpleCuesTests(unittest.TestCase):
    def test_chunks_within_scene_window_and_skips_empty(self):
        c = load()
        scenes = [
            {"id": "s1", "narration": "one two three four five six seven eight", "start": 0, "duration": 8},
            {"id": "s2", "narration": "", "start": 8, "duration": 4},
        ]
        cues = c.simple_cues(scenes, max_words=4)
        self.assertTrue(all(cue["end_ms"] > cue["start_ms"] for cue in cues))
        self.assertEqual(cues[0]["start_ms"], 0)
        self.assertLessEqual(cues[-1]["end_ms"], 8000)  # stays inside scene 1 (scene 2 empty)
        self.assertEqual(cues[0]["text"].split(), ["one", "two", "three", "four"])


class BuildAssTests(unittest.TestCase):
    def test_simple_ass_has_header_and_dialogue_no_karaoke(self):
        c = load()
        cues = [{"start_ms": 0, "end_ms": 2000, "text": "hello world"}]
        ass = c.build_ass(cues, mode="simple", width=1080, height=1920)
        self.assertIn("[Script Info]", ass)
        self.assertIn("PlayResX: 1080", ass)
        self.assertIn("Dialogue:", ass)
        self.assertIn("hello world", ass)
        self.assertNotIn("\\k", ass)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_captions -v`
Expected: FAIL (`No module named 'captions'`).

- [ ] **Step 3: Write minimal implementation**

Create `scripts/captions.py`:

```python
"""Caption cue building (simple + karaoke) and ASS subtitle generation."""

from __future__ import annotations

from typing import Any

# Center-safe, large, bold, thick outline; alignment 2 = bottom-center, MarginV lifts
# it above the very bottom (safe area). Colours are ASS &HBBGGRR.
_STYLE = (
    "Style: Cap,Arial,96,&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,"
    "-1,0,0,0,100,100,0,0,1,6,3,2,80,80,420,1"
)
_HIGHLIGHT = "&H0030B0FF"  # karaoke fill (amber), ASS &HBBGGRR


def _ts(ms: int) -> str:
    ms = max(0, int(ms))
    h = ms // 3600000
    m = (ms % 3600000) // 60000
    s = (ms % 60000) // 1000
    cs = (ms % 1000) // 10
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _header(width: int, height: int) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"{_STYLE}\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )


def simple_cues(scenes: list[dict[str, Any]], max_words: int = 6) -> list[dict[str, Any]]:
    cues: list[dict[str, Any]] = []
    cursor = 0.0
    for index, scene in enumerate(scenes, start=1):
        duration = float(scene.get("duration") or 4)
        start = scene.get("start")
        start = float(start) if start is not None else cursor
        text = str(scene.get("narration") or scene.get("script") or "").strip()
        cursor = start + duration
        if not text:
            continue
        words = text.split()
        chunks = [words[i:i + max_words] for i in range(0, len(words), max_words)]
        span_ms = int(duration * 1000)
        each = max(1, span_ms // max(1, len(chunks)))
        base = int(start * 1000)
        for ci, chunk in enumerate(chunks):
            s = base + ci * each
            e = base + (ci + 1) * each if ci < len(chunks) - 1 else base + span_ms
            cues.append({"start_ms": s, "end_ms": e, "text": " ".join(chunk)})
    return cues


def _dialogue(start_ms: int, end_ms: int, text: str) -> str:
    return f"Dialogue: 0,{_ts(start_ms)},{_ts(end_ms)},Cap,,0,0,0,,{text}\n"


def build_ass(cues: list[dict[str, Any]], mode: str, width: int, height: int) -> str:
    body = _header(width, height)
    for cue in cues:
        if mode == "karaoke" and cue.get("words"):
            parts = []
            for w in cue["words"]:
                dur_cs = max(1, int((w["t1"] - w["t0"]) / 10))
                parts.append(f"{{\\kf{dur_cs}\\c{_HIGHLIGHT}}}{w['word']} ")
            body += _dialogue(cue["start_ms"], cue["end_ms"], "".join(parts).strip())
        else:
            body += _dialogue(cue["start_ms"], cue["end_ms"], cue["text"])
    return body
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_captions -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/captions.py tests/test_captions.py
git commit -m "feat: simple caption cues and ASS subtitle generation"
```

---

## Task 4: Burn simple captions in the finish step

**Files:**
- Modify: `scripts/add_narration.py`
- Test: extend `tests/test_add_narration.py`; live smoke

**Interfaces:**
- Consumes: `captions.simple_cues`, `captions.build_ass` (Task 3); `music.*` (Tasks 1-2).
- Produces: `add_narration(project_path, voice, speed, music=None, captions="off")`; when `captions != "off"`, writes `exports/finish.ass` and burns it (re-encode). `build_ffmpeg_command` gains `ass_name` + `reencode`.

- [ ] **Step 1: Extend `build_ffmpeg_command` for captions**

Replace `build_ffmpeg_command` with a caption-aware version. When `ass_name` is set, add a `subtitles` video filter and re-encode; else keep `-c:v copy`. The `subtitles` path is referenced by **basename** (ffmpeg is run with `cwd=exports_dir` in Step 3).

```python
def build_ffmpeg_command(video, wavs, filter_complex, output, music=None, ass_name=None):
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y", "-i", str(video)]
    for wav in wavs:
        cmd += ["-i", str(wav)]
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    if ass_name:
        fc = f"{filter_complex};[0:v]subtitles={ass_name}[v]"
        cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20"]
    else:
        cmd += ["-filter_complex", filter_complex, "-map", "0:v", "-map", "[a]", "-c:v", "copy"]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
    return cmd
```

- [ ] **Step 2: Write the ASS + call ffmpeg from exports_dir**

In `add_narration`, after selecting music and before building the command, add caption assembly (simple only for now; karaoke added in Task 6):

```python
        import captions as captions_lib
        ass_name = ""
        if captions and captions != "off":
            payload = collect_narration.__self__ if False else None  # (illustrative; use project below)
            project_payload = json.loads(project_path.read_text(encoding="utf-8"))
            sb = captions_lib_scenes(project_payload)
            cues = captions_lib.simple_cues(sb)
            if cues:
                (exports_dir / "finish.ass").write_text(
                    captions_lib.build_ass(cues, mode="simple", width=1080, height=1920), encoding="utf-8")
                ass_name = "finish.ass"
```

Add a tiny helper near the top of `add_narration.py` to reach scenes (reuse `payload_ref`):

```python
def captions_lib_scenes(project):
    return (payload_ref(project).get("scenes") or [])
```

Then build and run the command with `cwd=exports_dir` when captions are on:

```python
        cmd = build_ffmpeg_command(source_video, wavs, filt, narrated_tmp, music=track, ass_name=ass_name or None)
        run_cwd = exports_dir if ass_name else REPO_ROOT
        ...
        completed = subprocess.run(cmd, cwd=run_cwd, text=True, capture_output=True, timeout=900)
```

Note: with `cwd=exports_dir`, `narrated_tmp`/inputs use absolute paths (they already are), and only `subtitles=finish.ass` is relative — which resolves against `exports_dir`. Add `captions` to `main()` argparse (`--captions`, default `"off"` for the CLI; the bridge passes `karaoke`) and thread it into `add_narration`.

- [ ] **Step 3: Add a test that captions produce an ASS + re-encode command**

Add to `tests/test_add_narration.py`:

```python
class CaptionCommandTests(unittest.TestCase):
    def test_ass_command_reencodes_and_maps_v(self):
        an = load()
        cmd = an.build_ffmpeg_command(Path("v.mp4"), [Path("a1.wav")], "AF", Path("out.mp4"), ass_name="finish.ass")
        self.assertIn("subtitles=finish.ass", " ".join(cmd))
        self.assertIn("libx264", cmd)
        self.assertIn("[v]", cmd)

    def test_no_caption_command_copies_video(self):
        an = load()
        cmd = an.build_ffmpeg_command(Path("v.mp4"), [Path("a1.wav")], "AF", Path("out.mp4"))
        self.assertIn("copy", cmd)
        self.assertNotIn("libx264", cmd)
```

- [ ] **Step 4: Run tests + live smoke**

Run: `python -m unittest tests.test_add_narration tests.test_captions tests.test_music -v` (PASS).
Live: `python scripts/add_narration.py bridge-jobs/20260701-141153-hegra-madain-salih/project.json --voice bm_george --captions simple` then open the mp4 and confirm captions are visible and centered; `ffprobe` shows the video re-encoded (h264, still 1080x1920, ~138s).

- [ ] **Step 5: Commit**

```bash
git add scripts/add_narration.py tests/test_add_narration.py
git commit -m "feat: burn simple captions into the finish step"
```

---

## Task 5: Karaoke cues from transcribe (`scripts/captions.py`)

**Files:**
- Modify: `scripts/captions.py`
- Test: `tests/test_captions.py`

**Interfaces:**
- Produces: `karaoke_cues(transcribe_json, scene_start_ms=0) -> list[dict]` — groups whisper word timestamps into cues of `{start_ms, end_ms, words:[{t0,t1,word}]}` (times in ms, offset by `scene_start_ms`). `build_ass(..., mode="karaoke")` already renders `words` with `\kf` (Task 3).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_captions.py`:

```python
class KaraokeCuesTests(unittest.TestCase):
    def test_groups_words_and_offsets(self):
        c = load()
        tj = {"ok": True, "words": [
            {"word": "In", "start": 0.0, "end": 0.2},
            {"word": "the", "start": 0.2, "end": 0.4},
            {"word": "desert", "start": 0.4, "end": 0.9},
        ]}
        cues = c.karaoke_cues(tj, scene_start_ms=1000, max_words=2)
        self.assertEqual(cues[0]["start_ms"], 1000)
        self.assertEqual(len(cues[0]["words"]), 2)
        self.assertEqual(cues[0]["words"][0]["word"], "In")
        self.assertEqual(cues[-1]["words"][-1]["word"], "desert")
        # end of last cue reflects the last word end (0.9s) + offset
        self.assertEqual(cues[-1]["end_ms"], 1900)

    def test_empty_transcript_yields_no_cues(self):
        c = load()
        self.assertEqual(c.karaoke_cues({"ok": False, "skipped": True}, 0), [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_captions.KaraokeCuesTests -v`
Expected: FAIL (`AttributeError: karaoke_cues`).

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/captions.py`:

```python
def karaoke_cues(transcribe_json, scene_start_ms: int = 0, max_words: int = 4) -> list[dict[str, Any]]:
    if not transcribe_json or not transcribe_json.get("ok"):
        return []
    words = transcribe_json.get("words") or []
    cues: list[dict[str, Any]] = []
    for i in range(0, len(words), max_words):
        group = words[i:i + max_words]
        if not group:
            continue
        wlist = [
            {"word": str(w.get("word", "")).strip(),
             "t0": int(round(float(w.get("start", 0)) * 1000)) + scene_start_ms,
             "t1": int(round(float(w.get("end", 0)) * 1000)) + scene_start_ms}
            for w in group
        ]
        cues.append({"start_ms": wlist[0]["t0"], "end_ms": wlist[-1]["t1"], "words": wlist})
    return cues
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_captions -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/captions.py tests/test_captions.py
git commit -m "feat: karaoke caption cues from transcribe word timings"
```

---

## Task 6: Wire karaoke + whisper fallback in the finish step

**Files:**
- Modify: `scripts/add_narration.py`
- Test: extend `tests/test_add_narration.py`; live smoke (if whisper-cpp built)

**Interfaces:**
- Consumes: `captions.karaoke_cues`/`build_ass`, the per-scene wavs (already generated), HyperFrames `transcribe --json --optional`.
- Produces: when `captions == "karaoke"`, transcribe each scene wav (offset by scene start), build karaoke cues; if transcribe is unavailable (`whisper_unavailable`) for the first scene, fall back to `simple` (logged).

- [ ] **Step 1: Add a transcribe helper**

Add to `scripts/add_narration.py`:

```python
def transcribe_wav(wav: Path, log) -> dict[str, Any]:
    npx = shutil.which("npx") or "npx"
    cmd = [npx, "--yes", "hyperframes", "transcribe", str(wav), "--json", "--optional"]
    try:
        completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=300)
        log.write(completed.stderr)
        line = (completed.stdout or "").strip().splitlines()[-1] if completed.stdout.strip() else "{}"
        return json.loads(line)
    except Exception as exc:
        log.write(f"\ntranscribe error: {exc}\n")
        return {"ok": False, "skipped": True, "reason": str(exc)}
```

- [ ] **Step 2: Build karaoke cues with fallback, before writing the ASS**

Replace the caption-assembly block from Task 4 so it branches on mode. `voiced`/`wavs` from the narration loop pair each scene with its wav and `start_ms`:

```python
        ass_name = ""
        effective_mode = captions
        cues = []
        if captions == "karaoke":
            karaoke = []
            for item, wav in zip(voiced, wavs):
                tj = transcribe_wav(wav, log)
                if not tj.get("ok"):
                    effective_mode = "simple"  # whisper unavailable / failed
                    log.write("\nkaraoke unavailable; falling back to simple captions\n")
                    break
                karaoke.extend(captions_lib.karaoke_cues(tj, scene_start_ms=item["start_ms"]))
            if effective_mode == "karaoke":
                cues = karaoke
        if effective_mode == "simple" and captions != "off":
            cues = captions_lib.simple_cues(captions_lib_scenes(json.loads(project_path.read_text(encoding="utf-8"))))
        if captions != "off" and cues:
            (exports_dir / "finish.ass").write_text(
                captions_lib.build_ass(cues, mode=effective_mode, width=1080, height=1920), encoding="utf-8")
            ass_name = "finish.ass"
            summary["captions"] = effective_mode
```

(`voiced` items carry `start_ms` from `collect_narration`; each `wav` corresponds to the same index. Ensure the narration loop keeps `voiced` and `wavs` index-aligned — it already appends to both together.)

- [ ] **Step 3: Add a test for the fallback shape**

Add to `tests/test_add_narration.py` a test that `transcribe_wav` returns a dict and that a `whisper_unavailable` transcript yields no karaoke cues (via the captions module), documenting the fallback contract:

```python
class KaraokeFallbackTests(unittest.TestCase):
    def test_unavailable_transcript_has_no_karaoke_cues(self):
        import importlib.util
        from pathlib import Path as _P
        spec = importlib.util.spec_from_file_location("captions", _P(__file__).resolve().parents[1] / "scripts" / "captions.py")
        c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
        self.assertEqual(c.karaoke_cues({"ok": False, "skipped": True}, 0), [])
```

- [ ] **Step 4: Run tests + live smoke**

Run: `python -m unittest discover -s tests -p "test_*.py"` (PASS).
Live (only if whisper-cpp is built): `python scripts/add_narration.py <hegra>/project.json --voice bm_george --captions karaoke` → open the video, confirm word-by-word highlight. If whisper is absent, confirm it logs the fallback and produces simple captions instead.

- [ ] **Step 5: Commit**

```bash
git add scripts/add_narration.py tests/test_add_narration.py
git commit -m "feat: karaoke captions via transcribe with simple fallback"
```

---

## Task 7: Thread caption/music flags through the bridge

**Files:**
- Modify: `scripts/bridge_server.py`
- Test: extend `tests/test_bridge_workflow.py`

**Interfaces:**
- Consumes: `add_narration.py` CLI `--captions`/`--music`/`--voice`.
- Produces: `build_narration_command(job_dir, voice="bm_george", captions="karaoke", music="")` — allowlist-validated; render chain passes them.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_bridge_workflow.py`:

```python
    def test_narration_command_threads_and_validates_captions_music(self):
        bridge = load_bridge()
        cmd = bridge.build_narration_command("bridge-jobs/x", "bm_george", "karaoke", "")
        self.assertIn("--captions karaoke", cmd)
        # bad captions value falls back to the default
        self.assertIn("--captions karaoke", bridge.build_narration_command("x", "bm_george", "evil; rm", ""))
        # a music path with shell metacharacters is dropped
        self.assertNotIn(";", bridge.build_narration_command("x", "bm_george", "simple", "a; rm -rf /"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_bridge_workflow.BridgeWorkflowTests.test_narration_command_threads_and_validates_captions_music -v`
Expected: FAIL (signature mismatch).

- [ ] **Step 3: Update the command builder + constant**

In `scripts/bridge_server.py`, change `NARRATION_CMD` and `build_narration_command`:

```python
NARRATION_CMD = "python scripts/add_narration.py {job_dir}/project.json --voice {voice} --captions {captions}{music}"


def build_narration_command(job_dir: str, voice: str = "bm_george", captions: str = "karaoke", music: str = "") -> str:
    safe_voice = voice if re.fullmatch(r"[a-z_]+", str(voice or "")) else "bm_george"
    safe_captions = captions if str(captions) in {"karaoke", "simple", "off"} else "karaoke"
    music_arg = ""
    if music and re.fullmatch(r"[A-Za-z0-9_./\\:\- ]+", str(music)):
        music_arg = f' --music "{music}"'
    return NARRATION_CMD.format(job_dir=job_dir, voice=safe_voice, captions=safe_captions, music=music_arg)
```

In `run_render_job`, pass the request's caption/music prefs:

```python
        command += " && " + build_narration_command(
            str(job_dir),
            str(request.get("voice") or "bm_george"),
            str(request.get("captions") or "karaoke"),
            str(request.get("music") or ""),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_bridge_workflow -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge_server.py tests/test_bridge_workflow.py
git commit -m "feat: thread caption/music options through the render chain"
```

---

## Self-Review Notes

- **Spec coverage:** music local-folder selection + ducking (Tasks 1-2) ✓; simple captions no-dep (Tasks 3-4) ✓; karaoke via transcribe with simple fallback (Tasks 5-6) ✓; burned-in captions re-encode vs copy branch (Task 4) ✓; bridge flags allowlist-validated (Task 7) ✓; never-break/idempotent inherited from Phase 3 (finish step keeps its guards) ✓.
- **Windows subtitle path:** handled by running ffmpeg with `cwd=exports_dir` and a basename `subtitles=finish.ass` (Task 4).
- **Dependency posture:** simple captions + music need nothing new; karaoke degrades to simple when whisper-cpp is absent (Task 6) — matches the spec.
- **Type consistency:** `build_audio_filter(items, has_music, music_input_index, music_volume)` and `build_ffmpeg_command(video, wavs, filter, output, music, ass_name)` signatures are used consistently across Tasks 2/4; `simple_cues`/`karaoke_cues`/`build_ass(cues, mode, width, height)` names match across Tasks 3/5/4/6; `build_narration_command(job_dir, voice, captions, music)` matches Task 7 tests and the `run_render_job` call.
- **Deferred (per spec):** MusicGen-generated music (local-folder chosen for v1; MusicGen only used to make a *test* track in Task 2's smoke); HyperFrames-native caption renderer (hand-rolled ASS chosen for isolation).
- **Note for executor:** the Task 4 snippet `collect_narration.__self__ if False else None` is illustrative scaffolding — delete that line; the real scene source is `captions_lib_scenes(json.loads(project_path.read_text(...)))` shown in Task 6. Use the Task 6 caption block as the authoritative version; Task 4 ships the simple-only subset of it.
