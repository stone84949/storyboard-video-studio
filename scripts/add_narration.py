#!/usr/bin/env python3
"""Add spoken narration to a rendered storyboard video.

Reads a bridge job ``project.json``, generates per-scene speech from each
scene's ``narration`` text with HyperFrames' local ``tts`` (Kokoro-82M), times
each line to the scene's start, and muxes the combined voice track onto the
already-rendered (silent) ``exports/final.mp4`` with ffmpeg.

Designed to never break the render: if there is no narration, or TTS/ffmpeg
fails, the silent ``final.mp4`` is kept in place, the reason is logged, and the
script exits 0.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import music as music_lib  # noqa: E402
import captions as captions_lib  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_VOICE = "bm_george"


def slugify(value: str, fallback: str = "scene") -> str:
    out = "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:48] or fallback


def payload_ref(project: dict[str, Any]) -> dict[str, Any]:
    payload = project.get("payload") if isinstance(project.get("payload"), dict) else project
    if isinstance(payload.get("storyboard"), dict):
        return payload["storyboard"]
    return payload


def captions_lib_scenes(project: dict[str, Any]) -> list[dict[str, Any]]:
    return (payload_ref(project).get("scenes") or [])


def collect_narration(project: dict[str, Any]) -> list[dict[str, Any]]:
    """Return scenes that have narration, with a start time in milliseconds.

    Uses each scene's ``start`` when present, otherwise a cumulative sum of
    durations. Scenes with empty narration are skipped.
    """
    payload = payload_ref(project)
    scenes = payload.get("scenes") or []
    items: list[dict[str, Any]] = []
    cursor = 0.0
    for index, scene in enumerate(scenes, start=1):
        duration = float(scene.get("duration") or scene.get("hold_seconds") or scene.get("vo_seconds") or 4)
        start = scene.get("start")
        start = float(start) if start is not None else cursor
        text = str(scene.get("narration") or scene.get("script") or "").strip()
        scene_id = str(scene.get("id") or scene.get("scene_id") or f"scene-{index:03d}")
        if text:
            items.append({
                "scene_id": scene_id,
                "index": index,
                "text": text,
                "start_ms": int(round(start * 1000)),
            })
        cursor = start + duration
    return items


def build_ffmpeg_filter(items: list[dict[str, Any]]) -> str:
    """Build the filter_complex that delays each voice input and mixes them.

    Input 0 is the video; voice inputs are numbered 1..N in the order of
    ``items``. Each is delayed to its ``start_ms`` and the results are amixed
    with ``normalize=0`` so volumes are preserved.
    """
    if not items:
        return ""
    labels: list[str] = []
    parts: list[str] = []
    for pos, item in enumerate(items):
        input_index = pos + 1
        label = f"a{input_index}"
        parts.append(f"[{input_index}]adelay={item['start_ms']}:all=1[{label}]")
        labels.append(f"[{label}]")
    # ``apad`` extends the mixed voice track with silence so ``-shortest`` trims
    # it to the video length rather than cutting the video short when the last
    # line ends before the video does.
    if len(labels) == 1:
        mix = f"{labels[0]}apad[a]"
    else:
        mix = "".join(labels) + f"amix=inputs={len(labels)}:normalize=0:dropout_transition=0,apad[a]"
    return ";".join(parts + [mix])


def build_ffmpeg_command(video: Path, wavs: list[Path], filter_complex: str, output: Path, music: Path | None = None, ass_name: str | None = None) -> list[str]:
    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [ffmpeg, "-y", "-i", str(video)]
    for wav in wavs:
        cmd += ["-i", str(wav)]
    if music is not None:
        cmd += ["-stream_loop", "-1", "-i", str(music)]  # loop the track; -shortest trims
    if ass_name:
        fc = f"{filter_complex};[0:v]subtitles={ass_name}[v]"
        cmd += [
            "-filter_complex", fc,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        ]
    else:
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[a]",
            "-c:v", "copy",
        ]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", str(output)]
    return cmd


def synth_scene(text: str, out_wav: Path, voice: str, speed: float, log) -> bool:
    npx = shutil.which("npx") or "npx"
    cmd = [npx, "--yes", "hyperframes", "tts", text, "-o", str(out_wav), "-v", voice, "-s", str(speed)]
    log.write(f"\n$ tts -> {out_wav.name}\n")
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True, timeout=300)
    log.write(completed.stdout + completed.stderr)
    return completed.returncode == 0 and out_wav.exists()


_WHISPER_MODEL = None


def _whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def transcribe_wav_words(wav: Path, log) -> dict[str, Any]:
    """Word-level transcript of a narration wav via faster-whisper (local, no cmake).

    Returns ``{"ok": True, "words": [{word, start, end}]}`` (seconds), or
    ``{"ok": False}`` when faster-whisper is unavailable or transcription fails —
    the caller then falls back to simple captions.
    """
    try:
        model = _whisper_model()
        segments, _info = model.transcribe(str(wav), word_timestamps=True)
        words = []
        for seg in segments:
            for w in (seg.words or []):
                words.append({"word": str(w.word).strip(), "start": float(w.start), "end": float(w.end)})
        return {"ok": True, "words": words}
    except Exception as exc:
        log.write(f"\ntranscribe unavailable/failed ({exc}); will use simple captions\n")
        return {"ok": False, "reason": str(exc)}


def add_narration(project_path: Path, voice: str, speed: float, music: str | None = None, captions: str = "off") -> dict[str, Any]:
    project_path = project_path.resolve()
    job_dir = project_path.parent
    exports_dir = job_dir / "exports"
    logs_dir = job_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / "narration.log"

    summary = {"ok": True, "voice": voice, "scenes_voiced": 0, "output": "", "skipped": "", "music": "", "captions": ""}

    with log_path.open("a", encoding="utf-8") as log:
        final = exports_dir / "final.mp4"
        if not final.exists():
            summary.update(ok=False, skipped="no rendered final.mp4 to narrate")
            log.write("\nSKIP: no final.mp4\n")
            _write_summary(exports_dir, summary)
            return summary

        silent = exports_dir / "final-silent.mp4"
        # Narrate from the true silent master when a prior run preserved it, so
        # re-runs are idempotent and never clobber the original silent render.
        source_video = silent if silent.exists() else final

        project = json.loads(project_path.read_text(encoding="utf-8"))
        items = collect_narration(project)
        if not items:
            summary["skipped"] = "no narration text on any scene"
            log.write("\nSKIP: no narration text\n")
            _write_summary(exports_dir, summary)
            return summary

        audio_dir = job_dir / "audio" / "narration"
        audio_dir.mkdir(parents=True, exist_ok=True)

        voiced: list[dict[str, Any]] = []
        wavs: list[Path] = []
        for item in items:
            out_wav = audio_dir / f"{item['index']:03d}-{slugify(item['scene_id'])}.wav"
            try:
                ok = synth_scene(item["text"], out_wav, voice, speed, log)
            except Exception as exc:  # keep going; one bad scene shouldn't kill the track
                ok = False
                log.write(f"\ntts error for {item['scene_id']}: {exc}\n")
            if ok:
                voiced.append(item)
                wavs.append(out_wav)

        if not wavs:
            summary.update(ok=False, skipped="tts produced no audio (is kokoro-onnx installed?)")
            log.write("\nSKIP: no tts output; keeping silent final.mp4\n")
            _write_summary(exports_dir, summary)
            return summary

        root_music = REPO_ROOT / "music"
        per_video_music = job_dir / "music"
        track = music_lib.select_track(root_music, per_video_music, explicit=music)
        music_input_index = len(wavs) + 1 if track else None
        filt = music_lib.build_audio_filter(voiced, has_music=bool(track), music_input_index=music_input_index)
        narrated_tmp = exports_dir / "final-narrated.tmp.mp4"

        ass_name = ""
        if captions and captions != "off":
            effective_mode = captions
            cues: list[dict[str, Any]] = []
            if captions == "karaoke":
                for item, wav in zip(voiced, wavs):
                    tj = transcribe_wav_words(wav, log)
                    if not tj.get("ok"):
                        effective_mode = "simple"  # whisper unavailable / failed
                        log.write("\nkaraoke unavailable; falling back to simple captions\n")
                        cues = []
                        break
                    cues.extend(captions_lib.karaoke_cues_for_scene(
                        item["text"], tj.get("words") or [], scene_start_ms=item["start_ms"]))
            if effective_mode == "simple":
                cues = captions_lib.simple_cues(captions_lib_scenes(project))
            if cues:
                (exports_dir / "finish.ass").write_text(
                    captions_lib.build_ass(cues, mode=effective_mode, width=1080, height=1920), encoding="utf-8")
                ass_name = "finish.ass"
                summary["captions"] = effective_mode

        cmd = build_ffmpeg_command(source_video, wavs, filt, narrated_tmp, music=track, ass_name=ass_name or None)
        summary["music"] = track.name if track else ""
        run_cwd = exports_dir if ass_name else REPO_ROOT
        log.write("\n$ " + " ".join(cmd) + "\n")
        try:
            completed = subprocess.run(cmd, cwd=run_cwd, text=True, capture_output=True, timeout=600)
            log.write(completed.stdout + completed.stderr)
            if completed.returncode != 0 or not narrated_tmp.exists():
                raise RuntimeError(f"ffmpeg exited {completed.returncode}")
        except Exception as exc:
            summary.update(ok=False, skipped=f"ffmpeg mux failed: {exc}")
            log.write(f"\nSKIP: ffmpeg failed; keeping silent final.mp4: {exc}\n")
            if narrated_tmp.exists():
                narrated_tmp.unlink()
            _write_summary(exports_dir, summary)
            return summary

        # Success: preserve the true silent master (first run only), then promote
        # the narrated file to final.mp4 (replace() overwrites on a re-run).
        if not silent.exists():
            final.rename(silent)
        narrated_tmp.replace(final)

        summary.update(scenes_voiced=len(voiced), output="exports/final.mp4")
        log.write(f"\nOK: narrated {len(voiced)} scene(s); silent kept as final-silent.mp4\n")
        _write_summary(exports_dir, summary)
        return summary


def _write_summary(exports_dir: Path, summary: dict[str, Any]) -> None:
    exports_dir.mkdir(exist_ok=True)
    (exports_dir / "narration-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Add TTS narration to a rendered storyboard video")
    parser.add_argument("project_json", type=Path)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--music", default=None, help="explicit music file, else music/ folders are used")
    parser.add_argument("--captions", default="off", help="off | simple | karaoke")
    args = parser.parse_args()

    try:
        summary = add_narration(args.project_json, args.voice, args.speed, music=args.music, captions=args.captions)
    except Exception as exc:  # never fail the render chain
        print(f"WARNING: narration step skipped: {exc}", file=sys.stderr)
        return 0
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
