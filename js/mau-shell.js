/**
 * Shell Mau.html dùng chung: menu, header, footer, modal nhập dữ liệu, thống kê sidebar.
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

  function toast(msg, ms = 3200) {
    const el = document.createElement('div');
    el.className = 'toast-msg';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  async function fetchJson(path, options) {
    const res = await fetch(path, options);
    let body = {};
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    if (!res.ok) throw new Error(body.error || body.hint || `HTTP ${res.status}`);
    return body;
  }

  function formatNumber(n) {
    const x = Number(n);
    if (!Number.isFinite(x)) return null;
    return x.toLocaleString('vi-VN');
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
      await fetchJson('/api/run-generator', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      closeModal();
      toast('Tạo dữ liệu thành công.');
      await refreshSideStats();
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
      await fetchJson('/api/upload-data', { method: 'POST', body: fd });
      closeModal();
      toast('Tải lên thành công.');
      await refreshSideStats();
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

  async function refreshSideStats() {
    try {
      const data = await fetchJson('/api/graph?refresh=0');
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
        if (key === 'report') {
          toast('Phiên bản và thời gian cập nhật ở chân trang.');
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

  function bindHeader() {
    document.getElementById('btnGuide')?.addEventListener('click', () => {
      toast('Tổng quan: bản đồ mạng & Top 10. Phân tích mạng: mô phỏng SIR.');
    });
    document.getElementById('btnReport')?.addEventListener('click', () => {
      toast('Phiên bản và thời gian cập nhật ở chân trang.');
    });
    document.getElementById('btnExport')?.addEventListener('click', () => {
      toast('Dữ liệu CSV nằm trong thư mục outputs/ trên máy chủ.');
    });
    document.getElementById('btnSettings')?.addEventListener('click', () => {
      toast('Dùng «Nhập dữ liệu» để sinh lại mạng.');
    });
  }

  function bindModal(onDataReady) {
    document.getElementById('menuOpenData')?.addEventListener('click', openModal);
    document.getElementById('modalClose')?.addEventListener('click', closeModal);
    document.getElementById('modalCancel')?.addEventListener('click', closeModal);
    document.getElementById('btnConfirmGenerate')?.addEventListener('click', () => confirmData(onDataReady));
    document.getElementById('dataSource')?.addEventListener('change', function () {
      const g = document.getElementById('fileUploadGroup');
      if (g) g.style.display = this.value === 'upload' ? 'block' : 'none';
    });
    document.getElementById('dataGenModal')?.addEventListener('click', (e) => {
      if (e.target.id === 'dataGenModal') closeModal();
    });
  }

  function init(options = {}) {
    const page = options.page || document.body.getAttribute('data-mau-page') || 'overview';
    const onDataReady = options.onDataReady;
    bindNavigation(page, onDataReady);
    bindHeader();
    bindModal(onDataReady);
    refreshSideStats();
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
    ROUTES,
  };
})(typeof window !== 'undefined' ? window : global);
