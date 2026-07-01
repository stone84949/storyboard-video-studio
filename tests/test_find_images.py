from __future__ import annotations

import importlib.util
import json
import os
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


class GenerateImageTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()
        self._prev_live = os.environ.get("STORYBOARD_BRIDGE_LIVE")
        os.environ["STORYBOARD_BRIDGE_LIVE"] = "1"

    def tearDown(self):
        if self._prev_live is None:
            os.environ.pop("STORYBOARD_BRIDGE_LIVE", None)
        else:
            os.environ["STORYBOARD_BRIDGE_LIVE"] = self._prev_live

    def test_generate_image_writes_and_returns_local_and_url(self):
        mat = self.bridge._load_materialize()
        orig_choose = mat.choose_provider
        orig_gen = mat.run_openmontage_provider
        mat.choose_provider = lambda preferred: "flux"

        def fake_gen(provider, prompt, output_path, aspect_ratio):
            Path(output_path).write_bytes(b"\x89PNG\r\n")
            return True, None

        mat.run_openmontage_provider = fake_gen
        try:
            with tempfile.TemporaryDirectory() as tmp:
                result = self.bridge.generate_one_image(
                    {"prompt": "a stone doorway", "aspect_ratio": "9:16"}, Path(tmp)
                )
                self.assertTrue(result["ok"])
                self.assertTrue(result["url"].startswith("/jobs/_library/"))
                self.assertTrue(Path(result["abs"]).is_file())
                self.assertEqual(result["provider"], "flux")
        finally:
            mat.choose_provider = orig_choose
            mat.run_openmontage_provider = orig_gen

    def test_generate_image_empty_prompt_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self.bridge.generate_one_image({"prompt": "   "}, Path(tmp))

    def test_generate_image_blocked_without_live(self):
        os.environ.pop("STORYBOARD_BRIDGE_LIVE", None)
        with tempfile.TemporaryDirectory() as tmp:
            result = self.bridge.generate_one_image({"prompt": "x"}, Path(tmp))
            self.assertFalse(result["ok"])
            self.assertIn("STORYBOARD_BRIDGE_LIVE", result["error"])


if __name__ == "__main__":
    unittest.main()
