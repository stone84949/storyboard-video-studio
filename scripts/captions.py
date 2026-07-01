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


def karaoke_cues_for_scene(script_text, whisper_words, scene_start_ms: int = 0, max_words: int = 4) -> list[dict[str, Any]]:
    """Karaoke cues that ALWAYS show the author's exact script text.

    ASR (whisper) can mis-hear proper nouns, so we never display its guessed
    words. We take the known ``script_text`` for the words and use the whisper
    timings only: paired 1:1 when the word counts match, otherwise the script
    words are evenly distributed across the actual spoken span. Returns [] when
    there is no script or no timing to work with (caller falls back to simple).
    """
    script_words = str(script_text or "").split()
    words = whisper_words or []
    if not script_words or not words:
        return []
    if len(words) == len(script_words):
        timed = [
            {"word": script_words[i],
             "t0": int(round(float(words[i].get("start", 0)) * 1000)),
             "t1": int(round(float(words[i].get("end", 0)) * 1000))}
            for i in range(len(script_words))
        ]
    else:
        # Even-distribute the script words across the span whisper actually heard.
        span0 = float(words[0].get("start", 0))
        span1 = float(words[-1].get("end", span0 + len(script_words) * 0.4))
        total_ms = max(1, int(round((span1 - span0) * 1000)))
        base = int(round(span0 * 1000))
        each = max(1, total_ms // len(script_words))
        timed = [
            {"word": w,
             "t0": base + i * each,
             "t1": base + ((i + 1) * each if i < len(script_words) - 1 else total_ms)}
            for i, w in enumerate(script_words)
        ]
    for t in timed:
        t["t0"] += scene_start_ms
        t["t1"] += scene_start_ms
    cues: list[dict[str, Any]] = []
    for i in range(0, len(timed), max_words):
        group = timed[i:i + max_words]
        cues.append({"start_ms": group[0]["t0"], "end_ms": group[-1]["t1"], "words": group})
    return cues


def build_ass(cues: list[dict[str, Any]], mode: str, width: int, height: int) -> str:
    body = _header(width, height)
    for cue in cues:
        if mode == "karaoke" and cue.get("words"):
            # Un-sung words render in SecondaryColour (white); each word fills to
            # PrimaryColour (amber) via \kf as it is spoken — the karaoke sweep.
            # Setting \1c/\2c inline gives contrast the base style (all-white) lacks.
            parts = [f"{{\\1c{_HIGHLIGHT}\\2c&H00FFFFFF&}}"]
            for w in cue["words"]:
                dur_cs = max(1, int((w["t1"] - w["t0"]) / 10))
                parts.append(f"{{\\kf{dur_cs}}}{w['word']} ")
            body += _dialogue(cue["start_ms"], cue["end_ms"], "".join(parts).strip())
        else:
            body += _dialogue(cue["start_ms"], cue["end_ms"], cue["text"])
    return body
