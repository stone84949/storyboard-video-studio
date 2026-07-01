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
