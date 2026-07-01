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
  { scenes: [{ scene_id: 'a', image_url: '/jobs/j/assets/001.png', status: 'generated' }] },
  'http://127.0.0.1:8788'
);
assert.strictEqual(applied[0].previewUrl, 'http://127.0.0.1:8788/jobs/j/assets/001.png', 'preview url set');
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

console.log('review-gate tests passed');
