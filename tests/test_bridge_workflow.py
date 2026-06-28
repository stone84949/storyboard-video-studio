from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_PATH = REPO_ROOT / "scripts" / "bridge_server.py"


def load_bridge():
    spec = importlib.util.spec_from_file_location("bridge_server", BRIDGE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class BridgeWorkflowTests(unittest.TestCase):
    def realistic_payload(self):
        return {
            "project_title": "Forgotten Mystery Dry Run",
            "pipeline_target": "short-shorts",
            "aspect_ratio": "9:16",
            "scenes": [
                {
                    "id": "scene-001",
                    "title": "Cold open",
                    "narration": "A strange signal appears in the archive.",
                    "duration": 3.4,
                    "asset": "archive-signal.jpg",
                    "motion": "slow push in",
                },
                {
                    "id": "scene-002",
                    "title": "Reveal",
                    "narration": "The clue points to a forgotten experiment.",
                    "duration": 4.1,
                    "asset": "lab-notes.jpg",
                    "motion": "slow pan right",
                },
            ],
        }

    def test_launch_payload_writes_reusable_job_folder(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "dry-run",
                "run_label": "unit bridge job",
                "execute": False,
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp))
            job_dir = Path(result["job_dir"])

            self.assertEqual(result["status"], "dry_run")
            self.assertTrue((job_dir / "project.json").exists())
            self.assertTrue((job_dir / "STATUS.md").exists())
            self.assertTrue((job_dir / "activity.md").exists())
            self.assertTrue((job_dir / "launch-command.txt").exists())
            self.assertEqual(len(list((job_dir / "scenes").glob("*.json"))), 2)

            project = json.loads((job_dir / "project.json").read_text(encoding="utf-8"))
            self.assertEqual(project["machine"], "BEAST")
            self.assertEqual(project["pipeline_target"], "short-shorts")
            self.assertEqual(project["live_execution_enabled"], False)

    def test_rejects_missing_required_launch_fields(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                bridge.create_launch_job({"payload": {"scenes": []}}, Path(tmp))
            self.assertIn("machine", str(ctx.exception))

    def test_accepts_ultimate_workflow_nested_payload(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "beast",
                "engine": "hyperframes",
                "run_label": "ultimate workflow unit",
                "execute": False,
                "payload": {
                    "storyboard": {
                        "id": "storyboard-ultimate-001",
                        "title": "Storyboard Ultimate Workflow",
                        "aspect_ratio": "9:16",
                        "total_duration_sec": 7.5,
                        "scenes": [
                            {"id": "scene-01", "title": "Cold open", "assetUrl": "https://example.com/a.jpg", "duration": 3.2, "motionPreset": "zoom-in", "narration": "Hook narration."},
                            {"id": "scene-02", "title": "Proof", "assetUrl": "https://example.com/b.jpg", "duration": 4.3, "motionPreset": "pan-left-right", "narration": "Proof narration."},
                        ],
                    },
                    "launcher": {"machine": "beast", "engine": "hyperframes", "execute": False},
                },
            }
            result = bridge.create_launch_job(request, Path(tmp))
            job_dir = Path(result["job_dir"])
            project = json.loads((job_dir / "project.json").read_text(encoding="utf-8"))
            scene_one = json.loads(sorted((job_dir / "scenes").glob("*.json"))[0].read_text(encoding="utf-8"))
            self.assertEqual(project["project_title"], "Storyboard Ultimate Workflow")
            self.assertEqual(project["aspect_ratio"], "9:16")
            self.assertEqual(scene_one["asset"], "https://example.com/a.jpg")
            self.assertEqual(scene_one["motion"], "zoom-in")
            self.assertTrue((job_dir / "storyboard" / "source-payload.json").exists())

    def test_pipeline_command_contracts_are_documented(self):
        bridge = load_bridge()
        for target in ["short-shorts", "longer-shorts", "montage"]:
            command = bridge.build_launch_command(target, "example-job", execute=False)
            self.assertIn("DRY RUN", command)
            self.assertIn(target, command)
        short_command = bridge.build_launch_command("short-shorts", "example-job", execute=True)
        self.assertIn("materialize_assets.py", short_command)
        self.assertIn("render_hyperframes_job.py", short_command)


if __name__ == "__main__":
    unittest.main()
