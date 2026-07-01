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

    def test_materialize_and_render_commands_split(self):
        bridge = load_bridge()
        mat = bridge.build_materialize_command("bridge-jobs/example")
        self.assertIn("materialize_assets.py", mat)
        self.assertIn("bridge-jobs/example", mat)
        self.assertNotIn("render_hyperframes_job.py", mat)

        render = bridge.build_render_command("bridge-jobs/example", "short-shorts", "hyperframes")
        self.assertIn("render_hyperframes_job.py", render)
        self.assertNotIn("materialize_assets.py", render)

        montage = bridge.build_render_command("bridge-jobs/example", "montage", "openmontage")
        self.assertIn("prepare_montage_handoff.py", montage)

    def test_pipeline_command_contracts_are_documented(self):
        bridge = load_bridge()
        for target in ["short-shorts", "longer-shorts", "montage"]:
            command = bridge.build_launch_command(target, "example-job", execute=False)
            self.assertIn("DRY RUN", command)
            self.assertIn(target, command)
        short_command = bridge.build_launch_command("short-shorts", "example-job", execute=True)
        self.assertIn("materialize_assets.py", short_command)
        self.assertIn("render_hyperframes_job.py", short_command)

    def test_resolve_served_job_asset_guards_traversal(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "job-1" / "assets" / "images" / "materialized" / "001.png"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(b"\x89PNG\r\n")

            ok = bridge.resolve_served_job_asset(
                "/jobs/job-1/assets/images/materialized/001.png", root
            )
            self.assertIsNotNone(ok)
            self.assertEqual(ok.read_bytes(), b"\x89PNG\r\n")

            self.assertIsNone(bridge.resolve_served_job_asset("/jobs/../secret.txt", root))
            self.assertIsNone(bridge.resolve_served_job_asset("/jobs/job-1/missing.png", root))

    def test_read_job_returns_scene_image_urls(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "hyperframes",
                "run_label": "read job test",
                "execute": False,
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp))
            job_id = result["job_id"]
            job_dir = Path(result["job_dir"])
            (job_dir / "exports").mkdir(exist_ok=True)
            (job_dir / "exports" / "asset-manifest.json").write_text(
                json.dumps({"assets": [
                    {"scene_id": "scene-001", "status": "generated",
                     "asset": "assets/images/materialized/001-scene-001.png", "notes": ""},
                    {"scene_id": "scene-002", "status": "downloaded",
                     "asset": "assets/images/materialized/002-scene-002.jpg", "notes": ""},
                ]}), encoding="utf-8")

            out = bridge.read_job(job_id, Path(tmp))
            self.assertEqual(len(out["scenes"]), 2)
            self.assertEqual(
                out["scenes"][0]["image_url"],
                f"/jobs/{job_id}/assets/images/materialized/001-scene-001.png",
            )
            self.assertEqual(out["scenes"][0]["status"], "generated")

    def test_read_job_unknown_id_raises(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                bridge.read_job("does-not-exist", Path(tmp))

    def test_read_job_without_manifest_returns_pending_scenes(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "hyperframes",
                "run_label": "read job pending test",
                "execute": False,
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp))
            job_id = result["job_id"]

            out = bridge.read_job(job_id, Path(tmp))
            self.assertEqual(len(out["scenes"]), 2)
            for scene in out["scenes"]:
                self.assertEqual(scene["image_url"], "")
                self.assertEqual(scene["status"], "pending")

    def test_materialize_action_writes_materialize_only_command(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "machine": "BEAST",
                "engine": "hyperframes",
                "run_label": "materialize action",
                "execute": False,
                "action": "materialize",
                "payload": self.realistic_payload(),
            }
            result = bridge.create_launch_job(request, Path(tmp), action="materialize")
            self.assertEqual(result["status"], "dry_run")
            self.assertIn("scenes", result)
            self.assertEqual(len(result["scenes"]), 2)
            command = (Path(result["job_dir"]) / "launch-command.txt").read_text(encoding="utf-8")
            self.assertIn("materialize_assets.py", command)
            self.assertNotIn("render_hyperframes_job.py", command)

    def test_render_action_applies_reviewed_asset_and_builds_render_command(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            created = bridge.create_launch_job(
                {
                    "machine": "BEAST",
                    "engine": "hyperframes",
                    "run_label": "render action",
                    "execute": False,
                    "payload": self.realistic_payload(),
                },
                Path(tmp),
            )
            job_id = created["job_id"]

            reviewed = {
                "job_id": job_id,
                "engine": "hyperframes",
                "execute": False,
                "payload": {
                    "storyboard": {
                        "id": "x",
                        "title": "x",
                        "aspect_ratio": "9:16",
                        "scenes": [
                            {"id": "scene-001", "title": "Cold open", "assetUrl": "https://real.example/site.jpg", "duration": 3.4},
                            {"id": "scene-002", "title": "Reveal", "assetUrl": "lab-notes.jpg", "duration": 4.1},
                        ],
                    }
                },
            }
            result = bridge.run_render_job(reviewed, Path(tmp))
            self.assertEqual(result["status"], "dry_run")
            self.assertIn("render_hyperframes_job.py", result["command"])

            project = json.loads((Path(created["job_dir"]) / "project.json").read_text(encoding="utf-8"))
            payload = project["payload"]
            storyboard = payload.get("storyboard", payload)
            self.assertEqual(storyboard["scenes"][0]["asset"], "https://real.example/site.jpg")
            self.assertEqual(storyboard["scenes"][1]["asset"], "lab-notes.jpg")

    def test_render_action_unknown_job_raises(self):
        bridge = load_bridge()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                bridge.run_render_job({"job_id": "nope", "payload": {}}, Path(tmp))

    def test_render_command_appends_narration_for_hyperframes(self):
        bridge = load_bridge()
        self.assertIn("add_narration.py", bridge.build_narration_command("bridge-jobs/x"))
        # a voice with shell metacharacters is rejected back to the safe default
        self.assertIn("--voice bm_george", bridge.build_narration_command("x", "evil; rm -rf /"))
        with tempfile.TemporaryDirectory() as tmp:
            created = bridge.create_launch_job(
                {"machine": "BEAST", "engine": "hyperframes", "run_label": "narr",
                 "execute": False, "payload": self.realistic_payload()},
                Path(tmp),
            )
            result = bridge.run_render_job(
                {"job_id": created["job_id"], "engine": "hyperframes", "execute": False,
                 "payload": {"storyboard": {"scenes": [{"id": "scene-001", "assetUrl": "x.jpg"}]}}},
                Path(tmp),
            )
            self.assertIn("render_hyperframes_job.py", result["command"])
            self.assertIn("add_narration.py", result["command"])


if __name__ == "__main__":
    unittest.main()
