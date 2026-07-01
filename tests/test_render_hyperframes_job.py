from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RENDER_PATH = REPO_ROOT / "scripts" / "render_hyperframes_job.py"


def load_render_module():
    spec = importlib.util.spec_from_file_location("render_hyperframes_job", RENDER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class RenderHyperframesJobTests(unittest.TestCase):
    def test_normalize_payload_disables_viewer_overlays_by_default(self):
        mod = load_render_module()
        payload = mod.normalize_payload(
            {
                "project_title": "Unit Test",
                "scenes": [
                    {
                        "id": "scene-001",
                        "title": "Hook",
                        "narration": "A strange thing happened.",
                        "motion": "slow push in",
                        "duration": 4,
                        "asset": "",
                    }
                ],
            }
        )
        self.assertFalse(payload["viewer_overlays"])

    def test_generate_index_html_hides_scene_copy_by_default(self):
        mod = load_render_module()
        payload = {
            "title": "Unit Test",
            "aspect_ratio": "9:16",
            "viewer_overlays": False,
            "scenes": [
                {
                    "id": "scene-001",
                    "title": "The Hook",
                    "narration": "What if the archive was alive?",
                    "motion": "slow push in",
                    "duration": 4,
                    "asset": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            job_dir = Path(tmp) / "job"
            workspace.mkdir(parents=True, exist_ok=True)
            job_dir.mkdir(parents=True, exist_ok=True)
            mod.generate_index_html(payload, workspace, job_dir)
            html = (workspace / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('<div class="scene-copy">', html)
        self.assertNotIn("Scene 01 · slow push in", html)
        self.assertNotIn("The Hook", html)
        self.assertNotIn("What if the archive was alive?", html)

    def test_generate_index_html_keeps_scene_copy_when_explicitly_enabled(self):
        mod = load_render_module()
        payload = {
            "title": "Unit Test",
            "aspect_ratio": "9:16",
            "viewer_overlays": True,
            "scenes": [
                {
                    "id": "scene-001",
                    "title": "The Hook",
                    "narration": "What if the archive was alive?",
                    "motion": "slow push in",
                    "duration": 4,
                    "asset": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            job_dir = Path(tmp) / "job"
            workspace.mkdir(parents=True, exist_ok=True)
            job_dir.mkdir(parents=True, exist_ok=True)
            mod.generate_index_html(payload, workspace, job_dir)
            html = (workspace / "index.html").read_text(encoding="utf-8")
        self.assertIn('<div class="scene-copy">', html)
        self.assertIn("Scene 01 · slow push in", html)
        self.assertIn("The Hook", html)
        self.assertIn("What if the archive was alive?", html)


if __name__ == "__main__":
    unittest.main()
