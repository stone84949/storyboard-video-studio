# Next Actions

0b. Captions + music (Phase 3b) are live in the finish step. Captions default to karaoke word-highlight (needs `pip install faster-whisper` for word timing; falls back to simple line captions automatically if absent). Music: drop royalty-free tracks into `music/` (gitignored); they're looped and ducked under the narration. Captions ON re-encodes the video (slower). CyberPower one-time: `pip install faster-whisper`.

0. Narration audio (Phase 3) is live. Every HyperFrames/Remotion render now auto-adds
   a spoken narration track via `scripts/add_narration.py` (HyperFrames local Kokoro
   TTS + ffmpeg mux). One-time setup on a new machine (e.g. CyberPower):
   `pip install kokoro-onnx soundfile` (ffmpeg + Node/npx must also be present).
   Voice defaults to `bm_george`; change with `--voice`. Silent render is kept as
   `exports/final-silent.mp4`. If TTS is unavailable the render still succeeds silent.
   Not yet built: background music bed and word-level captions (Phase 3b).

1. Prove one cloud/provider image generation lane once credentials are visible.
   - Current live command is:
     `python scripts/materialize_assets.py <job_dir>/project.json --provider auto`
   - Provider-specific options are `--provider openai`, `--provider google_imagen`, and `--provider grok`.
   - Current shell did not expose `OPENAI_API_KEY`, `GOOGLE_API_KEY` / `GEMINI_API_KEY`, `XAI_API_KEY`, `FAL_KEY`, `PEXELS_API_KEY`, `PIXABAY_API_KEY`, or `UNSPLASH_ACCESS_KEY`, so the proven path is local generated SVG scene art.

2. Upgrade the OpenMontage lane from handoff-ready to render-ready.
   - Current command is:
     `python scripts/prepare_montage_handoff.py <job_dir>/project.json`
   - It writes the OpenMontage project copy and editor/Resolve/Shotcut artifacts.
   - OpenMontage scan confirmed it is pipeline/director driven; there is no single obvious local CLI yet for `storyboard/storyboard-handoff.json`.
   - Next improvement: choose or add the relevant OpenMontage director/render command from the generated handoff package.

3. Decide whether `bridge-jobs/` should be committed as test fixtures or treated as local generated output.
   - Current dry-run folders are left in place for inspection.

4. Mount `storyboard/index.html` into Mission Control or Cabinet once the control-plane route is chosen.
   - Current low-babysitting option is to serve it as static files and keep the bridge API separate.

5. When ready for live execution:
   - Set `STORYBOARD_BRIDGE_LIVE=1` before starting `start-bridge.bat`.
   - Send one short-shorts job with `execute: true`.
   - Inspect `exports/asset-manifest.json`, `logs/execution.log`, `logs/hyperframes-render.log`, `exports/render-summary.json`, and `exports/final.mp4`.

6. Add renderer-level regression tests around `scripts/render_hyperframes_job.py`.
   - Keep the existing bridge/UI tests as fast contract tests.
   - Add one fixture with mocked assets and expected `hyperframes/index.html` plus a mocked CLI invocation.
