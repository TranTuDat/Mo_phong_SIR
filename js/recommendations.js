/**
 * Trang gợi ý can thiệp /recommendations
 */
(function () {
  function getLang() {
    return window.I18N && window.I18N.getLang ? window.I18N.getLang() : 'vi';
  }

  function t(key) {
    if (window.I18N && window.I18N.t) return window.I18N.t(key);
    return key;
  }

  async function fetchJson(url) {
    const r = await fetch(url, { cache: 'no-store' });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
    return data;
  }

  function setStatus(msg, type) {
    const el = document.getElementById('recStatus');
    if (!el) return;
    el.textContent = msg || '';
    el.className = 'status-message sim-status-msg ' + (type || 'info');
  }

  function renderAnalysis(data) {
    const folderEl = document.getElementById('recOutputFolder');
    if (folderEl) folderEl.textContent = data.output_folder || '—';

    const rat = document.getElementById('recRationale');
    if (rat) {
      rat.textContent = getLang() === 'en' ? data.rationale_en : data.rationale_vi;
    }

    const p = data.pure_sir;
    document.getElementById('recPurePeakI').textContent = p ? String(p.peak_infected) : '—';
    document.getElementById('recPurePeakDay').textContent = p ? String(p.peak_day) : '—';
    document.getElementById('recPureFinal').textContent = p ? String(p.final_day) : '—';

    const tbody = document.getElementById('recStrategiesBody');
    tbody.innerHTML = '';
    (data.strategies || []).forEach((row) => {
      const tr = document.createElement('tr');
      const stLabel = row.available ? t('rec.statusOk') : t('rec.statusMissing');
      tr.innerHTML = `
        <td>${row.strategy}</td>
        <td class="tabular-nums">${row.available ? row.peak_infected : '—'}</td>
        <td class="tabular-nums">${row.available ? row.peak_day : '—'}</td>
        <td class="tabular-nums">${row.available ? row.final_day : '—'}</td>
        <td>${stLabel}</td>
      `;
      tbody.appendChild(tr);
    });

    const win = data.winner;
    const sumEl = document.getElementById('recWinnerSummary');
    const listEl = document.getElementById('recWinnerNodes');
    listEl.innerHTML = '';

    if (!win) {
      sumEl.textContent = t('rec.winnerNone');
      return;
    }

    const stratLabel = win.strategy;
    sumEl.textContent =
      getLang() === 'en'
        ? `Best strategy: ${stratLabel} (lower peak I = ${win.peak_infected}, end day = ${win.final_day}).`
        : `Chiến lược được đề xuất: ${stratLabel} (đỉnh I = ${win.peak_infected}, ngày kết thúc = ${win.final_day}).`;

    (win.intervened_nodes || []).forEach((n) => {
      const li = document.createElement('li');
      li.className = 'cluster-item';
      li.innerHTML = `<div><strong class="tabular-nums">${n.id}</strong> — ${escapeHtml(n.name)}</div>`;
      listEl.appendChild(li);
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function loadAnalysis() {
    setStatus('…', 'loading');
    try {
      const summary = await fetchJson('/api/summary');
      const folder = summary.output_folder;
      const data = await fetchJson(
        `/api/intervention-recommendations${folder ? `?output_dir=${encodeURIComponent(folder)}` : ''}`
      );
      renderAnalysis(data);
      if (data.warning) {
        setStatus(data.warning, 'error');
      } else if (!data.strategies?.some((s) => s.available)) {
        setStatus(data.hint || summary.hint || '', 'info');
      } else {
        setStatus('', 'info');
      }
    } catch (e) {
      setStatus(t('rec.errLoad') + ' ' + e.message, 'error');
    }
  }

  function init() {
    window.onSharedDataReady = () => loadAnalysis();
    window.SharedNav?.init({
      onLangChange: () => loadAnalysis(),
    });
    document.getElementById('btnAnalyze')?.addEventListener('click', loadAnalysis);
    loadAnalysis();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
