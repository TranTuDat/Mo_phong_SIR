/**
 * Trang gợi ý can thiệp /recommendations
 */
(function () {
  const STRATEGY_META = {
    betweenness: { vi: 'Betweenness', sub: 'Trung gian (cầu nối)', en: 'Betweenness' },
    degree: { vi: 'Degree', sub: 'Bậc cao (kết nối nhiều)', en: 'Degree' },
    eigenvector: { vi: 'Eigenvector', sub: 'Ảnh hưởng lan truyền', en: 'Eigenvector' },
  };

  function getLang() {
    return window.I18N && window.I18N.getLang ? window.I18N.getLang() : 'vi';
  }

  const VI = {
    'rec.statusOk': 'Đã mô phỏng',
    'rec.statusMissing': 'Chưa chạy',
    'rec.statusWinner': 'Đề xuất',
    'rec.winnerNone': 'Chưa có đề xuất — chạy mô phỏng SIR + can thiệp trước.',
    'rec.winnerTitle': 'Can thiệp: {strategy}',
    'rec.winnerDesc':
      '{strategy} — ngày can thiệp {day}, miễn nhiễm top-{k}. Đỉnh I = {peak}, kết thúc ngày {final}.',
    'rec.deltaDown': '−{n}',
    'rec.deltaUp': '+{n}',
    'rec.deltaSame': '0',
    'rec.finalDay': 'Kết thúc dịch: ngày {d}',
    'rec.errLoad': 'Không tải được phân tích:',
    'rec.loading': 'Đang phân tích…',
    'rec.noRuns': 'Chưa có mẫu nào — chạy SIR + can thiệp tại Phân tích mạng.',
  };

  function t(key, vars) {
    let s = window.I18N && window.I18N.t ? window.I18N.t(key) : VI[key] || key;
    if (vars) {
      Object.keys(vars).forEach((k) => {
        s = s.replace(new RegExp(`\\{${k}\\}`, 'g'), String(vars[k]));
      });
    }
    return s;
  }

  function strategyLabel(key) {
    const meta = STRATEGY_META[key] || { vi: key, sub: '', en: key };
    const lang = getLang();
    if (lang === 'en') return { title: meta.en, sub: meta.sub };
    return { title: meta.vi, sub: meta.sub };
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
    if (!msg) {
      el.hidden = true;
      el.textContent = '';
      return;
    }
    el.hidden = false;
    el.textContent = msg;
    el.className = 'sim-status-msg rec-status-bar ' + (type || 'info');
  }

  function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text ?? '—';
  }

  function formatDelta(purePeak, rowPeak) {
    if (purePeak == null || rowPeak == null) return '—';
    const d = rowPeak - purePeak;
    if (d < 0) return t('rec.deltaDown', { n: Math.abs(d) });
    if (d > 0) return t('rec.deltaUp', { n: d });
    return t('rec.deltaSame');
  }

  function deltaClass(purePeak, rowPeak) {
    if (purePeak == null || rowPeak == null) return '';
    const d = rowPeak - purePeak;
    if (d < 0) return 'rec-delta-good';
    if (d > 0) return 'rec-delta-bad';
    return '';
  }

  /** Thứ tự xếp hạng: kết thúc dịch sớm → đỉnh I thấp → ngày đỉnh sớm. */
  function rankKey(row) {
    const big = 1e9;
    return [
      row.final_day != null ? Number(row.final_day) : big,
      row.peak_infected != null ? Number(row.peak_infected) : big,
      row.peak_day != null ? Number(row.peak_day) : big,
    ];
  }

  function compareRuns(a, b) {
    const ka = rankKey(a);
    const kb = rankKey(b);
    for (let i = 0; i < 3; i++) {
      if (ka[i] !== kb[i]) return ka[i] - kb[i];
    }
    return 0;
  }

  function runSignature(r) {
    if (!r) return '';
    return `${r.strategy}|${r.intervention_day ?? ''}|${r.top_k ?? ''}`;
  }

  function isSameRun(win, row) {
    if (!win || !row?.available) return false;
    if (runSignature(win) && runSignature(row) && runSignature(win) === runSignature(row)) {
      return true;
    }
    return (
      row.strategy === win.strategy &&
      Number(row.intervention_day) === Number(win.intervention_day) &&
      Number(row.top_k) === Number(win.top_k)
    );
  }

  /** Luôn chọn đề xuất từ danh sách runs (tránh API winner thiếu ngày/k). */
  function resolveWinner(data) {
    const pool = (data.runs || []).filter((r) => r.available);
    if (!pool.length) return null;
    const sorted = [...pool].sort(compareRuns);
    return sorted[0];
  }

  function renderTableRow(row, win, purePeak, opts) {
    const { showBadge = false, emptyRuns = false } = opts || {};
    const lbl = strategyLabel(row.strategy);
    const tr = document.createElement('tr');
    const isWinner = isSameRun(win, row);
    if (isWinner) tr.className = 'rec-row-winner';

    if (!row.available) {
      tr.innerHTML = `
        <td>
          <div class="rec-strat-cell">
            <strong>${escapeHtml(lbl.title)}</strong>
            <span>${escapeHtml(lbl.sub)}</span>
          </div>
        </td>
        <td colspan="7" class="rec-cell-muted">${t('rec.statusMissing')}</td>
        ${showBadge ? '<td></td>' : ''}
      `;
      return tr;
    }

    let badgeCell = '';
    if (showBadge) {
      const badgeClass = isWinner ? 'winner' : 'ok';
      const badgeText = isWinner ? t('rec.statusWinner') : t('rec.statusOk');
      badgeCell = `<td><span class="rec-badge ${badgeClass}">${badgeText}</span></td>`;
    }

    const day = row.intervention_day != null ? row.intervention_day : '—';
    const k = row.top_k != null ? row.top_k : '—';
    const delta = formatDelta(purePeak, row.peak_infected);
    const dCls = deltaClass(purePeak, row.peak_infected);

    tr.innerHTML = `
      <td>
        <div class="rec-strat-cell">
          <strong>${escapeHtml(lbl.title)}</strong>
          <span>${escapeHtml(lbl.sub)}</span>
        </div>
      </td>
      <td class="tabular-nums mau-num">${day}</td>
      <td class="tabular-nums mau-num">${k}</td>
      <td class="tabular-nums mau-num">${row.peak_infected}</td>
      <td class="tabular-nums mau-num">${row.final_day}</td>
      <td class="tabular-nums mau-num">${row.peak_day}</td>
      <td class="tabular-nums mau-num ${dCls}">${delta}</td>
      ${badgeCell}
    `;
    return tr;
  }

  function renderStrategiesTable(rows, win, purePeak) {
    const tbody = document.getElementById('recStrategiesBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    (rows || []).forEach((row) => {
      tbody.appendChild(renderTableRow(row, win, purePeak, { showBadge: false }));
    });
  }

  function renderRunsTable(runs, win, purePeak) {
    const tbody = document.getElementById('recRunsBody');
    if (!tbody) return;
    tbody.innerHTML = '';
    const available = (runs || []).filter((r) => r.available).sort(compareRuns);
    if (!available.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td colspan="8" class="rec-cell-muted">${t('rec.noRuns')}</td>`;
      tbody.appendChild(tr);
      return;
    }
    available.forEach((row) => {
      tbody.appendChild(renderTableRow(row, win, purePeak, { showBadge: true }));
    });
  }

  function formatWinnerStrategyLine(win) {
    const lbl = strategyLabel(win.strategy);
    const day = win.intervention_day != null ? win.intervention_day : '—';
    const k = win.top_k != null ? win.top_k : '—';
    return `${lbl.title} · ngày ${day} · k=${k}`;
  }

  function renderWinnerPanel(win, pureSir) {
    const p = pureSir;
    if (win) {
      const lbl = strategyLabel(win.strategy);
      setText('recWinnerPeakI', win.peak_infected);
      setText('recWinnerStrategy', formatWinnerStrategyLine(win));
      setText('recWinnerFinal', t('rec.finalDay', { d: win.final_day }));
      setText('recWinnerDelta', formatDelta(p?.peak_infected, win.peak_infected));

      const titleEl = document.getElementById('recWinnerTitle');
      const sumEl = document.getElementById('recWinnerSummary');
      const hero = document.getElementById('recWinnerHero');
      if (titleEl) titleEl.textContent = t('rec.winnerTitle', { strategy: lbl.title });
      if (sumEl) {
        sumEl.textContent = t('rec.winnerDesc', {
          strategy: lbl.title,
          day: win.intervention_day != null ? win.intervention_day : '—',
          k: win.top_k != null ? win.top_k : '—',
          peak: win.peak_infected,
          final: win.final_day,
        });
      }
      if (hero) hero.classList.remove('rec-winner-empty');
    } else {
      setText('recWinnerPeakI', '—');
      setText('recWinnerStrategy', '—');
      setText('recWinnerFinal', '—');
      setText('recWinnerDelta', '—');
      const titleEl = document.getElementById('recWinnerTitle');
      const sumEl = document.getElementById('recWinnerSummary');
      const hero = document.getElementById('recWinnerHero');
      if (titleEl) titleEl.textContent = 'Chưa có đề xuất';
      if (sumEl) sumEl.textContent = t('rec.winnerNone');
      if (hero) hero.classList.add('rec-winner-empty');
    }

    const listEl = document.getElementById('recWinnerNodes');
    if (!listEl) return;
    listEl.innerHTML = '';
    if (!win || !(win.intervened_nodes || []).length) {
      const li = document.createElement('li');
      li.className = 'rec-node-empty';
      li.textContent = '—';
      listEl.appendChild(li);
      return;
    }
    win.intervened_nodes.forEach((n, i) => {
      const li = document.createElement('li');
      li.innerHTML = `
        <span class="rec-node-rank">${i + 1}</span>
        <div class="rec-node-info">
          <strong class="tabular-nums">#${escapeHtml(n.id)}</strong>
          <span>${escapeHtml(n.name)}</span>
        </div>
      `;
      listEl.appendChild(li);
    });
  }

  function renderAnalysis(data) {
    setText('recOutputFolder', data.output_folder || '—');

    const pure = data.pure_sir;
    const purePeak = pure?.peak_infected;
    setText('recPurePeakI', pure != null ? pure.peak_infected : '—');
    setText('recPurePeakDay', pure != null ? pure.peak_day : '—');

    const strategies = data.strategies || [];
    const runs = (data.runs || []).filter((r) => r.available || r.strategy);
    const win = resolveWinner(data);
    const pureSir = data.pure_sir;

    renderStrategiesTable(strategies, win, purePeak);
    renderRunsTable(runs, win, purePeak);
    renderWinnerPanel(win, pureSir);
  }

  async function loadAnalysis() {
    setStatus(t('rec.loading'), 'loading');
    try {
      const summary = await fetchJson('/api/summary');
      const folder = summary.output_folder;
      const data = await fetchJson(
        `/api/intervention-recommendations${folder ? `?output_dir=${encodeURIComponent(folder)}` : ''}`
      );
      renderAnalysis(data);
      const hasRuns = (data.runs || []).some((r) => r.available);
      const hasStrat = (data.strategies || []).some((s) => s.available);
      if (data.warning) {
        setStatus(data.warning, 'error');
      } else if (!hasRuns && !hasStrat) {
        setStatus(
          data.hint ||
            summary.hint ||
            'Chưa có kết quả can thiệp. Vào Phân tích mạng → chạy SIR + can thiệp.',
          'info'
        );
      } else {
        setStatus('', 'info');
      }
    } catch (e) {
      setStatus(t('rec.errLoad') + ' ' + e.message, 'error');
    }
  }

  function init() {
    window.onSharedDataReady = () => loadAnalysis();
    window.MauShell?.init({ page: 'recommendations', onDataReady: loadAnalysis });
    document.getElementById('btnAnalyze')?.addEventListener('click', loadAnalysis);
    loadAnalysis();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
