const assert = require('assert');
const gate = require('../storyboard/review-gate.js');

// allApproved
assert.strictEqual(gate.allApproved([]), false, 'empty is not approved');
assert.strictEqual(
  gate.allApproved([{ id: 'a', reviewState: 'approved' }, { id: 'b', reviewState: 'needs-review' }]),
  false,
  'one pending blocks approval'
);
assert.strictEqual(
  gate.allApproved([{ id: 'a', reviewState: 'approved' }, { id: 'b', reviewState: 'approved' }]),
  true,
  'all approved passes'
);

// applyMaterializeResult
const applied = gate.applyMaterializeResult(
  [{ id: 'a', assetUrl: 'old' }],
  { scenes: [{ scene_id: 'a', image_url: '/jobs/j/assets/001.png', abs: 'C:\\jobs\\j\\assets\\001.png', status: 'generated' }] },
  'http://127.0.0.1:8788'
);
assert.strictEqual(applied[0].previewUrl, 'http://127.0.0.1:8788/jobs/j/assets/001.png', 'preview url set');
assert.strictEqual(applied[0].assetUrl, 'C:\\jobs\\j\\assets\\001.png', 'asset url uses local abs path for render fidelity');
assert.strictEqual(applied[0].reviewState, 'needs-review', 'materialized scenes need review');
assert.strictEqual(applied[0].materializeStatus, 'generated', 'status carried through');

// markReviewed
const marked = gate.markReviewed(applied, 'a', 'approved');
assert.strictEqual(marked[0].reviewState, 'approved', 'approve sets state');

// resetOnSwap
assert.strictEqual(gate.resetOnSwap({ id: 'a', reviewState: 'approved' }).reviewState, 'needs-review', 'swap resets review');

// reviewStateFor
assert.strictEqual(gate.reviewStateFor({ id: 'x' }), 'needs-review', 'default review state');
assert.strictEqual(gate.reviewStateFor({ id: 'x', reviewState: 'flagged' }), 'flagged', 'explicit review state passes through');

// gate transition: generate -> approve -> render-unlock -> swap -> relock
let gateScenes = [{ id: 'a', assetUrl: 'old-a' }, { id: 'b', assetUrl: 'old-b' }];
gateScenes = gate.applyMaterializeResult(
  gateScenes,
  {
    scenes: [
      { scene_id: 'a', image_url: '/jobs/j/assets/001.png', abs: 'C:\\jobs\\j\\assets\\001.png', status: 'generated' },
      { scene_id: 'b', image_url: '/jobs/j/assets/002.png', abs: 'C:\\jobs\\j\\assets\\002.png', status: 'generated' },
    ],
  },
  'http://127.0.0.1:8788'
);
assert.strictEqual(gate.allApproved(gateScenes), false, 'freshly generated scenes are not all approved');

gateScenes = gate.markReviewed(gateScenes, 'a', 'approved');
gateScenes = gate.markReviewed(gateScenes, 'b', 'approved');
assert.strictEqual(gate.allApproved(gateScenes), true, 'approving every scene unlocks render');

const swappedA = gate.resetOnSwap(gateScenes.find(function (s) { return s.id === 'a'; }));
gateScenes = gateScenes.map(function (s) { return s.id === 'a' ? swappedA : s; });
assert.strictEqual(gate.allApproved(gateScenes), false, 'swapping an approved scene relocks render');

console.log('review-gate tests passed');
