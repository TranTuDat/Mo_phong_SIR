/**
 * Shell chung: theme, ngôn ngữ, modal nhập dữ liệu, dọn output.
 * Trang tổng quan (script.js) tự xử lý — không gọi SharedNav.init.
 */
(function (global) {
  function t(key, vars) {
    return global.I18N && global.I18N.t ? global.I18N.t(key, vars) : key;
  }

  function toast(message, variant, timeoutMs) {
    const ms = timeoutMs ?? 3800;
    let root = document.getElementById('toastRoot');
    if (!root) {
      root = document.createElement('div');
      root.id = 'toastRoot';
      root.className = 'toast-root';
      document.body.appendChild(root);
    }
    const item = document.createElement('div');
    item.className = `toast toast-${variant || 'info'}`;
    item.textContent = message;
    root.appendChild(item);
    window.setTimeout(() => {
      item.classList.add('toast-hide');
      window.setTimeout(() => item.remove(), 220);
    }, ms);
  }

  function showError(message) {
    toast(message, 'error', 5200);
    console.error(message);
  }

  function initTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
    global.I18N?.applyI18n?.();
  }

  function openDataGenModal() {
    const modal = document.getElementById('dataGenModal');
    if (!modal) return;
    modal.classList.add('show');
    initDataGenForm();
  }

  function closeDataGenModal() {
    document.getElementById('dataGenModal')?.classList.remove('show');
  }

  function toggleFileUpload(show) {
    const fileGroup = document.getElementById('fileUploadGroup');
    if (fileGroup) fileGroup.style.display = show ? 'grid' : 'none';
  }

  function initDataGenForm() {
    const nu = document.getElementById('numUsers');
    const rp = document.getElementById('relationshipProb');
    const rs = document.getElementById('randomSeed');
    const ds = document.getElementById('dataSource');
    if (nu) nu.value = 500;
    if (rp) rp.value = 0.025;
    if (rs) rs.value = 42;
    if (ds) {
      ds.value = 'generate';
      ds.onchange = function () {
        toggleFileUpload(this.value === 'upload');
      };
    }
    toggleFileUpload(false);
    const btn = document.getElementById('btnConfirmGenerate');
    if (btn) btn.onclick = handleDataGeneration;
  }

  async function refreshAfterDataChange() {
    if (typeof global.loadDashboard === 'function') {
      await global.loadDashboard();
      return;
    }
    if (typeof global.onSharedDataReady === 'function') {
      try {
        await global.onSharedDataReady();
      } catch (e) {
        console.warn(e);
      }
      return;
    }
    global.location.reload();
  }

  async function runGenerator() {
    const numUsers = parseInt(document.getElementById('numUsers')?.value, 10);
    const relationshipProb = parseFloat(document.getElementById('relationshipProb')?.value);
    const seed = parseInt(document.getElementById('randomSeed')?.value, 10);
    const btn = document.getElementById('btnConfirmGenerate');
    const originalText = btn ? btn.textContent || t('dashboard.confirmGen') : t('dashboard.confirmGen');
    if (btn) {
      btn.textContent = t('msgs.processing');
      btn.disabled = true;
    }
    try {
      const response = await fetch('/api/run-generator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          num_users: numUsers,
          relationship_prob: relationshipProb,
          seed,
        }),
      });
      let errBody = {};
      try {
        errBody = await response.json();
      } catch {
        /* ignore */
      }
      if (!response.ok) throw new Error(errBody.error || `HTTP ${response.status}`);
      await refreshAfterDataChange();
      toast(t('toast.generated'), 'success');
    } catch (error) {
      showError(t('msgs.errGen') + ' ' + error.message);
    } finally {
      if (btn) {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    }
  }

  async function uploadAndProcessFile() {
    const fileInput = document.getElementById('dataFile');
    const file = fileInput?.files?.[0];
    if (!file) {
      showError(t('msgs.pickCsv'));
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    const btn = document.getElementById('btnConfirmGenerate');
    const originalText = btn ? btn.textContent || t('dashboard.confirmGen') : t('dashboard.confirmGen');
    if (btn) {
      btn.textContent = t('msgs.processing');
      btn.disabled = true;
    }
    try {
      const response = await fetch('/api/upload-data', { method: 'POST', body: formData });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      await refreshAfterDataChange();
      toast(t('toast.uploaded'), 'success');
    } catch (error) {
      showError(t('msgs.errUpload') + ' ' + error.message);
    } finally {
      if (btn) {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    }
  }

  async function handleDataGeneration() {
    const dataSource = document.getElementById('dataSource')?.value;
    if (dataSource === 'upload') await uploadAndProcessFile();
    else await runGenerator();
    closeDataGenModal();
  }

  async function cleanupOldOutputs() {
    if (!window.confirm(t('msgs.cleanupAsk'))) return;
    const btn = document.getElementById('btnCleanupOutputs');
    const originalText = btn ? btn.textContent : '';
    if (btn) {
      btn.textContent = t('msgs.processing');
      btn.disabled = true;
    }
    try {
      const response = await fetch('/api/cleanup-outputs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keep_latest: 3, include_uploaded: true }),
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      toast(t('msgs.cleanupOk', { n: result.removed_count ?? 0 }), 'success');
      await refreshAfterDataChange();
    } catch (error) {
      showError(t('msgs.errCleanup') + ' ' + error.message);
    } finally {
      if (btn) {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    }
  }

  global.closeDataGenModal = closeDataGenModal;
  global.openDataGenModal = openDataGenModal;

  let shellInited = false;

  /**
   * Gọi từ trang phụ (SIR, recommendations, graph). Không gọi từ trang tổng quan (script.js).
   * @param {{ onLangChange?: () => void }} options
   */
  function init(options) {
    if (shellInited) return;
    shellInited = true;
    const opts = options || {};

    initTheme();
    document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);

    document.getElementById('langToggle')?.addEventListener('click', () => {
      global.I18N?.toggleLang?.();
      global.I18N?.applyI18n?.();
      window.dispatchEvent(new CustomEvent('app:langchange'));
      opts.onLangChange?.();
    });

    global.I18N?.applyI18n?.();

    document.getElementById('menuOpenData')?.addEventListener('click', openDataGenModal);
    document.getElementById('btnCleanupOutputs')?.addEventListener('click', cleanupOldOutputs);

    const ds = document.getElementById('dataSource');
    if (ds) {
      ds.addEventListener('change', function () {
        toggleFileUpload(this.value === 'upload');
      });
    }

    const ft = document.getElementById('footerTimestamp');
    if (ft) {
      ft.textContent = new Date().toLocaleString(global.I18N?.getLang?.() === 'en' ? 'en-GB' : 'vi-VN');
    }
  }

  global.SharedNav = { init };
})(typeof window !== 'undefined' ? window : globalThis);
