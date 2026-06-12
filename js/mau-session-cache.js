/**
 * Cache sessionStorage giữa các trang — tránh fetch + render lại toàn bộ khi điều hướng.
 */
(function (global) {
  const PREFIX = 'mau_cache_v1';
  const TTL_MS = 30 * 60 * 1000;

  const KIND = {
    SUMMARY: 'summary',
    GRAPH: 'graph',
    RECOMMENDATIONS: 'recommendations',
    SIR: 'sir',
  };

  function outputKey(outputDir) {
    const s = String(outputDir || '').trim();
    return s || '__latest__';
  }

  function storageKey(kind, outputDir) {
    return `${PREFIX}:${kind}:${outputKey(outputDir)}`;
  }

  function get(kind, outputDir) {
    try {
      const raw = sessionStorage.getItem(storageKey(kind, outputDir));
      if (!raw) return null;
      const entry = JSON.parse(raw);
      if (!entry || typeof entry.ts !== 'number' || Date.now() - entry.ts > TTL_MS) {
        sessionStorage.removeItem(storageKey(kind, outputDir));
        return null;
      }
      return entry.data ?? null;
    } catch {
      return null;
    }
  }

  function set(kind, outputDir, data) {
    try {
      sessionStorage.setItem(
        storageKey(kind, outputDir),
        JSON.stringify({ ts: Date.now(), data })
      );
      return true;
    } catch {
      return false;
    }
  }

  function remove(kind, outputDir) {
    try {
      sessionStorage.removeItem(storageKey(kind, outputDir));
    } catch {
      /* ignore */
    }
  }

  function invalidate(outputDir) {
    const suffix = `:${outputKey(outputDir)}`;
    try {
      const keys = [];
      for (let i = 0; i < sessionStorage.length; i += 1) {
        const k = sessionStorage.key(i);
        if (k && k.startsWith(PREFIX + ':') && k.endsWith(suffix)) keys.push(k);
      }
      keys.forEach((k) => sessionStorage.removeItem(k));
    } catch {
      /* ignore */
    }
  }

  function invalidateAll() {
    try {
      const keys = [];
      for (let i = 0; i < sessionStorage.length; i += 1) {
        const k = sessionStorage.key(i);
        if (k && k.startsWith(PREFIX + ':')) keys.push(k);
      }
      keys.forEach((k) => sessionStorage.removeItem(k));
    } catch {
      /* ignore */
    }
  }

  global.MauSessionCache = {
    KIND,
    TTL_MS,
    get,
    set,
    remove,
    invalidate,
    invalidateAll,
    outputKey,
  };
})(typeof window !== 'undefined' ? window : global);
