from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONVERTER_PATH = REPO_ROOT / "scripts" / "storyboard_to_config.py"


def load_converter():
    spec = importlib.util.spec_from_file_location("storyboard_to_config", CONVERTER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class StoryboardConfigTests(unittest.TestCase):
    def test_build_job_config_from_bridge_project_json(self):
        converter = load_converter()
        project = {
            "job_id": "unit-json-job",
            "pipeline_target": "longer-shorts",
            "project_title": "Unit JSON Job",
            "aspect_ratio": "9:16",
            "payload": {
                "target_duration_seconds": 44,
                "scenes": [
                    {"id": "scene-001", "title": "One", "narration": "First narration.", "duration": 5, "asset": "one.jpg", "motion": "slow push in"},
                    {"id": "scene-002", "title": "Two", "narration": "Second narration.", "duration": 6, "asset": "two.jpg", "motion": "slow pan right"},
                ],
            },
        }
        config = converter.build_job_config_from_bridge_project(project)
        self.assertEqual(config["job_id"], "unit-json-job")
        self.assertEqual(config["pipeline_target"], "longer-shorts")
        self.assertEqual(config["aspect_ratio"], "9:16")
        self.assertEqual(config["target_duration_seconds"], 44)
        self.assertEqual(len(config["images"]), 2)
        self.assertEqual(config["images"][0]["filename"], "one.jpg")
        self.assertEqual(config["images"][0]["motion"], "slow push in")

    def test_scaffold_json_job_folder_writes_config_under_exports(self):
        converter = load_converter()
        config = {
            "job_id": "unit-json-scaffold",
            "title": "Unit JSON Scaffold",
            "input_text": "Narration",
            "target_duration_seconds": 12,
            "resolution": {"width": 1080, "height": 1920},
            "aspect_ratio": "9:16",
            "pipeline_target": "short-shorts",
            "image_folder": "assets/images/src",
            "images": [{"panel": 1, "filename": "one.jpg", "mode": "fill", "focal_point": {"x_pct": 0.5, "y_pct": 0.5}, "allow_upscale": False, "scene_description": "One", "narration": "Narration", "motion": "slow push in", "notes": ""}],
            "output_format": {"container": "mp4", "codec": "libx264", "hw_accel": None, "crf": 18, "preset": "veryfast"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "project.json"
            source.write_text(json.dumps({"ok": True}), encoding="utf-8")
            job_dir, cfg_path, img_src = converter.scaffold_job_folder(config, source, base_dir=Path(tmp), source_format="json")
            self.assertTrue(cfg_path.exists())
            self.assertTrue((job_dir / "exports" / "editor-handoff.md").exists())
            self.assertTrue(img_src.exists())


if __name__ == "__main__":
    unittest.main()
