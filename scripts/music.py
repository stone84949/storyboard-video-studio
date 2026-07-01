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
    if not has_music or music_input_index is None:
        parts[-1] = parts[-1][:-len("[narr]")] + "[a]"
        return ";".join(parts)
    parts.append("[narr]asplit[narrmix][narrkey]")
    parts.append(f"[{music_input_index}]volume={music_volume}[bg]")
    parts.append("[bg][narrkey]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=400[bgduck]")
    parts.append("[narrmix][bgduck]amix=inputs=2:normalize=0:dropout_transition=0[a]")
    return ";".join(parts)
