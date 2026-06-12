/**
 * Shell dùng chung: menu, header, footer, modal nhập dữ liệu, thống kê sidebar.
 */
(function (global) {
  const ROUTES = {
    overview: '/',
    simulation: '/simulation',
    recommendations: '/recommendations',
    topnodes: '/#dash-top-table',
    communities: '/#dash-communities',
    risk: '/#dash-top-table',
  };

  const ACTIVE_OUTPUT_KEY = 'mau_active_output_dir';

  function getActiveOutputDir() {
    try {
      return String(localStorage.getItem(ACTIVE_OUTPUT_KEY) || '').trim() || '';
    } catch {
      return '';
    }
  }

  function setActiveOutputDir(dirNameOrPath) {
    try {
      const v = String(dirNameOrPath || '').trim();
      if (!v) localStorage.removeItem(ACTIVE_OUTPUT_KEY);
      else localStorage.setItem(ACTIVE_OUTPUT_KEY, v);
    } catch {
      /* ignore */
    }
  }

  function withOutputDir(url) {
    const out = getActiveOutputDir();
    if (!out) return url;
    if (String(url).includes('output_dir=')) return url;
    const sep = String(url).includes('?') ? '&' : '?';
    return `${url}${sep}output_dir=${encodeURIComponent(out)}`;
  }

  function toast(msg, ms = 3200) {
    const el = document.createElement('div');
    el.className = 'toast-msg';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  function invalidatePageCaches(outputDir) {
    if (global.MauSessionCache) {
      if (outputDir) global.MauSessionCache.invalidate(outputDir);
      else global.MauSessionCache.invalidateAll();
    }
  }

  async function fetchSummaryCached(force) {
    const out = getActiveOutputDir();
    if (!force && global.MauSessionCache) {
      const cached = global.MauSessionCache.get(global.MauSessionCache.KIND.SUMMARY, out);
      if (cached) return cached;
    }
    const data = await fetchJson('/api/summary');
    global.MauSessionCache?.set(global.MauSessionCache.KIND.SUMMARY, out, data);
    return data;
  }

  async function fetchJson(path, options) {
    const res = await fetch(withOutputDir(path), options);
    let body = {};
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    if (!res.ok) {
      const msg = body.error || body.hint || (body.message ? String(body.message) : '');
      throw new Error(msg ? `${msg}` : `HTTP ${res.status} — xem Logs trên Render`);
    }
    return body;
  }

  function formatNumber(n) {
    const x = Number(n);
    if (!Number.isFinite(x)) return null;
    return x.toLocaleString('vi-VN');
  }

  function outputFolderNameFromApi(value) {
    const s = String(value || '').trim();
    if (!s) return '';
    return s.replace(/\\/g, '/').split('/').filter(Boolean).pop() || s;
  }

  function formatDisplayDate(raw) {
    if (!raw) return null;
    const s = String(raw).trim();
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return s;
  }

  function openModal() {
    document.getElementById('dataGenModal')?.classList.add('open');
    void refreshDatasetsList();
  }

  function closeModal() {
    document.getElementById('dataGenModal')?.classList.remove('open');
  }

  async function runGenerator(onDataReady) {
    const btn = document.getElementById('btnConfirmGenerate');
    const orig = btn?.textContent;
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Đang tạo...';
    }
    try {
      const payload = {
        num_users: parseInt(document.getElementById('numUsers').value, 10),
        relationship_prob: parseFloat(document.getElementById('relationshipProb').value),
        seed: parseInt(document.getElementById('randomSeed').value, 10),
      };
      const data = await fetchJson('/api/run-generator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const folderName = outputFolderNameFromApi(data.output_folder);
      invalidatePageCaches();
      if (folderName) setActiveOutputDir(folderName);
      closeModal();
      toast('Tạo dữ liệu thành công.');
      await refreshSideStats(true);
      if (typeof onDataReady === 'function') await onDataReady();
      if (typeof global.onSharedDataReady === 'function') await global.onSharedDataReady();
    } catch (e) {
      toast('Lỗi: ' + e.message, 5000);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = orig;
      }
    }
  }

  async function uploadCsv(onDataReady) {
    const file = document.getElementById('dataFile')?.files?.[0];
    if (!file) {
      toast('Chọn file CSV.');
      return;
    }
    const fd = new FormData();
    fd.append('file', file);
    try {
      const data = await fetchJson('/api/upload-data', { method: 'POST', body: fd });
      const folderName = outputFolderNameFromApi(data.output_folder);
      invalidatePageCaches();
      if (folderName) setActiveOutputDir(folderName);
      closeModal();
      toast('Tải lên thành công.');
      await refreshSideStats(true);
      if (typeof onDataReady === 'function') await onDataReady();
      if (typeof global.onSharedDataReady === 'function') await global.onSharedDataReady();
    } catch (e) {
      toast('Lỗi upload: ' + e.message, 5000);
    }
  }

  function confirmData(onDataReady) {
    const src = document.getElementById('dataSource')?.value;
    if (src === 'upload') uploadCsv(onDataReady);
    else runGenerator(onDataReady);
  }

  async function cleanupOldOutputs(onDataReady) {
    const ok = window.confirm(
      'Chỉ giữ bộ dữ liệu mạng mới nhất, xóa các output cũ và xóa hết kết quả mô phỏng SIR đã lưu?'
    );
    if (!ok) return;

    const btn = document.getElementById('btnCleanupOutputs');
    const orig = btn?.textContent;
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Đang dọn...';
    }
    try {
      const result = await fetchJson('/api/cleanup-outputs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keep_latest: 1, include_uploaded: true, clear_simulations: true }),
      });
      const n = Number(result.removed_count) || 0;
      const sim = Number(result.cleared_simulation_roots) || 0;
      let msg = 'Đã dọn xong.';
      if (n > 0) msg += ` Xóa ${n} bộ output cũ.`;
      if (sim > 0) msg += ` Xóa ${sim} nhóm kết quả mô phỏng.`;
      if (n === 0 && sim === 0) msg = 'Không có output hoặc mô phỏng cũ để xóa.';
      toast(msg);
      invalidatePageCaches();
      await refreshSideStats(true);
      if (typeof onDataReady === 'function') await onDataReady();
      if (typeof global.onSharedDataReady === 'function') await global.onSharedDataReady();
    } catch (e) {
      toast('Không thể dọn output cũ: ' + e.message, 5000);
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = orig;
      }
    }
  }

  async function refreshSideStats(force) {
    try {
      const data = await fetchSummaryCached(!!force);
      const ready = data.ready !== false && (Number(data.nodes) || 0) > 0;
      const set = (id, v) => {
        const el = document.getElementById(id);
        if (el && ready && v != null) el.textContent = v;
      };
      set('sideStatNodes', formatNumber(data.nodes));
      set('sideStatEdges', formatNumber(data.edges));
      set('sideStatDate', formatDisplayDate(data.data_date));
      const ft = document.getElementById('footerTimestamp');
      if (ft && data.timestamp) ft.textContent = data.timestamp;
      return data;
    } catch {
      return null;
    }
  }

  function setActiveNav(page) {
    document.querySelectorAll('.nav-menu .nav-item').forEach((el) => {
      const key = el.getAttribute('data-mau-nav');
      el.classList.toggle('active', key === page);
    });
  }

  function bindNavigation(page, onDataReady) {
    document.querySelectorAll('.nav-menu .nav-item[data-mau-nav]').forEach((el) => {
      const key = el.getAttribute('data-mau-nav');
      el.addEventListener('click', () => {
        if (key === 'data') {
          openModal();
          return;
        }
        const href = ROUTES[key];
        if (href) {
          if (href.startsWith('/#') && page === 'overview') {
            const id = href.slice(1);
            document.querySelector(id)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          } else {
            window.location.href = href;
          }
        }
      });
    });
    setActiveNav(page);
  }

  function bindLangToggle() {
    const btn = document.getElementById('langToggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      if (window.I18N) {
        window.I18N.toggleLang();
      }
    });
  }

  function bindHeader() {
    const page = document.body.getAttribute('data-mau-page') || '';
    if (page !== 'simulation') {
      document.getElementById('btnReport')?.addEventListener('click', () => {
        toast('Phiên bản và thời gian cập nhật ở chân trang.');
      });
    }
    bindLangToggle();
  }

  function bindModal(onDataReady) {
    document.getElementById('menuOpenData')?.addEventListener('click', openModal);
    document.getElementById('modalClose')?.addEventListener('click', closeModal);
    document.getElementById('modalCancel')?.addEventListener('click', closeModal);
    document.getElementById('btnConfirmGenerate')?.addEventListener('click', () => confirmData(onDataReady));
    document.getElementById('btnUseExistingOutput')?.addEventListener('click', async () => {
      const sel = document.getElementById('existingOutputSelect');
      const v = sel?.value;
      if (!v) {
        toast('Chọn một output có sẵn.');
        return;
      }
      const prev = getActiveOutputDir();
      setActiveOutputDir(v);
      if (prev && prev !== v) invalidatePageCaches(prev);
      closeModal();
      toast('Đã chọn bộ dữ liệu cũ.');
      await refreshSideStats(true);
      if (typeof onDataReady === 'function') await onDataReady();
      if (typeof global.onSharedDataReady === 'function') await global.onSharedDataReady();
    });
    document.getElementById('dataSource')?.addEventListener('change', function () {
      const g = document.getElementById('fileUploadGroup');
      if (g) g.style.display = this.value === 'upload' ? 'block' : 'none';
    });
    document.getElementById('dataGenModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'dataGenModal') closeModal();
    });
  }

  async function applyServerConfig() {
    try {
      const cfg = await fetchJson('/api/config');
      const nu = document.getElementById('numUsers');
      const maxU = Number(cfg.max_users) || 10000;
      if (nu) {
        nu.max = String(maxU);
        if (parseInt(nu.value, 10) > maxU) nu.value = String(Math.min(maxU, 3000));
      }
      document.body.dataset.skipGraphViz = cfg.skip_graph_viz ? '1' : '0';
      return cfg;
    } catch {
      return null;
    }
  }

  function formatDatasetLabel(row) {
    if (!row) return '—';
    const n = Number(row.nodes);
    const e = Number(row.edges);
    const ne =
      Number.isFinite(n) && Number.isFinite(e) ? ` — ${n} nút / ${e} cạnh` : '';
    return `${row.name || 'output'}${ne}`;
  }

  async function refreshDatasetsList() {
    const sel = document.getElementById('existingOutputSelect');
    const btn = document.getElementById('btnUseExistingOutput');
    if (!sel || !btn) return;
    btn.disabled = true;
    try {
      const data = await fetchJson('/api/output-datasets?include_uploaded=1');
      const list = Array.isArray(data.datasets) ? data.datasets : [];
      sel.replaceChildren();
      const opt0 = document.createElement('option');
      opt0.value = '';
      opt0.textContent = window.I18N ? window.I18N.t('dashboard.modalReusePlaceholder') : '— Chọn output đã có —';
      sel.appendChild(opt0);
      list.forEach((row) => {
        const opt = document.createElement('option');
        opt.value = row.name;
        opt.textContent = formatDatasetLabel(row);
        sel.appendChild(opt);
      });
      const cur = getActiveOutputDir();
      if (cur) sel.value = cur;
    } catch {
      /* ignore */
    } finally {
      btn.disabled = false;
    }
  }

  function init(options = {}) {
    const page = options.page || document.body.getAttribute('data-mau-page') || 'overview';
    const onDataReady = options.onDataReady;
    bindNavigation(page, onDataReady);
    bindHeader();
    bindModal(onDataReady);
    document.getElementById('btnCleanupOutputs')?.addEventListener('click', () => cleanupOldOutputs(onDataReady));
    applyServerConfig();
    refreshSideStats();
    if (window.I18N) {
      window.I18N.applyI18n();
      window.addEventListener('app:langchange', () => {
        window.I18N.applyI18n();
        void refreshDatasetsList();
      });
    }
    if (page === 'overview' && window.location.hash) {
      const el = document.querySelector(window.location.hash);
      if (el) setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 200);
    }
    return { refreshSideStats, toast, openModal, closeModal };
  }

  global.MauShell = {
    init,
    toast,
    openModal,
    closeModal,
    refreshSideStats,
    fetchSummaryCached,
    invalidatePageCaches,
    cleanupOldOutputs,
    ROUTES,
    getActiveOutputDir,
    setActiveOutputDir,
    withOutputDir,
    fetchJson,
  };
})(typeof window !== 'undefined' ? window : global);
