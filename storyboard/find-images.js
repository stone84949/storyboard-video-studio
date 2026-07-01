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
