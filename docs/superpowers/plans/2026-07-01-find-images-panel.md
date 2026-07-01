# Find-Images Panel (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-scene "Find images" panel with three isolated sources — Generate (flux), Stock (Pexels), Web (Google image search) — that feed chosen images into the existing Phase 1 approve→render gate.

**Architecture:** Three independent, key-guarded bridge endpoints return one normalized result shape; a pure UMD module (`find-images.js`) turns results into scene assignments; a tabbed panel in the existing UI wires them to the gate. Built in reliability order (Generate → Stock → Web); a missing key or flaky source disables only its own tab.

**Tech Stack:** Python 3.14 stdlib (`http.server`, `urllib.request`, `unittest`), plain browser JS + CommonJS test modules, reuses `scripts/materialize_assets.py` provider plumbing (`choose_provider`, `run_openmontage_provider`, `run_opendesign_provider`).

## Global Constraints

- Platform: Windows. Bridge runs `python scripts/bridge_server.py --host 127.0.0.1 --port 8788`.
- No new third-party dependencies. Python stdlib only; JS plain browser + CommonJS. No bundler, no TypeScript.
- JS files use lowercase-hyphen names (`find-images.js`) and CommonJS (`module.exports`) with browser `window` fallback (UMD).
- All bridge endpoints return JSON. Search endpoints (`/api/search-stock`, `/api/search-web`) ALWAYS respond HTTP 200 with an `{ok: bool, ...}` body (so the UI reads `need_key`/`error` from the body). `/api/generate-image` returns HTTP 200 on success and HTTP 400 `{ok:false,error}` on a bad request (empty prompt / not live).
- The generate endpoint runs an image provider (spends credits / runs a subprocess); gate it behind `STORYBOARD_BRIDGE_LIVE=="1"` exactly like the render/materialize actions. Search endpoints are read-only external GETs and are NOT gated.
- Result shape from every source is identical: `{thumb, full, source_url, credit}` (generate adds `abs`).
- Do NOT change `scripts/materialize_assets.py` or `scripts/render_hyperframes_job.py` behavior; the generate endpoint only imports and calls their existing functions.
- Reuse `storyboard/review-gate.js` semantics: an assigned image sets `reviewState:'needs-review'` so the Phase 1 render lock re-evaluates.

---

## File Structure

- `storyboard/find-images.js` (create) — pure result-normalization + assignment logic (UMD, `window.FindImages`).
- `tests/find_images.test.js` (create) — Node unit tests for `find-images.js`.
- `scripts/bridge_server.py` (modify) — add `generate_one_image`, `search_stock`, `search_web`, a `_load_materialize` helper, three routes, and imports (`sys`, `urllib.request`, `quote`).
- `tests/test_find_images.py` (create) — unittest for the three endpoints with provider/HTTP mocked.
- `storyboard/index.html` (modify) — include `find-images.js`; add a "Find images" button + an empty `#findPanel` container.
- `storyboard/ultimate-workflow.js` (modify) — panel open/close, tab switching, per-source fetch, results grid, pick→assign.

Build order (each independently reviewable): Task 1 (pure module) → Task 2 (generate endpoint) → Task 3 (stock endpoint) → Task 4 (web endpoint) → Task 5 (panel shell + Generate tab) → Task 6 (Stock + Web tabs).

---

## Task 1: Pure result/assignment module

**Files:**
- Create: `storyboard/find-images.js`
- Test: `tests/find_images.test.js`

**Interfaces:**
- Produces (`window.FindImages` in browser, `module.exports` in Node):
  - `parseResults(source, raw) -> [{thumb, full, abs, source_url, credit}]` — `source` is `'generate'|'stock'|'web'`; `raw` is the bridge JSON.
  - `assignPick(scene, pick, source, bridgeBase) -> scene` — returns a scene copy with `assetUrl`, `previewUrl`, `reviewState:'needs-review'`.
  - `defaultQueryForScene(scene) -> string` — initial query/prompt from title+notes+narration.

- [ ] **Step 1: Write the failing test**

Create `tests/find_images.test.js`:

```javascript
const assert = require('assert');
const fi = require('../storyboard/find-images.js');

// parseResults: generate (single image)
const g = fi.parseResults('generate', { ok: true, abs: 'C:\\lib\\img.png', url: '/jobs/_library/x/img.png', provider: 'flux' });
assert.strictEqual(g.length, 1, 'generate yields one result');
assert.strictEqual(g[0].abs, 'C:\\lib\\img.png', 'generate keeps abs');
assert.strictEqual(g[0].full, '/jobs/_library/x/img.png', 'generate full is the jobs url');

// parseResults: stock/web list shape
const s = fi.parseResults('stock', { ok: true, results: [
  { thumb: 't1', full: 'f1', source_url: 'u1', credit: 'c1' },
  { thumb: 't2', full: 'f2' },
] });
assert.strictEqual(s.length, 2, 'stock yields all results');
assert.strictEqual(s[0].full, 'f1', 'stock keeps full');
assert.strictEqual(s[1].credit, '', 'missing credit defaults to empty');

// parseResults: not ok -> empty
assert.deepStrictEqual(fi.parseResults('web', { ok: false, error: 'x' }), [], 'not-ok yields empty');

// assignPick: generate uses abs for assetUrl, base+url for previewUrl
const ag = fi.assignPick({ id: 'a', assetUrl: 'old' }, { abs: 'C:\\lib\\img.png', full: '/jobs/_library/x/img.png' }, 'generate', 'http://127.0.0.1:8788');
assert.strictEqual(ag.assetUrl, 'C:\\lib\\img.png', 'generate assetUrl is local abs');
assert.strictEqual(ag.previewUrl, 'http://127.0.0.1:8788/jobs/_library/x/img.png', 'generate previewUrl is base+url');
assert.strictEqual(ag.reviewState, 'needs-review', 'assign resets review');

// assignPick: stock/web use the external url for both
const aw = fi.assignPick({ id: 'a' }, { full: 'https://ex.com/p.jpg' }, 'web', 'http://127.0.0.1:8788');
assert.strictEqual(aw.assetUrl, 'https://ex.com/p.jpg', 'web assetUrl is external url');
assert.strictEqual(aw.previewUrl, 'https://ex.com/p.jpg', 'web previewUrl is external url');
assert.strictEqual(aw.reviewState, 'needs-review', 'assign resets review');

// defaultQueryForScene
assert.strictEqual(
  fi.defaultQueryForScene({ title: 'Stone doorway', notes: 'hidden', narration: 'A door.' }),
  'Stone doorway hidden A door.',
  'query joins title+notes+narration'
);

console.log('find-images tests passed');
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node tests/find_images.test.js`
Expected: FAIL with `Cannot find module '../storyboard/find-images.js'`

- [ ] **Step 3: Write minimal implementation**

Create `storyboard/find-images.js`:

```javascript
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.FindImages = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  function parseResults(source, raw) {
    if (!raw || !raw.ok) return [];
    if (source === 'generate') {
      return [{
        thumb: String(raw.url || ''),
        full: String(raw.url || ''),
        abs: String(raw.abs || ''),
        source_url: '',
        credit: String(raw.provider || 'generated'),
      }];
    }
    return (raw.results || []).filter(Boolean).map(function (r) {
      return {
        thumb: String(r.thumb || r.full || ''),
        full: String(r.full || r.thumb || ''),
        abs: '',
        source_url: String(r.source_url || ''),
        credit: String(r.credit || ''),
      };
    });
  }

  function assignPick(scene, pick, source, bridgeBase) {
    var base = String(bridgeBase || '');
    var copy = Object.assign({}, scene);
    if (source === 'generate') {
      copy.assetUrl = pick.abs ? pick.abs : (base + pick.full);
      copy.previewUrl = base + pick.full;
    } else {
      copy.assetUrl = pick.full;
      copy.previewUrl = pick.full;
    }
    copy.assetState = 'approved';
    copy.reviewState = 'needs-review';
    return copy;
  }

  function defaultQueryForScene(scene) {
    if (!scene) return '';
    return [scene.title, scene.notes, scene.narration]
      .map(function (s) { return String(s || '').trim(); })
      .filter(Boolean)
      .join(' ')
      .slice(0, 200);
  }

  return {
    parseResults: parseResults,
    assignPick: assignPick,
    defaultQueryForScene: defaultQueryForScene,
  };
}));
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node tests/find_images.test.js`
Expected: `find-images tests passed`

- [ ] **Step 5: Commit**

```bash
git add storyboard/find-images.js tests/find_images.test.js
git commit -m "feat: add pure find-images result/assignment module"
```

---

## Task 2: Bridge `POST /api/generate-image`

**Files:**
- Modify: `scripts/bridge_server.py` (imports near lines 12-23; add helpers before `BridgeHandler`; route in `do_POST`)
- Test: `tests/test_find_images.py`

**Interfaces:**
- Consumes: `materialize_assets.choose_provider`, `.run_openmontage_provider`, `.run_opendesign_provider` (via `_load_materialize`).
- Produces:
  - `_load_materialize() -> module`
  - `generate_one_image(request: dict, jobs_root: Path = DEFAULT_JOBS_ROOT) -> dict` → `{ok, abs, url, provider}` on success; raises `ValueError` on empty prompt; returns `{ok:false,error}` when not live or provider fails.
  - `POST /api/generate-image` route.

- [ ] **Step 1: Write the failing test**

Create `tests/test_find_images.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_find_images.GenerateImageTests -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute '_load_materialize'`

- [ ] **Step 3: Add imports and helpers**

In `scripts/bridge_server.py`, add to the import block (after line 18 `import subprocess`):

```python
import sys
import urllib.request
```

Change the urllib.parse import (line 23) to also bring in `quote`:

```python
from urllib.parse import unquote, quote
```

Add these functions just above the `class BridgeHandler` definition:

```python
def _load_materialize():
    scripts_dir = str(REPO_ROOT / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import materialize_assets
    return materialize_assets


def generate_one_image(request: dict[str, Any], jobs_root: Path = DEFAULT_JOBS_ROOT) -> dict[str, Any]:
    prompt = str(request.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if os.environ.get("STORYBOARD_BRIDGE_LIVE") != "1":
        return {"ok": False, "error": "image generation disabled; start the bridge with STORYBOARD_BRIDGE_LIVE=1"}

    aspect = str(request.get("aspect_ratio") or "9:16")
    mat = _load_materialize()
    provider = mat.choose_provider("auto")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    lib_dir = (jobs_root / "_library" / f"{stamp}-{slugify(prompt)[:24]}")
    lib_dir.mkdir(parents=True, exist_ok=True)
    dest = lib_dir / "image.png"

    if provider == "opendesign":
        ok, err = mat.run_opendesign_provider(prompt, dest, aspect)
    elif provider in {"flux", "openai", "google_imagen", "grok"}:
        ok, err = mat.run_openmontage_provider(provider, prompt, dest, aspect)
    else:
        ok, err = False, "no image provider configured (set FAL_KEY / OPENAI_API_KEY / GOOGLE_API_KEY / XAI_API_KEY)"

    if not ok:
        return {"ok": False, "error": f"generate failed ({provider}): {err}"}

    rel = dest.resolve().relative_to(jobs_root.resolve()).as_posix()
    return {"ok": True, "abs": str(dest.resolve()), "url": f"/jobs/{rel}", "provider": provider}
```

Note: `slugify` already exists in `bridge_server.py`; `datetime` and `DEFAULT_JOBS_ROOT` are already imported/defined.

- [ ] **Step 4: Wire the route**

In `BridgeHandler.do_POST`, extend the allowed paths and dispatch. Change the guard line `if self.path not in {"/api/launch", "/api/asset-upload"}:` to include the new path:

```python
        if self.path not in {"/api/launch", "/api/asset-upload", "/api/generate-image"}:
            self._send_json(404, {"ok": False, "error": "not found"})
            return
```

In the same method's try-block, add a branch (alongside the asset-upload / launch branches):

```python
            elif self.path == "/api/generate-image":
                result = generate_one_image(request, self.jobs_root)
                if not result.get("ok"):
                    self._send_json(400, result)
                    return
```

(The existing `self._send_json(200, result)` at the end of the try covers the success path.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_find_images.GenerateImageTests -v`
Expected: PASS (3 tests). Also run `python -m unittest tests.test_bridge_workflow -v` — still PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add scripts/bridge_server.py tests/test_find_images.py
git commit -m "feat: add generate-image endpoint reusing materialize providers"
```

---

## Task 3: Bridge `GET /api/search-stock` (Pexels)

**Files:**
- Modify: `scripts/bridge_server.py` (add `search_stock`; route in `do_GET`)
- Test: `tests/test_find_images.py`

**Interfaces:**
- Produces:
  - `search_stock(query: str, per_page: int = 15) -> dict` → `{ok:true, results:[{thumb,full,source_url,credit}]}`, or `{ok:false, error, need_key?}`.
  - `GET /api/search-stock?q=...&per_page=...` route (always HTTP 200).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_find_images.py`:

```python
import io
from unittest import mock


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_find_images.SearchStockTests -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'search_stock'`

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/bridge_server.py` (near `generate_one_image`):

```python
def search_stock(query: str, per_page: int = 15) -> dict[str, Any]:
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return {"ok": False, "error": "set PEXELS_API_KEY to enable stock search", "need_key": "PEXELS_API_KEY"}
    if not str(query).strip():
        return {"ok": False, "error": "query is required"}
    url = f"https://api.pexels.com/v1/search?query={quote(query)}&per_page={int(per_page)}"
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": "storyboard-video-studio/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"stock search failed: {exc}"}
    results = []
    for photo in data.get("photos", []):
        src = photo.get("src", {}) if isinstance(photo, dict) else {}
        results.append({
            "thumb": src.get("medium") or src.get("small") or src.get("original") or "",
            "full": src.get("large2x") or src.get("large") or src.get("original") or "",
            "source_url": photo.get("url", "") if isinstance(photo, dict) else "",
            "credit": photo.get("photographer", "") if isinstance(photo, dict) else "",
        })
    return {"ok": True, "results": results}
```

- [ ] **Step 4: Wire the route**

In `BridgeHandler.do_GET`, before the final 404 (after the `/api/job` block), add:

```python
        if self.path.startswith("/api/search-stock"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            query = (qs.get("q") or [""])[0]
            per_page = int((qs.get("per_page") or ["15"])[0] or "15")
            self._send_json(200, search_stock(query, per_page))
            return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_find_images -v`
Expected: PASS (all GenerateImage + SearchStock tests).

- [ ] **Step 6: Commit**

```bash
git add scripts/bridge_server.py tests/test_find_images.py
git commit -m "feat: add Pexels stock search endpoint"
```

---

## Task 4: Bridge `GET /api/search-web` (Google Custom Search)

**Files:**
- Modify: `scripts/bridge_server.py` (add `search_web`; route in `do_GET`)
- Test: `tests/test_find_images.py`

**Interfaces:**
- Produces:
  - `search_web(query: str, num: int = 10) -> dict` → same shape as `search_stock`; needs `GOOGLE_CSE_KEY` + `GOOGLE_CSE_ID`.
  - `GET /api/search-web?q=...&num=...` route (always HTTP 200).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_find_images.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_find_images.SearchWebTests -v`
Expected: FAIL with `AttributeError: module 'bridge_server' has no attribute 'search_web'`

- [ ] **Step 3: Write minimal implementation**

Add to `scripts/bridge_server.py` (near `search_stock`):

```python
def search_web(query: str, num: int = 10) -> dict[str, Any]:
    key = os.environ.get("GOOGLE_CSE_KEY")
    cse = os.environ.get("GOOGLE_CSE_ID")
    if not key or not cse:
        return {"ok": False, "error": "set GOOGLE_CSE_KEY and GOOGLE_CSE_ID to enable web image search", "need_key": "GOOGLE_CSE_KEY,GOOGLE_CSE_ID"}
    if not str(query).strip():
        return {"ok": False, "error": "query is required"}
    url = (
        "https://www.googleapis.com/customsearch/v1"
        f"?key={quote(key)}&cx={quote(cse)}&searchType=image&num={int(num)}&q={quote(query)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "storyboard-video-studio/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": f"web search failed: {exc}"}
    results = []
    for item in data.get("items", []):
        if not isinstance(item, dict):
            continue
        image = item.get("image", {}) if isinstance(item.get("image"), dict) else {}
        results.append({
            "thumb": image.get("thumbnailLink") or item.get("link", ""),
            "full": item.get("link", ""),
            "source_url": image.get("contextLink", ""),
            "credit": item.get("displayLink", ""),
        })
    return {"ok": True, "results": results}
```

- [ ] **Step 4: Wire the route**

In `BridgeHandler.do_GET`, after the `/api/search-stock` block, add:

```python
        if self.path.startswith("/api/search-web"):
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            query = (qs.get("q") or [""])[0]
            num = int((qs.get("num") or ["10"])[0] or "10")
            self._send_json(200, search_web(query, num))
            return
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m unittest tests.test_find_images -v`
Expected: PASS (Generate + Stock + Web). Also `python -m unittest discover -s tests -p "test_*.py"` — all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/bridge_server.py tests/test_find_images.py
git commit -m "feat: add Google Custom Search web image endpoint"
```

---

## Task 5: Find-images panel shell + Generate tab (UI)

**Files:**
- Modify: `storyboard/index.html` (include `find-images.js`; add a "Find images" button + empty `#findPanel`)
- Modify: `storyboard/ultimate-workflow.js` (panel logic + Generate tab)

**Interfaces:**
- Consumes: `window.FindImages` (Task 1); `POST /api/generate-image` (Task 2); existing `state`, `scene()`, `updateScene`, `renderAll`, `q`, `addEvent`, `bridgeUrlInput`.
- Produces: an in-app Generate/Regenerate flow that assigns an image to the current scene as `needs-review`.

- [ ] **Step 1: Add the module include, button, and panel container to `index.html`**

Add immediately before the `<script src="review-gate.js...">` include:

```html
    <script src="find-images.js?v=20260701-1"></script>
```

In the scene inspector, immediately after the element with `id="assetUrlInput"` (the Asset URL field), add a button:

```html
      <button id="findImagesBtn" class="btn" type="button" style="margin-top:8px">Find images</button>
```

Near the end of `<body>` (just before the closing `</body>` or after the main layout container), add an empty panel host:

```html
    <div id="findPanel" hidden style="position:fixed;inset:auto 16px 16px auto;width:460px;max-height:70vh;overflow:auto;background:#161b22;border:1px solid #30363d;border-radius:12px;padding:14px;z-index:50;box-shadow:0 8px 30px rgba(0,0,0,.5)"></div>
```

- [ ] **Step 2: Add the panel logic and Generate tab to `ultimate-workflow.js`**

Add these functions just before the `toggleTheme` definition:

```javascript
    var findState={open:false,tab:'generate',results:[],busy:false};
    function findBase(){return q('bridgeUrlInput').value.trim();}
    function closeFindPanel(){findState.open=false; q('findPanel').hidden=true;}
    function openFindPanel(){findState.open=true; q('findPanel').hidden=false; findState.tab='generate'; findState.results=[]; const s=scene(); findState.query=FindImages.defaultQueryForScene(s); renderFindPanel();}
    function setFindTab(tab){findState.tab=tab; findState.results=[]; renderFindPanel();}
    function pickFindResult(index){const pick=findState.results[index]; if(!pick) return; const patched=FindImages.assignPick(scene(),pick,findState.tab,findBase()); updateScene({assetUrl:patched.assetUrl,previewUrl:patched.previewUrl,assetState:patched.assetState,reviewState:patched.reviewState}); addEvent(`Assigned ${findState.tab} image to ${scene().id}.`); closeFindPanel();}
    async function runGenerate(){const base=findBase(); const prompt=(q('findQuery')?q('findQuery').value:findState.query||'').trim(); if(!prompt){setFindStatus('Enter a prompt first.'); return;} findState.busy=true; setFindStatus('Generating...'); try{const res=await fetch(base+'/api/generate-image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,aspect_ratio:state.project.aspect_ratio})}); const out=await res.json(); findState.busy=false; if(!out.ok){setFindStatus(out.error||'Generate failed.'); return;} findState.results=FindImages.parseResults('generate',out); renderFindResults(); setFindStatus('Generated. Click it to use, or Regenerate.');}catch(err){findState.busy=false; setFindStatus('Generate failed (is the bridge running with STORYBOARD_BRIDGE_LIVE=1?).');}}
    function setFindStatus(msg){const el=q('findStatus'); if(el) el.textContent=msg;}
    function renderFindResults(){const grid=q('findGrid'); if(!grid) return; grid.innerHTML=''; findState.results.forEach((r,i)=>{const cell=document.createElement('button'); cell.type='button'; cell.style.cssText='border:1px solid #30363d;border-radius:8px;overflow:hidden;padding:0;background:#0d1117;cursor:pointer'; cell.innerHTML=`<img src="${r.thumb||r.full}" alt="" style="width:100%;height:120px;object-fit:cover;display:block">`; cell.onclick=()=>pickFindResult(i); grid.appendChild(cell);});}
    function renderFindPanel(){const p=q('findPanel'); if(!p) return; const tabs=['generate','stock','web']; p.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><strong>Find images · ${scene().id}</strong><button type="button" id="findClose" class="btn">Close</button></div><div style="display:flex;gap:6px;margin-bottom:10px">${tabs.map(t=>`<button type="button" class="btn" data-tab="${t}" style="${t===findState.tab?'outline:2px solid #6ca8ff':''}">${t}</button>`).join('')}</div><div style="display:flex;gap:6px;margin-bottom:8px"><input id="findQuery" value="${(findState.query||'').replace(/"/g,'&quot;')}" style="flex:1;padding:8px;border-radius:8px;border:1px solid #30363d;background:#0d1117;color:#e6edf3"><button type="button" id="findGo" class="btn">${findState.tab==='generate'?'Generate':'Search'}</button>${findState.tab==='generate'?'<button type="button" id="findRegen" class="btn">Regenerate</button>':''}</div><div id="findStatus" class="muted" style="font-size:12px;margin-bottom:8px"></div><div id="findGrid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px"></div>`; q('findClose').onclick=closeFindPanel; p.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>setFindTab(b.dataset.tab)); q('findGo').onclick=onFindGo; if(q('findRegen')) q('findRegen').onclick=runGenerate; renderFindResults();}
    function onFindGo(){if(findState.tab==='generate'){runGenerate();}else{setFindStatus('This tab is added in the next step.');}}
```

- [ ] **Step 3: Wire the "Find images" button**

After the existing `q('generateImagesBtn').onclick=...` wiring line, add:

```javascript
    if(q('findImagesBtn')) q('findImagesBtn').onclick=openFindPanel;
```

- [ ] **Step 4: Syntax check + automated suites**

Run (all must be clean/pass):
```bash
node --check storyboard/find-images.js
node --check storyboard/ultimate-workflow.js
node tests/find_images.test.js
node tests/review_gate.test.js
node tests/storyboard_ui_contract.test.js
python -m unittest discover -s tests -p "test_*.py"
```
Expected: syntax clean; all suites pass.

- [ ] **Step 5: Manual smoke (controller-run, live bridge)**

With the bridge on `STORYBOARD_BRIDGE_LIVE=1` and the UI served, open `http://127.0.0.1:8128/`, select a scene, click **Find images** → panel opens on the Generate tab with the scene text pre-filled → click **Generate** → an image appears in the grid → click it → the scene preview updates and the scene shows `needs-review`. Confirm no console errors.

- [ ] **Step 6: Commit**

```bash
git add storyboard/index.html storyboard/ultimate-workflow.js
git commit -m "feat: add find-images panel with Generate/Regenerate tab"
```

---

## Task 6: Stock + Web tabs (UI)

**Files:**
- Modify: `storyboard/ultimate-workflow.js` (add stock/web fetches; replace the `onFindGo` placeholder)

**Interfaces:**
- Consumes: `GET /api/search-stock`, `GET /api/search-web` (Tasks 3-4); `window.FindImages.parseResults`.
- Produces: working Stock and Web tabs in the existing panel.

- [ ] **Step 1: Add the search functions**

In `storyboard/ultimate-workflow.js`, add near `runGenerate`:

```javascript
    async function runSearch(kind){const base=findBase(); const query=(q('findQuery')?q('findQuery').value:'').trim(); if(!query){setFindStatus('Enter a search term first.'); return;} setFindStatus('Searching...'); try{const path=kind==='stock'?'/api/search-stock?q=':'/api/search-web?q='; const res=await fetch(base+path+encodeURIComponent(query)); const out=await res.json(); if(!out.ok){setFindStatus(out.need_key?`Add ${out.need_key} to the bridge environment to enable ${kind} search.`:(out.error||'Search failed.')); findState.results=[]; renderFindResults(); return;} findState.results=FindImages.parseResults(kind,out); renderFindResults(); setFindStatus(findState.results.length?`${findState.results.length} results. Click one to use it.`:'No results.');}catch(err){setFindStatus(`${kind} search failed (is the bridge running?).`);}}
```

- [ ] **Step 2: Replace the `onFindGo` placeholder**

Replace the `onFindGo` function body added in Task 5 with:

```javascript
    function onFindGo(){if(findState.tab==='generate'){runGenerate();}else{runSearch(findState.tab);}}
```

- [ ] **Step 3: Syntax check + automated suites**

Run:
```bash
node --check storyboard/ultimate-workflow.js
python -m unittest discover -s tests -p "test_*.py"
node tests/find_images.test.js
```
Expected: clean + pass.

- [ ] **Step 4: Manual smoke (controller-run)**

With `PEXELS_API_KEY` set on the bridge: open Find images → **Stock** tab → search "mountains" → grid of photos → click one → scene updates to `needs-review`. Without the key, the Stock tab shows "Add PEXELS_API_KEY…" and Generate still works. Same for **Web** with `GOOGLE_CSE_KEY`+`GOOGLE_CSE_ID`.

- [ ] **Step 5: Commit**

```bash
git add storyboard/ultimate-workflow.js
git commit -m "feat: wire Stock and Web tabs in the find-images panel"
```

---

## Self-Review Notes

- **Spec coverage:** three isolated endpoints (Tasks 2,3,4) ✓; identical result shape (`parseResults` Task 1, endpoints Tasks 3-4) ✓; generate reuses materialize providers, no script behavior change (Task 2) ✓; per-tab key guard / graceful degradation (`need_key` in Tasks 3-4, surfaced in Task 6 `runSearch`) ✓; pure module unit-tested (Task 1) ✓; generate not gated to placeholder — returns `{ok:false,error}` on failure (Task 2) ✓; feeds the Phase 1 gate via `reviewState:'needs-review'` (`assignPick` Task 1, applied Task 5) ✓; built Generate→Stock→Web (Tasks 5 then 6) ✓.
- **Open decision resolved:** generated picks live under `bridge-jobs/_library/...` served by the existing `/jobs/` route (`generate_one_image` computes `rel` relative to `jobs_root`, so `resolve_served_job_asset` serves it). `read_job` is per-`job_id` and is unaffected by the `_library` sibling.
- **Live gate:** generate is gated on `STORYBOARD_BRIDGE_LIVE` (Task 2); search endpoints are read-only and ungated (Tasks 3-4), per Global Constraints.
- **Type consistency:** result keys `{thumb, full, abs, source_url, credit}` match across `parseResults` (Task 1) and both search endpoints (Tasks 3-4); `assignPick(scene, pick, source, bridgeBase)` signature matches its call in `pickFindResult` (Task 5); `generate_one_image`/`search_stock`/`search_web` names match their routes and tests.
- **Deferred (per spec):** clips/gifs, audio, cross-job image library.
