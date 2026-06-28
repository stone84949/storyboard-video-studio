const assert = require('assert');
const studio = require('../storyboard/storyboard.js');

const sampleScenes = [
  { id: 'a', title: 'Hook', narration: 'A strange archive photo starts the mystery.', duration: 1, asset: 'archive.jpg', motion: 'slow push in' },
  { id: 'b', title: 'Reveal', narration: 'The second clue points to an abandoned lab outside town.', duration: 1, asset: 'lab.jpg', motion: 'slow pan right' },
];

const moved = studio.moveScene(sampleScenes, 0, 1);
assert.strictEqual(moved[0].id, 'b', 'scene reorder should move first scene after second');

const timed = studio.autoFillVoTiming(sampleScenes);
assert(timed[0].vo_seconds > 0, 'VO auto-fill should set estimated seconds');
assert(timed[0].duration >= timed[0].vo_seconds, 'VO auto-fill should not leave duration shorter than VO');

const fit = studio.fitDurations(timed, 16);
assert(fit.reduce((sum, scene) => sum + scene.duration, 0) >= 16, 'fit durations should scale toward target without undercutting VO');

const valid = studio.validateScenes(fit, { pipeline_target: 'short-shorts' });
assert.strictEqual(valid.ok, true, 'valid sample scenes should pass');

const invalid = studio.validateScenes([{ title: '', narration: '', duration: 0 }]);
assert.strictEqual(invalid.ok, false, 'missing narration/title/duration should fail validation');

const flagged = studio.flagBadAssets([{ title: 'Missing asset', narration: 'Needs a replacement image.', duration: 2, asset: '' }]);
assert.strictEqual(flagged[0].asset_state, 'needs-image', 'missing assets should be flagged for replacement');
const replacementPlan = studio.buildReplacementPlan(flagged);
assert.strictEqual(replacementPlan.length, 1, 'replacement plan should include flagged image');
assert(replacementPlan[0].search_prompt.includes('Missing asset'), 'replacement plan should include a useful prompt');

const bundle = studio.buildExportBundle({ project_title: 'Unit Export', pipeline_target: 'montage', scenes: fit, target_duration_seconds: 16 });
assert.strictEqual(bundle.pipeline_target, 'montage', 'bundle should preserve target');
assert.strictEqual(bundle.aspect_ratio, '9:16', 'bundle should default to vertical 9:16');
assert.strictEqual(bundle.scenes.length, 2, 'bundle should include scenes');

const handoff = studio.buildEditorHandoff(bundle);
assert(handoff.includes('# Editor Handoff: Unit Export'), 'handoff should include title');
assert(handoff.includes('Pipeline: montage'), 'handoff should include pipeline');
assert(handoff.includes('- Start: 0.0s'), 'handoff should include scene timeline placement');

console.log('storyboard UI contract tests passed');
