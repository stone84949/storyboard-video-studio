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
