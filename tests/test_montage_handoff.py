from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "prepare_montage_handoff.py"


def load_module():
    spec = importlib.util.spec_from_file_location("prepare_montage_handoff", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class MontageHandoffTests(unittest.TestCase):
    def test_prepare_handoff_writes_job_and_openmontage_files(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            job_dir = root / "bridge-job"
            job_dir.mkdir()
            om_root = root / "OpenMontage"
            project = {
                "job_id": "unit-montage",
                "project_title": "Unit Montage",
                "pipeline_target": "montage",
                "aspect_ratio": "9:16",
                "payload": {
                    "project_title": "Unit Montage",
                    "pipeline_target": "montage",
                    "scenes": [
                        {
                            "id": "scene-001",
                            "title": "Exterior",
                            "asset": "sequence-a/*.jpg",
                            "duration": 7,
                            "vo_seconds": 4.1,
                            "motion": "crossfade plus slow push in",
                            "narration": "Start outside.",
                        },
                        {
                            "id": "scene-002",
                            "title": "Map",
                            "asset": "map-route.png",
                            "duration": 8,
                            "motion": "animated crop",
                            "narration": "Trace the route.",
                        },
                    ],
                },
            }
            project_json = job_dir / "project.json"
            project_json.write_text(json.dumps(project), encoding="utf-8")

            result = mod.prepare_handoff(project_json, om_root)
            om_project = Path(result["openmontage_project_dir"])

            self.assertEqual(result["status"], "handoff_ready")
            self.assertTrue((job_dir / "exports" / "openmontage-handoff.json").exists())
            self.assertTrue((job_dir / "exports" / "editor-handoff.md").exists())
            self.assertTrue((job_dir / "editor-handoff" / "shotcut-notes.txt").exists())
            self.assertTrue((job_dir / "editor-handoff" / "resolve-timeline.csv").exists())
            self.assertTrue((om_project / "storyboard" / "storyboard-handoff.json").exists())
            self.assertTrue((om_project / "editor-handoff" / "editor-handoff.md").exists())
            handoff = json.loads((om_project / "storyboard" / "storyboard-handoff.json").read_text(encoding="utf-8"))
            self.assertEqual(handoff["pipeline_target"], "montage")
            self.assertEqual(handoff["scenes"][1]["start"], 7)


if __name__ == "__main__":
    unittest.main()
