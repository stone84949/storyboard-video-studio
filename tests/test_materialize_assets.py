from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
MATERIALIZE_PATH = REPO_ROOT / "scripts" / "materialize_assets.py"


def load_materializer():
    spec = importlib.util.spec_from_file_location("materialize_assets", MATERIALIZE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class MaterializeAssetsTests(unittest.TestCase):
    def test_local_provider_writes_assets_manifest_and_updates_project(self):
        materializer = load_materializer()
        with tempfile.TemporaryDirectory() as tmp:
            job_dir = Path(tmp)
            project_path = job_dir / "project.json"
            project_path.write_text(
                json.dumps(
                    {
                        "job_id": "unit-materialize",
                        "pipeline_target": "short-shorts",
                        "project_title": "Materialize Unit",
                        "payload": {
                            "scenes": [
                                {
                                    "id": "scene-001",
                                    "title": "Missing image",
                                    "asset": "",
                                    "asset_state": "needs-image",
                                    "narration": "The missing image gets generated locally.",
                                },
                                {
                                    "id": "scene-002",
                                    "title": "Flagged image",
                                    "asset": "bad-remote.jpg",
                                    "status": "flagged",
                                    "narration": "The flagged image gets replaced.",
                                },
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            manifest = materializer.materialize(project_path, provider="local", style="test style", fallback=True)

            self.assertTrue((job_dir / "exports" / "asset-manifest.json").exists())
            self.assertEqual(len(manifest["assets"]), 2)
            self.assertTrue(all(item["status"] == "local-generated" for item in manifest["assets"]))
            for item in manifest["assets"]:
                self.assertTrue((job_dir / item["asset"]).exists())

            updated = json.loads(project_path.read_text(encoding="utf-8"))
            scenes = updated["payload"]["scenes"]
            self.assertEqual(scenes[0]["asset_state"], "materialized")
            self.assertTrue(scenes[0]["asset"].endswith(".svg"))
            self.assertTrue(updated["asset_materialization"]["manifest"].endswith("asset-manifest.json"))


if __name__ == "__main__":
    unittest.main()
