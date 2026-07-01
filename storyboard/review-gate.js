(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ReviewGate = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  function reviewStateFor(scene) {
    if (!scene) return 'needs-review';
    return scene.reviewState || 'needs-review';
  }

  function allApproved(scenes) {
    return Array.isArray(scenes) && scenes.length > 0 &&
      scenes.every(function (s) { return reviewStateFor(s) === 'approved'; });
  }

  function applyMaterializeResult(scenes, result, bridgeBase) {
    var base = String(bridgeBase || '');
    var byId = {};
    ((result && result.scenes) || []).forEach(function (r) { byId[r.scene_id] = r; });
    return (scenes || []).map(function (s) {
      var r = byId[s.id];
      if (!r) return Object.assign({}, s);
      var copy = Object.assign({}, s);
      if (r.image_url) {
        copy.previewUrl = base + r.image_url;
        copy.assetUrl = r.abs ? r.abs : (base + r.image_url);
      }
      copy.reviewState = 'needs-review';
      copy.materializeStatus = r.status || '';
      return copy;
    });
  }

  function markReviewed(scenes, sceneId, stateValue) {
    return (scenes || []).map(function (s) {
      if (s.id !== sceneId) return s;
      var copy = Object.assign({}, s);
      copy.reviewState = stateValue;
      return copy;
    });
  }

  function resetOnSwap(scene) {
    var copy = Object.assign({}, scene);
    copy.reviewState = 'needs-review';
    return copy;
  }

  return {
    reviewStateFor: reviewStateFor,
    allApproved: allApproved,
    applyMaterializeResult: applyMaterializeResult,
    markReviewed: markReviewed,
    resetOnSwap: resetOnSwap,
  };
}));
