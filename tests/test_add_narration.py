from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "add_narration.py"


def load():
    spec = importlib.util.spec_from_file_location("add_narration", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class CollectNarrationTests(unittest.TestCase):
    def test_skips_empty_narration_and_uses_scene_start(self):
        an = load()
        project = {"payload": {"storyboard": {"scenes": [
            {"id": "s1", "narration": "Hello there.", "start": 0, "duration": 5},
            {"id": "s2", "narration": "", "start": 5, "duration": 5},
            {"id": "s3", "narration": "Third line.", "start": 10, "duration": 5},
        ]}}}
        items = an.collect_narration(project)
        self.assertEqual([i["scene_id"] for i in items], ["s1", "s3"])
        self.assertEqual(items[0]["start_ms"], 0)
        self.assertEqual(items[1]["start_ms"], 10000)

    def test_falls_back_to_cumulative_durations_when_no_start(self):
        an = load()
        project = {"scenes": [
            {"id": "s1", "narration": "A.", "duration": 3},
            {"id": "s2", "narration": "B.", "duration": 4},
        ]}
        items = an.collect_narration(project)
        self.assertEqual(items[0]["start_ms"], 0)
        self.assertEqual(items[1]["start_ms"], 3000)

    def test_no_narration_returns_empty(self):
        an = load()
        self.assertEqual(an.collect_narration({"scenes": [{"id": "s1", "duration": 3}]}), [])


class FilterTests(unittest.TestCase):
    def test_empty_items(self):
        an = load()
        self.assertEqual(an.build_ffmpeg_filter([]), "")

    def test_single_scene_delays_and_pads(self):
        an = load()
        f = an.build_ffmpeg_filter([{"start_ms": 0}])
        self.assertIn("[1]adelay=0", f)
        self.assertTrue(f.endswith("apad[a]"))
        self.assertNotIn("amix", f)

    def test_multi_scene_mixes_and_pads(self):
        an = load()
        f = an.build_ffmpeg_filter([{"start_ms": 0}, {"start_ms": 5000}])
        self.assertIn("[1]adelay=0[a1]", f)
        self.assertIn("[2]adelay=5000[a2]", f)
        self.assertIn("amix=inputs=2:normalize=0", f)
        self.assertTrue(f.endswith("apad[a]"))


class CommandTests(unittest.TestCase):
    def test_command_maps_video_and_mixed_audio(self):
        an = load()
        cmd = an.build_ffmpeg_command(Path("v.mp4"), [Path("a1.wav"), Path("a2.wav")], "FILT", Path("out.mp4"))
        joined = " ".join(cmd)
        self.assertIn("-filter_complex", cmd)
        self.assertIn("FILT", cmd)
        self.assertIn("v.mp4", joined)
        self.assertIn("a1.wav", joined)
        self.assertIn("a2.wav", joined)
        # video mapped and stream-copied, mixed audio mapped, trimmed to video length
        self.assertIn("0:v", cmd)
        self.assertIn("[a]", cmd)
        self.assertIn("copy", cmd)
        self.assertIn("-shortest", cmd)


if __name__ == "__main__":
    unittest.main()
