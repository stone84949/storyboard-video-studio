(function (global) {
  const DEFAULT_SCENE = {
    title: "New scene",
    asset: "",
    narration: "",
    duration: 3,
    vo_seconds: 3,
    motion: "slow push in",
    notes: "",
    asset_state: "candidate",
  };

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function sceneId(index) {
    return `scene-${String(index + 1).padStart(3, "0")}`;
  }

  function normalizeScene(scene, index) {
    const normalized = { ...DEFAULT_SCENE, ...scene };
    normalized.id = normalized.id || sceneId(index);
    normalized.duration = Number(normalized.duration || normalized.vo_seconds || 3);
    normalized.vo_seconds = Number(normalized.vo_seconds || normalized.duration || 3);
    return normalized;
  }

  function estimateVoSeconds(text, wordsPerSecond = 2.6) {
    const words = String(text || "").trim().split(/\s+/).filter(Boolean).length;
    if (!words) return 0;
    return Math.round(Math.max(1.5, words / wordsPerSecond) * 10) / 10;
  }

  function autoFillVoTiming(scenes) {
    return scenes.map((scene, index) => {
      const next = normalizeScene(scene, index);
      const estimate = estimateVoSeconds(next.narration);
      if (estimate > 0) {
        next.vo_seconds = estimate;
        next.duration = Math.max(Number(next.duration || 0), estimate);
      }
      return next;
    });
  }

  function fitDurations(scenes, targetSeconds) {
    const normalized = scenes.map(normalizeScene);
    const target = Number(targetSeconds || 0);
    const total = normalized.reduce((sum, scene) => sum + Number(scene.duration || 0), 0);
    if (!target || !total) return normalized;
    const ratio = target / total;
    return normalized.map((scene) => ({
      ...scene,
      duration: Math.round(Math.max(Number(scene.vo_seconds || 1.5), Number(scene.duration || 0) * ratio) * 10) / 10,
    }));
  }

  function validateScenes(scenes, options = {}) {
    const errors = [];
    const warnings = [];
    const target = options.pipeline_target || "short-shorts";
    const normalized = scenes.map(normalizeScene);
    if (!normalized.length) errors.push("Add at least one scene.");
    normalized.forEach((scene, index) => {
      const label = scene.id || sceneId(index);
      if (!String(scene.title || "").trim()) errors.push(`${label}: title is required.`);
      if (!String(scene.narration || "").trim()) errors.push(`${label}: narration is required.`);
      if (!String(scene.asset || "").trim()) warnings.push(`${label}: asset filename/path is blank.`);
      if (scene.asset_state === "needs-image") warnings.push(`${label}: asset needs replacement.`);
      if (Number(scene.duration || 0) <= 0) errors.push(`${label}: duration must be greater than 0.`);
      if (Number(scene.duration || 0) < Number(scene.vo_seconds || 0)) warnings.push(`${label}: duration is shorter than VO estimate.`);
    });
    if (target === "short-shorts" && normalized.length > 8) warnings.push("Short shorts should usually stay at 3-8 scenes for fast turnaround.");
    if (target === "longer-shorts" && normalized.length < 6) warnings.push("Longer shorts usually need 6+ scenes for pacing.");
    if (target === "montage" && normalized.some((scene) => !scene.motion)) warnings.push("Montage handoff is stronger when every scene has transition/motion notes.");
    return { ok: errors.length === 0, errors, warnings };
  }

  function buildReplacementPlan(scenes) {
    return scenes.map(normalizeScene).filter((scene) => {
      return !String(scene.asset || "").trim() || scene.asset_state === "needs-image";
    }).map((scene, index) => ({
      scene_id: scene.id,
      title: scene.title,
      reason: !String(scene.asset || "").trim() ? "missing asset" : "asset marked needs-image",
      search_prompt: `${scene.title} ${scene.notes || scene.narration}`.trim(),
      fallback_asset: `generated-fallback-${String(index + 1).padStart(3, "0")}.svg`,
      status: "needs-replacement",
    }));
  }

  function flagBadAssets(scenes) {
    return scenes.map((scene, index) => {
      const next = normalizeScene(scene, index);
      if (!String(next.asset || "").trim()) {
        next.asset_state = "needs-image";
        next.notes = [next.notes, "Auto-flag: asset missing; replace before production render."].filter(Boolean).join(" ");
      }
      return next;
    });
  }

  function moveScene(scenes, fromIndex, toIndex) {
    const next = scenes.map(normalizeScene);
    if (fromIndex < 0 || fromIndex >= next.length || toIndex < 0 || toIndex >= next.length) return next;
    const [scene] = next.splice(fromIndex, 1);
    next.splice(toIndex, 0, scene);
    return next.map((scene, index) => ({ ...scene, id: scene.id || sceneId(index) }));
  }

  function buildExportBundle(state) {
    const scenes = (state.scenes || []).map(normalizeScene);
    return {
      schema_version: "storyboard-video-studio/v1",
      project_title: state.project_title || "Untitled storyboard",
      machine: state.machine || "BEAST",
      engine: state.engine || "dry-run",
      pipeline_target: state.pipeline_target || "short-shorts",
      aspect_ratio: state.aspect_ratio || "9:16",
      style: state.style || "still-image vertical 9:16, slow Ken Burns, documentary mystery",
      target_duration_seconds: Number(state.target_duration_seconds || scenes.reduce((sum, scene) => sum + scene.duration, 0)),
      scenes,
      validation: validateScenes(scenes, state),
      replacement_plan: buildReplacementPlan(scenes),
      created_at: new Date().toISOString(),
    };
  }

  function buildEditorHandoff(bundle) {
    const lines = [
      `# Editor Handoff: ${bundle.project_title}`,
      "",
      `Pipeline: ${bundle.pipeline_target}`,
      `Aspect ratio: ${bundle.aspect_ratio}`,
      `Target duration: ${bundle.target_duration_seconds}s`,
      `Style: ${bundle.style}`,
      "",
      "## Scene timeline",
    ];
    if (bundle.replacement_plan && bundle.replacement_plan.length) {
      lines.push("", "## Asset Replacement Plan");
      bundle.replacement_plan.forEach((item) => {
        lines.push(`- ${item.scene_id}: ${item.reason}; prompt: ${item.search_prompt}; fallback: ${item.fallback_asset}`);
      });
      lines.push("");
    }
    bundle.scenes.forEach((scene, index) => {
      lines.push("", `### ${index + 1}. ${scene.title}`, `- ID: ${scene.id}`, `- Start: ${bundle.scenes.slice(0, index).reduce((sum, s) => sum + Number(s.duration || 0), 0).toFixed(1)}s`, `- Duration: ${scene.duration}s`, `- VO seconds: ${scene.vo_seconds}s`, `- Asset: ${scene.asset || "TBD"}`, `- Asset state: ${scene.asset_state || "candidate"}`, `- Motion: ${scene.motion || "slow Ken Burns"}`, `- Narration: ${scene.narration}`, `- Notes: ${scene.notes || ""}`);
    });
    return lines.join("\n") + "\n";
  }

  const api = { DEFAULT_SCENE, normalizeScene, estimateVoSeconds, autoFillVoTiming, fitDurations, validateScenes, buildReplacementPlan, flagBadAssets, moveScene, buildExportBundle, buildEditorHandoff };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  global.StoryboardStudio = api;

  if (typeof document === "undefined") return;

  let scenes = [
    normalizeScene({ title: "Hook", asset: "archive-mystery-01.jpg", narration: "A forgotten mystery starts with one strange image in the archive.", duration: 3.5 }, 0),
    normalizeScene({ title: "Context", asset: "old-map.jpg", narration: "The trail leads through a place most people have never heard of.", duration: 4.2, motion: "slow pan left" }, 1),
    normalizeScene({ title: "Payoff", asset: "newspaper-clipping.jpg", narration: "And the final clue changes the story completely.", duration: 3.8, motion: "slow push in" }, 2),
  ];

  const els = {
    projectTitle: document.querySelector("#projectTitle"),
    pipelineTarget: document.querySelector("#pipelineTarget"),
    targetDuration: document.querySelector("#targetDuration"),
    bridgeUrl: document.querySelector("#bridgeUrl"),
    executeToggle: document.querySelector("#executeToggle"),
    sceneList: document.querySelector("#sceneList"),
    validationOutput: document.querySelector("#validationOutput"),
    exportOutput: document.querySelector("#exportOutput"),
  };

  function state() {
    return {
      project_title: els.projectTitle.value,
      pipeline_target: els.pipelineTarget.value,
      target_duration_seconds: Number(els.targetDuration.value),
      machine: "BEAST",
      engine: "storyboard-bridge",
      aspect_ratio: "9:16",
      scenes,
    };
  }

  function render() {
    els.sceneList.innerHTML = "";
    scenes.forEach((scene, index) => {
      const card = document.createElement("article");
      card.className = "scene-card";
      card.draggable = true;
      card.dataset.index = String(index);
      card.innerHTML = `
        <div class="scene-head"><strong>${index + 1}. ${scene.title || "Untitled"}</strong><span>${scene.duration}s</span></div>
        <label>Title <input data-field="title" value="${escapeHtml(scene.title)}"></label>
        <label>Asset <input data-field="asset" value="${escapeHtml(scene.asset)}" placeholder="image filename or path"></label>
        <label>Narration <textarea data-field="narration">${escapeHtml(scene.narration)}</textarea></label>
        <label>Duration <input data-field="duration" type="range" min="1" max="20" step="0.1" value="${scene.duration}"><input data-field="duration" type="number" min="0.5" step="0.1" value="${scene.duration}"></label>
        <label>Motion <input data-field="motion" value="${escapeHtml(scene.motion)}"></label>
        <div class="scene-actions"><button data-action="up">Up</button><button data-action="down">Down</button><button data-action="duplicate">Duplicate</button><button data-action="delete">Delete</button></div>`;
      els.sceneList.appendChild(card);
    });
    showValidation(false);
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;" }[char]));
  }

  function showValidation(force = true) {
    const result = validateScenes(scenes, state());
    els.validationOutput.textContent = [
      result.ok ? "PASS: storyboard validation succeeded." : "FAIL: storyboard validation errors found.",
      ...result.errors.map((x) => `ERROR: ${x}`),
      ...result.warnings.map((x) => `WARN: ${x}`),
    ].join("\n");
    els.validationOutput.className = result.ok ? "pass" : "fail";
    if (force) els.validationOutput.scrollIntoView({ block: "nearest" });
    return result;
  }

  function download(filename, text, type = "application/json") {
    const blob = new Blob([text], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  els.sceneList.addEventListener("input", (event) => {
    const card = event.target.closest(".scene-card");
    if (!card) return;
    const index = Number(card.dataset.index);
    const field = event.target.dataset.field;
    const value = event.target.type === "number" || event.target.type === "range" ? Number(event.target.value) : event.target.value;
    scenes[index][field] = value;
    if (field === "duration") scenes[index].vo_seconds = Math.min(scenes[index].vo_seconds || value, value);
    render();
  });

  els.sceneList.addEventListener("click", (event) => {
    const action = event.target.dataset.action;
    if (!action) return;
    const index = Number(event.target.closest(".scene-card").dataset.index);
    if (action === "up") scenes = moveScene(scenes, index, index - 1);
    if (action === "down") scenes = moveScene(scenes, index, index + 1);
    if (action === "duplicate") scenes.splice(index + 1, 0, { ...clone(scenes[index]), id: sceneId(scenes.length) });
    if (action === "delete") scenes.splice(index, 1);
    render();
  });

  els.sceneList.addEventListener("dragstart", (event) => event.dataTransfer.setData("text/plain", event.target.dataset.index));
  els.sceneList.addEventListener("dragover", (event) => event.preventDefault());
  els.sceneList.addEventListener("drop", (event) => {
    event.preventDefault();
    const from = Number(event.dataTransfer.getData("text/plain"));
    const toCard = event.target.closest(".scene-card");
    if (toCard) scenes = moveScene(scenes, from, Number(toCard.dataset.index));
    render();
  });

  document.querySelector("#addScene").addEventListener("click", () => { scenes.push(normalizeScene({ id: sceneId(scenes.length) }, scenes.length)); render(); });
  document.querySelector("#validateScenes").addEventListener("click", () => showValidation(true));
  document.querySelector("#autoVo").addEventListener("click", () => { scenes = autoFillVoTiming(scenes); render(); });
  document.querySelector("#fitDurations").addEventListener("click", () => { scenes = fitDurations(scenes, Number(els.targetDuration.value)); render(); });
  document.querySelector("#exportBundle").addEventListener("click", () => {
    const bundle = buildExportBundle(state());
    els.exportOutput.textContent = JSON.stringify(bundle, null, 2);
    download(`${bundle.project_title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-storyboard-bundle.json`, JSON.stringify(bundle, null, 2));
  });
  document.querySelector("#editorHandoff").addEventListener("click", () => {
    const handoff = buildEditorHandoff(buildExportBundle(state()));
    els.exportOutput.textContent = handoff;
    download("editor-handoff.md", handoff, "text/markdown");
  });
  document.querySelector("#sendBridge").addEventListener("click", async () => {
    const bundle = buildExportBundle(state());
    const request = { machine: "BEAST", engine: "storyboard-ui", run_label: bundle.project_title, execute: false, payload: bundle };
    const response = await fetch(`${els.bridgeUrl.value.replace(/\/$/, "")}/api/launch`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
    els.exportOutput.textContent = JSON.stringify(await response.json(), null, 2);
  });
  document.querySelector("#sendExecute").addEventListener("click", async () => {
    const bundle = buildExportBundle(state());
    const request = { machine: "BEAST", engine: "storyboard-ui", run_label: bundle.project_title, execute: Boolean(els.executeToggle.checked), payload: bundle };
    const response = await fetch(`${els.bridgeUrl.value.replace(/\/$/, "")}/api/launch`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request) });
    els.exportOutput.textContent = JSON.stringify(await response.json(), null, 2);
  });

  render();
})(typeof window !== "undefined" ? window : globalThis);
