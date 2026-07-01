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
