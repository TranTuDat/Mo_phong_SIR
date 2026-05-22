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
    'rec.winnerTitle': 'Can thiệp theo {strategy}',
    'rec.winnerDesc':
      'Đỉnh I = {peak}, ngày đỉnh = {peakDay}, kết thúc dịch ngày {final}. Ưu tiên miễn nhiễm các nút bên dưới.',
    'rec.deltaDown': 'Giảm {n} ca so với SIR thuần',
    'rec.deltaUp': 'Cao hơn SIR thuần {n} ca',
    'rec.deltaSame': 'Bằng đỉnh SIR thuần',
    'rec.finalDay': 'Kết thúc dịch: ngày {d}',
    'rec.errLoad': 'Không tải được phân tích:',
    'rec.loading': 'Đang phân tích…',
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

  function formatDelta(purePeak, winnerPeak) {
    if (purePeak == null || winnerPeak == null) return '—';
    const d = winnerPeak - purePeak;
    if (d < 0) return t('rec.deltaDown', { n: Math.abs(d) });
    if (d > 0) return t('rec.deltaUp', { n: d });
    return t('rec.deltaSame');
  }

  function renderAnalysis(data) {
    setText('recOutputFolder', data.output_folder || '—');

    const rat = document.getElementById('recRationale');
    if (rat) {
      rat.textContent =
        (getLang() === 'en' ? data.rationale_en : data.rationale_vi) ||
        '—';
    }

    const p = data.pure_sir;
    setText('recPurePeakI', p != null ? p.peak_infected : '—');
    setText('recPurePeakDay', p != null ? p.peak_day : '—');

    const win = data.winner;
    const tbody = document.getElementById('recStrategiesBody');
    if (tbody) tbody.innerHTML = '';

    if (win) {
      const lbl = strategyLabel(win.strategy);
      setText('recWinnerPeakI', win.peak_infected);
      setText('recWinnerStrategy', lbl.title);
      setText('recWinnerFinal', t('rec.finalDay', { d: win.final_day }));
      setText('recWinnerDelta', formatDelta(p?.peak_infected, win.peak_infected));

      const titleEl = document.getElementById('recWinnerTitle');
      const sumEl = document.getElementById('recWinnerSummary');
      const hero = document.getElementById('recWinnerHero');
      if (titleEl) {
        titleEl.textContent = t('rec.winnerTitle', { strategy: lbl.title });
      }
      if (sumEl) {
        sumEl.textContent = t('rec.winnerDesc', {
          peak: win.peak_infected,
          peakDay: win.peak_day,
          final: win.final_day,
        });
      }
      if (hero) {
        hero.classList.remove('rec-winner-empty');
      }
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

    (data.strategies || []).forEach((row) => {
      const lbl = strategyLabel(row.strategy);
      const tr = document.createElement('tr');
      const isWinner = win && row.available && row.strategy === win.strategy;
      if (isWinner) tr.className = 'rec-row-winner';

      let badgeClass = 'missing';
      let badgeText = t('rec.statusMissing');
      if (row.available) {
        badgeClass = isWinner ? 'winner' : 'ok';
        badgeText = isWinner ? t('rec.statusWinner') : t('rec.statusOk');
      }

      tr.innerHTML = `
        <td>
          <div class="rec-strat-cell">
            <strong>${escapeHtml(lbl.title)}</strong>
            <span>${escapeHtml(lbl.sub)}</span>
          </div>
        </td>
        <td class="tabular-nums mau-num">${row.available ? row.peak_infected : '—'}</td>
        <td class="tabular-nums mau-num">${row.available ? row.peak_day : '—'}</td>
        <td class="tabular-nums mau-num">${row.available ? row.final_day : '—'}</td>
        <td><span class="rec-badge ${badgeClass}">${badgeText}</span></td>
      `;
      tbody?.appendChild(tr);
    });

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

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
      if (data.warning) {
        setStatus(data.warning, 'error');
      } else if (!data.strategies?.some((s) => s.available)) {
        setStatus(
          data.hint ||
            summary.hint ||
            'Chưa có kết quả can thiệp. Vào Phân tích mạng → chạy SIR + can thiệp (3 chiến lược).',
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
