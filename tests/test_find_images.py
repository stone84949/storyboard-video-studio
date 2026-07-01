from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class SearchStockTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()

    def test_missing_key_returns_need_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PEXELS_API_KEY", None)
            out = self.bridge.search_stock("mountains")
            self.assertFalse(out["ok"])
            self.assertEqual(out["need_key"], "PEXELS_API_KEY")

    def test_returns_normalized_results(self):
        fake = json.dumps({"photos": [
            {"src": {"medium": "m1", "large2x": "l1"}, "url": "u1", "photographer": "Ann"},
            {"src": {"small": "s2", "large": "l2"}, "url": "u2", "photographer": "Bo"},
        ]}).encode("utf-8")

        class FakeResp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch.dict(os.environ, {"PEXELS_API_KEY": "k"}, clear=False):
            with mock.patch.object(self.bridge.urllib.request, "urlopen", return_value=FakeResp(fake)):
                out = self.bridge.search_stock("mountains")
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["results"]), 2)
        self.assertEqual(out["results"][0]["thumb"], "m1")
        self.assertEqual(out["results"][0]["full"], "l1")
        self.assertEqual(out["results"][0]["credit"], "Ann")
        self.assertEqual(out["results"][1]["full"], "l2")


class SearchWebTests(unittest.TestCase):
    def setUp(self):
        self.bridge = load_bridge()

    def test_missing_keys_returns_need_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_CSE_KEY", None)
            os.environ.pop("GOOGLE_CSE_ID", None)
            out = self.bridge.search_web("kaharumi site")
            self.assertFalse(out["ok"])
            self.assertIn("GOOGLE_CSE_KEY", out["need_key"])

    def test_returns_normalized_results(self):
        fake = json.dumps({"items": [
            {"link": "https://ex.com/a.jpg", "displayLink": "ex.com",
             "image": {"thumbnailLink": "https://ex.com/a_t.jpg", "contextLink": "https://ex.com/page"}},
        ]}).encode("utf-8")

        class FakeResp(io.BytesIO):
            def __enter__(self):
                return self
            def __exit__(self, *a):
                return False

        with mock.patch.dict(os.environ, {"GOOGLE_CSE_KEY": "k", "GOOGLE_CSE_ID": "cx"}, clear=False):
            with mock.patch.object(self.bridge.urllib.request, "urlopen", return_value=FakeResp(fake)):
                out = self.bridge.search_web("kaharumi site")
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["results"]), 1)
        self.assertEqual(out["results"][0]["thumb"], "https://ex.com/a_t.jpg")
        self.assertEqual(out["results"][0]["full"], "https://ex.com/a.jpg")
        self.assertEqual(out["results"][0]["source_url"], "https://ex.com/page")
        self.assertEqual(out["results"][0]["credit"], "ex.com")


if __name__ == "__main__":
    unittest.main()
