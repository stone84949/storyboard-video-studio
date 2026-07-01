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


class KaraokeAssTests(unittest.TestCase):
    def test_karaoke_ass_has_kf_and_colour_contrast(self):
        c = load()
        cues = [{"start_ms": 0, "end_ms": 800, "words": [
            {"word": "In", "t0": 0, "t1": 200},
            {"word": "the", "t0": 200, "t1": 500},
        ]}]
        ass = c.build_ass(cues, mode="karaoke", width=1080, height=1920)
        self.assertIn("\\kf", ass)   # per-word karaoke timing present
        self.assertIn("\\1c", ass)   # sung colour override (creates the sweep contrast)
        self.assertIn("\\2c", ass)   # un-sung colour override
        # regression guard: the old all-white bug set \c per word AND left primary
        # == secondary; ensure a distinct primary colour override exists.
        self.assertIn("\\1c" + c._HIGHLIGHT, ass)
