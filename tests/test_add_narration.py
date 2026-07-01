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
        self.assertIn("[1]adelay=0:all=1[a1]", f)
        self.assertIn("[2]adelay=5000:all=1[a2]", f)
        self.assertIn("amix=inputs=2:normalize=0", f)
        self.assertTrue(f.endswith("apad[a]"))

    def test_multi_scene_exact_filter_string(self):
        an = load()
        f = an.build_ffmpeg_filter([{"start_ms": 0}, {"start_ms": 5000}])
        self.assertEqual(
            f,
            "[1]adelay=0:all=1[a1];[2]adelay=5000:all=1[a2];"
            "[a1][a2]amix=inputs=2:normalize=0:dropout_transition=0,apad[a]",
        )


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


class PromoteIdempotencyTests(unittest.TestCase):
    """The rename/promote dance is the highest-risk code: re-running must never
    clobber the true silent master (regression guard for the data-loss bug)."""

    def _run_once(self, an, job, narrated_bytes):
        import subprocess as _sp

        def fake_synth(text, out_wav, voice, speed, log):
            out_wav.write_bytes(b"WAV")
            return True

        def fake_ffmpeg(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(narrated_bytes)  # last arg is the output temp
            return _sp.CompletedProcess(cmd, 0, "", "")

        orig_synth, orig_run = an.synth_scene, an.subprocess.run
        an.synth_scene = fake_synth
        an.subprocess.run = fake_ffmpeg
        try:
            return an.add_narration(job / "project.json", "bm_george", 1.0)
        finally:
            an.synth_scene = orig_synth
            an.subprocess.run = orig_run

    def test_rerun_preserves_original_silent_master(self):
        an = load()
        import json as _json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            job = Path(tmp)
            (job / "exports").mkdir()
            (job / "exports" / "final.mp4").write_bytes(b"SILENT_MASTER")
            (job / "project.json").write_text(
                _json.dumps({"scenes": [{"id": "s1", "narration": "Hi.", "duration": 5, "start": 0}]}),
                encoding="utf-8",
            )

            self._run_once(an, job, b"NARRATED_1")
            self.assertEqual((job / "exports" / "final-silent.mp4").read_bytes(), b"SILENT_MASTER")
            self.assertEqual((job / "exports" / "final.mp4").read_bytes(), b"NARRATED_1")

            # Second run: silent master must stay the ORIGINAL, final updates.
            self._run_once(an, job, b"NARRATED_2")
            self.assertEqual((job / "exports" / "final-silent.mp4").read_bytes(), b"SILENT_MASTER")
            self.assertEqual((job / "exports" / "final.mp4").read_bytes(), b"NARRATED_2")


if __name__ == "__main__":
    unittest.main()
