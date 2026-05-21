/**
 * Trang mô phỏng SIR độc lập (/simulation)
 */
(function () {
  let simLineChart = null;
  let simCompareChart = null;
  let pureResults = null;
  let dynamicResults = null;
  let currentSimModel = 'pure';
  /** @type {{ pure: object | null }} */
  const resultsByKey = { pure: null };
  /** @type {Record<string, object>} key = `${strategy}:${intervention_day}` */
  const dynamicRuns = {};
  /** 'pure' | `${strategy}:${intervention_day}` — mẫu đang xem ở tab Đồ thị / Chỉ số */
  let activeSirRunKey = 'pure';

  function t(key, vars) {
    return window.I18N && window.I18N.t ? window.I18N.t(key, vars) : key;
  }

  function getLang() {
    return window.I18N && window.I18N.getLang ? window.I18N.getLang() : 'vi';
  }

  async function fetchJson(path) {
    const r = await fetch(path, { cache: 'no-store' });
    if (!r.ok) throw new Error(`API lỗi ${r.status}`);
    return r.json();
  }

  async function loadSidebarSummary() {
    try {
      const data = await fetchJson('/api/summary');
      const n = document.getElementById('summary-nodes');
      const e = document.getElementById('summary-edges');
      if (n) n.textContent = data.nodes;
      if (e) e.textContent = data.edges;
      const hint = document.getElementById('dataHint');
      if (hint) {
        hint.style.display = data.ready === false ? 'block' : 'none';
      }
      return data;
    } catch (err) {
      console.warn(err);
      const hint = document.getElementById('dataHint');
      if (hint) hint.style.display = 'block';
      return null;
    }
  }

  function switchModel(model) {
    currentSimModel = model;
    document.querySelectorAll('.sim-tab-model').forEach((btn) => {
      btn.classList.toggle('active', btn.dataset.model === model);
    });
    const pureEl = document.getElementById('pure-controls');
    const dynEl = document.getElementById('dynamic-controls');
    if (pureEl) pureEl.style.display = model === 'pure' ? 'flex' : 'none';
    if (dynEl) dynEl.style.display = model === 'dynamic' ? 'flex' : 'none';
  }

  function getActiveSirResultTab() {
    const active = document.querySelector('.sim-results-panel .result-tab-content.active');
    if (!active) return 'chart';
    if (active.id === 'sir-stats-tab') return 'stats';
    if (active.id === 'sir-comparison-tab') return 'comparison';
    return 'chart';
  }

  function dynamicRunKeyFromRun(run) {
    const strat = run.strategy || 'betweenness';
    const day = run.intervention_day != null ? run.intervention_day : 1;
    return `${strat}:${day}`;
  }

  function strategyShortName(strat) {
    if (strat === 'degree') return 'degree';
    if (strat === 'eigenvector') return 'eigenvector';
    return 'betweenness';
  }

  function formatDynamicRunLabel(run, key) {
    const strat = run?.strategy || (key && key.split(':')[0]) || 'betweenness';
    const day =
      run?.intervention_day != null ? run.intervention_day : parseInt((key || '').split(':')[1], 10) || 1;
    const topK = run?.top_k != null ? run.top_k : '—';
    return t('sir.runDynFmt', {
      strategy: strategyShortName(strat),
      day,
      k: topK,
    });
  }

  function listSirRunOptions() {
    const opts = [];
    if (resultsByKey.pure) opts.push({ key: 'pure', type: 'pure' });
    for (const k of Object.keys(dynamicRuns).sort()) {
      opts.push({ key: k, type: 'dynamic', run: dynamicRuns[k] });
    }
    return opts;
  }

  function getActiveSirRunData() {
    if (activeSirRunKey === 'pure') {
      return { model: 'pure', data: resultsByKey.pure };
    }
    return { model: 'dynamic', data: dynamicRuns[activeSirRunKey] };
  }

  function syncSirRunPicker(preferredKey) {
    const picker = document.getElementById('sirRunPicker');
    const sel = document.getElementById('sirRunSelect');
    const countBadge = document.getElementById('sirRunPickerCount');
    if (!picker || !sel) return;
    const opts = listSirRunOptions();
    const hasDynamic = opts.some((o) => o.type === 'dynamic');
    picker.hidden = !hasDynamic;
    if (!hasDynamic) return;

    sel.replaceChildren();
    for (const o of opts) {
      const opt = document.createElement('option');
      opt.value = o.key;
      opt.textContent =
        o.type === 'pure' ? t('sir.runPureOpt') : formatDynamicRunLabel(o.run, o.key);
      sel.appendChild(opt);
    }
    const keys = opts.map((o) => o.key);
    let next = keys[keys.length - 1];
    if (preferredKey && keys.includes(preferredKey)) next = preferredKey;
    else if (keys.includes(activeSirRunKey)) next = activeSirRunKey;
    sel.value = next;
    const dynCount = opts.filter((o) => o.type === 'dynamic').length;
    if (countBadge) {
      countBadge.textContent = dynCount >= 2 ? t('sir.runCount', { n: dynCount }) : '';
      countBadge.hidden = dynCount < 2;
    }
    resizeSirCharts();
  }

  function setActiveSirRun(key) {
    if (key === 'pure') {
      if (!resultsByKey.pure) return;
      activeSirRunKey = 'pure';
      currentSimModel = 'pure';
      pureResults = resultsByKey.pure;
    } else {
      const run = dynamicRuns[key];
      if (!run) return;
      activeSirRunKey = key;
      currentSimModel = 'dynamic';
      dynamicResults = run;
    }
    const sel = document.getElementById('sirRunSelect');
    if (sel && sel.value !== key) sel.value = key;

    const { model, data } = getActiveSirRunData();
    if (!data) return;
    const modelLabel =
      model === 'pure' ? 'SIR thuần' : 'SIR + can thiệp (miễn nhiễm động)';
    updateStatsSim(data, modelLabel);
    updateResultsStrip(data);
    if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
      updateComparisonTableSim();
    }
    refreshSirChartsForTab(getActiveSirResultTab());
    resizeSirCharts();
  }

  function sirChartTitleForModel(model) {
    if (model === 'pure') {
      return t('sir.chartPure') || (getLang() === 'en' ? 'S–I–R curve (pure SIR)' : 'Đường cong S-I-R (SIR thuần)');
    }
    const base = t('sir.chartDyn') || 'Đường cong S-I-R (SIR + can thiệp)';
    if (activeSirRunKey !== 'pure' && dynamicRuns[activeSirRunKey]) {
      return `${base} — ${formatDynamicRunLabel(dynamicRuns[activeSirRunKey], activeSirRunKey)}`;
    }
    return base;
  }

  function resizeSirCharts() {
    requestAnimationFrame(() => {
      if (simLineChart) simLineChart.resize();
      if (simCompareChart) simCompareChart.resize();
    });
  }

  function switchSirResultTab(tab, evt) {
    document.querySelectorAll('.sim-results-panel .result-tab-content').forEach((el) => {
      el.classList.remove('active');
    });
    document.querySelectorAll('.sim-results-panel .result-tab-btn').forEach((btn) => {
      btn.classList.remove('active');
    });
    const pane = document.getElementById(`sir-${tab}-tab`);
    if (pane) pane.classList.add('active');
    const tabBtn =
      (evt && evt.currentTarget) ||
      document.querySelector(`.sim-results-panel .result-tab-btn[data-sir-tab="${tab}"]`);
    if (tabBtn) tabBtn.classList.add('active');
    requestAnimationFrame(() => {
      refreshSirChartsForTab(tab);
      resizeSirCharts();
    });
  }

  /** Vẽ lại biểu đồ sau khi tab hiển thị (tránh canvas 0×0 khi tab ẩn). */
  function refreshSirChartsForTab(tab) {
    const { model, data } = getActiveSirRunData();
    if (tab === 'chart') {
      if (data?.history?.length) drawSirSimChart(data.history, sirChartTitleForModel(model));
    } else if (tab === 'comparison') {
      if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
        drawSirComparisonChart();
        updateComparisonTableSim();
      }
    } else if (tab === 'stats' && data) {
      updateStatsSim(data, model === 'pure' ? 'SIR thuần' : 'SIR + can thiệp (miễn nhiễm động)');
    }
  }

  function setupSirRangeInputs() {
    const bind = (id, outId, fmt) => {
      const inp = document.getElementById(id);
      const out = document.getElementById(outId);
      if (!inp || !out) return;
      inp.addEventListener('input', () => {
        out.textContent = fmt ? fmt(inp.value) : inp.value;
      });
    };
    bind('pureTrans', 'pureTransValue', (v) => parseFloat(v).toFixed(2));
    bind('pureRecov', 'pureRecovValue', (v) => parseFloat(v).toFixed(2));
    bind('dynTrans', 'dynTransValue', (v) => parseFloat(v).toFixed(2));
    bind('dynRecov', 'dynRecovValue', (v) => parseFloat(v).toFixed(2));
    bind('topK', 'topKValue', null);
    const syncInterventionDayMax = () => {
      const daysEl = document.getElementById('dynDays');
      const intEl = document.getElementById('interventionDay');
      if (!daysEl || !intEl) return;
      const d = parseInt(daysEl.value, 10) || 300;
      intEl.max = String(Math.max(1, d));
      const cur = parseInt(intEl.value, 10) || 1;
      if (cur > d) intEl.value = String(d);
    };
    syncInterventionDayMax();
    document.getElementById('dynDays')?.addEventListener('input', syncInterventionDayMax);
    document.getElementById('dynDays')?.addEventListener('change', syncInterventionDayMax);
  }

  function showSimStatus(message, type) {
    const el = document.getElementById('simStatus');
    if (!el) return;
    el.textContent = message;
    el.className = 'status-message sim-status-msg ' + (type || 'info');
  }

  function updateResultsStrip(data) {
    const peakDay = document.getElementById('stripPeakDay');
    const peakI = document.getElementById('stripPeakInfected');
    const finalD = document.getElementById('stripFinalDay');
    const susEnd = document.getElementById('stripSusceptibleEnd');
    if (peakDay) peakDay.textContent = data.peak_day;
    if (peakI) peakI.textContent = data.peak_infected;
    if (finalD) finalD.textContent = data.final_day;
    if (susEnd && data.history && data.history.length) {
      susEnd.textContent = data.history[data.history.length - 1].S;
    }
    const strip = document.getElementById('sirResultsStrip');
    if (strip) strip.hidden = false;
  }

  async function runPureSimulation() {
    const btn = document.getElementById('btnRunPureSimulation');
    const transmission = parseFloat(document.getElementById('pureTrans').value);
    const recovery = parseFloat(document.getElementById('pureRecov').value);
    const days = parseInt(document.getElementById('pureDays').value, 10);
    const seed = parseInt(document.getElementById('pureSeed').value, 10);
    if (!transmission || !recovery || !days) {
      showSimStatus(t('msgs.errParams'), 'error');
      return;
    }
    btn.disabled = true;
    showSimStatus(t('msgs.runningPure'), 'loading');
    try {
      const response = await fetch('/api/simulate-sir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'pure',
          transmission_rate: transmission,
          recovery_rate: recovery,
          days,
          seed,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Lỗi mô phỏng');
      pureResults = data;
      dynamicResults = null;
      resultsByKey.pure = data;
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      displayPureResults(data);
      showSimStatus(t('msgs.donePure'), 'success');
    } catch (error) {
      showSimStatus('Lỗi: ' + error.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  async function runDynamicSimulation() {
    const btn = document.getElementById('btnRunDynamicSimulation');
    const transmission = parseFloat(document.getElementById('dynTrans').value);
    const recovery = parseFloat(document.getElementById('dynRecov').value);
    const days = parseInt(document.getElementById('dynDays').value, 10);
    const topK = parseInt(document.getElementById('topK').value, 10);
    const seed = parseInt(document.getElementById('dynSeed').value, 10);
    const strategy = document.getElementById('interventionStrategy')?.value || 'betweenness';
    let interventionDay = parseInt(document.getElementById('interventionDay')?.value, 10);
    if (!Number.isFinite(interventionDay) || interventionDay < 1) interventionDay = 1;
    if (interventionDay > days) {
      showSimStatus(
        getLang() === 'en'
          ? 'Intervention day cannot exceed max days.'
          : 'Ngày can thiệp không được lớn hơn số ngày tối đa.',
        'error'
      );
      return;
    }
    if (!transmission || !recovery || !days || !topK) {
      showSimStatus(t('msgs.errParams'), 'error');
      return;
    }
    btn.disabled = true;
    showSimStatus(t('msgs.runningDyn'), 'loading');
    try {
      const response = await fetch('/api/simulate-sir', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'dynamic',
          transmission_rate: transmission,
          recovery_rate: recovery,
          days,
          top_k: topK,
          seed,
          strategy,
          intervention_day: interventionDay,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Lỗi mô phỏng');
      const rk = `${strategy}:${data.intervention_day != null ? data.intervention_day : interventionDay}`;
      dynamicRuns[rk] = data;
      dynamicResults = data;
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      displayDynamicResults(data, rk);
      showSimStatus(t('msgs.doneDyn'), 'success');
    } catch (error) {
      showSimStatus('Lỗi: ' + error.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  function updateStatsSim(data, modelLabel) {
    const recovered =
      data.history && data.history.length ? data.history[data.history.length - 1].R : 0;
    document.getElementById('statPeakDaySim').textContent = data.peak_day;
    document.getElementById('statPeakInfectedSim').textContent = data.peak_infected;
    document.getElementById('statFinalDaySim').textContent = data.final_day;
    document.getElementById('statTotalRecoveredSim').textContent = recovered;
    document.getElementById('detailModelSim').textContent = modelLabel;
    const isPure = currentSimModel === 'pure';
    const tr = parseFloat(document.getElementById(isPure ? 'pureTrans' : 'dynTrans').value);
    const rc = parseFloat(document.getElementById(isPure ? 'pureRecov' : 'dynRecov').value);
    document.getElementById('detailTransSim').textContent = (tr * 100).toFixed(1) + '%';
    document.getElementById('detailRecovSim').textContent = (rc * 100).toFixed(1) + '%';
    const outPath = document.getElementById('detailOutputPath');
    if (outPath) outPath.textContent = data.output_directory || '—';
    const strat = data.strategy || (document.getElementById('interventionStrategy')?.value || 'betweenness');
    const stratLabel =
      strat === 'degree' ? 'degree' : strat === 'eigenvector' ? 'eigenvector' : 'betweenness';
    const iday = data.intervention_day != null ? data.intervention_day : 1;
    document.getElementById('detailRuntimeSim').textContent =
      data.top_k != null
        ? (getLang() === 'en'
            ? `Immunize top-${data.top_k} by ${stratLabel}, intervention day ${iday}`
            : `Miễn nhiễm top-${data.top_k} theo ${stratLabel}, ngày can thiệp ${iday}`)
        : '—';
  }

  function displayPureResults(data) {
    resultsByKey.pure = data;
    pureResults = data;
    syncSirRunPicker('pure');
    setActiveSirRun('pure');
  }

  function displayDynamicResults(data, runKey) {
    const rk = runKey || dynamicRunKeyFromRun(data);
    dynamicRuns[rk] = data;
    dynamicResults = data;
    syncSirRunPicker(rk);
    setActiveSirRun(rk);
  }

  function drawSirSimChart(history, titleText) {
    const canvas = document.getElementById('sirSimChart');
    if (!canvas || typeof Chart === 'undefined' || !history || !history.length) return;
    const ctx = canvas.getContext('2d');
    if (simLineChart) simLineChart.destroy();
    const labels = history.map((h) => h.day);
    const S = history.map((h) => h.S);
    const I = history.map((h) => h.I);
    const R = history.map((h) => h.R);
    simLineChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Dễ bị lây (S)',
            data: S,
            borderColor: '#4285f4',
            backgroundColor: 'rgba(66, 133, 244, 0.1)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
          },
          {
            label: 'Đang nhiễm (I)',
            data: I,
            borderColor: '#ea4335',
            backgroundColor: 'rgba(234, 67, 53, 0.1)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
          },
          {
            label: 'Hồi phục (R)',
            data: R,
            borderColor: '#34a853',
            backgroundColor: 'rgba(52, 168, 83, 0.1)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { position: 'top' },
          title: { display: true, text: titleText },
          tooltip: {
            callbacks: {
              label(ctx) {
                return `${ctx.dataset.label}: ${ctx.parsed.y}`;
              },
            },
          },
        },
        scales: {
          x: { title: { display: true, text: 'Ngày mô phỏng' } },
          y: { beginAtZero: true, title: { display: true, text: 'Số cá thể' } },
        },
      },
    });
    resizeSirCharts();
  }

  function drawSirComparisonChart() {
    const canvas = document.getElementById('comparisonSimChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');
    if (simCompareChart) simCompareChart.destroy();
    const pure = resultsByKey.pure;
    if (!pure) return;
    const keys = Object.keys(dynamicRuns).sort();
    if (!keys.length) return;

    let maxDay = 0;
    for (const h of pure.history || []) maxDay = Math.max(maxDay, h.day);
    for (const k of keys) {
      for (const h of dynamicRuns[k].history || []) maxDay = Math.max(maxDay, h.day);
    }
    const labels = Array.from({ length: maxDay + 1 }, (_, i) => i);

    const alignI = (history) => {
      const byDay = {};
      for (const h of history || []) byDay[h.day] = h.I;
      let last = history && history.length ? history[0].I : 0;
      return labels.map((d) => {
        if (Object.prototype.hasOwnProperty.call(byDay, d)) last = byDay[d];
        return last;
      });
    };

    const pureI = alignI(pure.history);
    const palette = [
      ['#2563eb', 'rgba(37, 99, 235, 0.08)'],
      ['#34a853', 'rgba(52, 168, 83, 0.08)'],
      ['#9333ea', 'rgba(147, 51, 234, 0.08)'],
      ['#f59e0b', 'rgba(245, 158, 11, 0.08)'],
      ['#ec4899', 'rgba(236, 72, 153, 0.08)'],
      ['#0ea5e9', 'rgba(14, 165, 233, 0.08)'],
    ];

    const datasets = [
      {
        label: t('sir.datasetPureI'),
        data: pureI,
        borderColor: '#ea4335',
        backgroundColor: 'rgba(234, 67, 53, 0.08)',
        tension: 0.35,
        fill: true,
        borderWidth: 2,
      },
    ];

    keys.forEach((key, idx) => {
      const run = dynamicRuns[key];
      const strat = run.strategy || key.split(':')[0];
      const day =
        run.intervention_day != null ? run.intervention_day : parseInt(key.split(':')[1], 10) || 1;
      const sShort =
        strat === 'degree' ? 'degree' : strat === 'eigenvector' ? 'eigenvector' : 'betweenness';
      const dayWord = getLang() === 'en' ? 'day' : 'ngày';
      const label = `${t('sir.cmpDyn')} (${sShort}, ${dayWord} ${day}) — I`;
      const [bc, fill] = palette[idx % palette.length];
      datasets.push({
        label,
        data: alignI(run.history),
        borderColor: bc,
        backgroundColor: fill,
        tension: 0.35,
        fill: true,
        borderWidth: 2,
      });
    });

    simCompareChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets,
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: 'top' },
          title: {
            display: true,
            text: t('sir.chartCmp'),
          },
        },
        scales: {
          y: { beginAtZero: true },
        },
      },
    });
    resizeSirCharts();
  }

  function updateComparisonTableSim() {
    const pure = resultsByKey.pure;
    const headRow = document.getElementById('comparisonSimTableHeadRow');
    const bodyEl = document.getElementById('comparisonSimTableBody');
    if (!pure || !headRow || !bodyEl) return;

    const keys = Object.keys(dynamicRuns).sort();
    const lang = getLang();

    headRow.replaceChildren();
    const thMetric = document.createElement('th');
    thMetric.setAttribute('data-i18n', 'sir.cmpMetric');
    thMetric.textContent = t('sir.cmpMetric');
    const thPure = document.createElement('th');
    thPure.setAttribute('data-i18n', 'sir.cmpPure');
    thPure.textContent = t('sir.cmpPure');
    headRow.appendChild(thMetric);
    headRow.appendChild(thPure);
    for (const k of keys) {
      const run = dynamicRuns[k];
      const strat = run.strategy || k.split(':')[0];
      const day =
        run.intervention_day != null ? run.intervention_day : parseInt(k.split(':')[1], 10) || 1;
      const sShort =
        strat === 'degree' ? 'degree' : strat === 'eigenvector' ? 'eigenvector' : 'betweenness';
      const th = document.createElement('th');
      th.textContent = `${t('sir.cmpDyn')}: ${sShort}, ${lang === 'en' ? 'day' : 'ngày'} ${day}`;
      headRow.appendChild(th);
    }

    bodyEl.replaceChildren();
    const rowsDef = [
      { tKey: 'sir.cmpPeak', pureKey: 'peak_day', runKey: 'peak_day' },
      { tKey: 'sir.cmpPeakI', pureKey: 'peak_infected', runKey: 'peak_infected' },
      { tKey: 'sir.cmpFinal', pureKey: 'final_day', runKey: 'final_day' },
    ];
    for (const def of rowsDef) {
      const tr = document.createElement('tr');
      const td0 = document.createElement('td');
      td0.setAttribute('data-i18n', def.tKey);
      td0.textContent = t(def.tKey);
      const td1 = document.createElement('td');
      td1.className = 'tabular-nums';
      td1.textContent = String(pure[def.pureKey]);
      tr.appendChild(td0);
      tr.appendChild(td1);
      for (const k of keys) {
        const run = dynamicRuns[k];
        const td = document.createElement('td');
        td.className = 'tabular-nums';
        const v = run[def.runKey];
        td.textContent = v != null ? String(v) : '—';
        tr.appendChild(td);
      }
      bodyEl.appendChild(tr);
    }
  }

  async function fetchSirResultsFromApi(datasetFolder, model, strategy, interventionDay) {
    let url = `/api/sir-results?output_dir=${encodeURIComponent(datasetFolder)}&model=${encodeURIComponent(model)}`;
    if (model === 'dynamic') {
      url += `&strategy=${encodeURIComponent(strategy)}&intervention_day=${encodeURIComponent(String(interventionDay))}`;
    }
    const r = await fetch(url, { cache: 'no-store' });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    return body;
  }

  function sirApiDataToRunModel(d, model) {
    const st = d.statistics || {};
    return {
      peak_day: st.peak_day,
      peak_infected: st.peak_infected,
      final_day: st.final_day,
      history: d.history,
      output_directory: d.output_directory || null,
      strategy: d.strategy,
      intervention_day: d.intervention_day != null ? d.intervention_day : 1,
      top_k: d.top_k,
      model,
    };
  }

  async function restoreSavedSirRuns(summary) {
    const s = summary || (await fetchJson('/api/summary').catch(() => null));
    if (!s || !s.ready || !s.output_folder) return;
    let list;
    try {
      list = await fetchJson(`/api/sir-saved-runs?output_dir=${encodeURIComponent(s.output_folder)}`);
    } catch {
      return;
    }
    let restored = 0;
    if (list.pure_available) {
      try {
        const d = await fetchSirResultsFromApi(s.output_folder, 'pure');
        const run = sirApiDataToRunModel(d, 'pure');
        pureResults = run;
        resultsByKey.pure = run;
        restored += 1;
      } catch (e) {
        console.warn('restore pure', e);
      }
    }
    for (const row of list.dynamic_runs || []) {
      try {
        const d = await fetchSirResultsFromApi(s.output_folder, 'dynamic', row.strategy, row.intervention_day);
        const run = sirApiDataToRunModel(d, 'dynamic');
        dynamicRuns[`${row.strategy}:${row.intervention_day}`] = run;
        restored += 1;
      } catch (e) {
        console.warn('restore dynamic', row, e);
      }
    }
    if (!restored) return;
    showSimStatus(t('msgs.restoredSir', { n: restored }), 'success');
    if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
      const dkLast = Object.keys(dynamicRuns).sort();
      const lastKey = dkLast[dkLast.length - 1];
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      syncSirRunPicker(lastKey);
      setActiveSirRun(lastKey);
    } else if (resultsByKey.pure) {
      syncSirRunPicker('pure');
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      setActiveSirRun('pure');
    } else {
      const dk = Object.keys(dynamicRuns).sort();
      if (dk.length) {
        const lastKey = dk[dk.length - 1];
        syncSirRunPicker(lastKey);
        setActiveSirRun(lastKey);
      }
    }
    const strip = document.getElementById('sirResultsStrip');
    if (strip) strip.hidden = false;
  }

  async function tryLoadFromUrl() {
    const p = new URLSearchParams(window.location.search);
    const out = p.get('output_dir');
    const model = p.get('model') || 'pure';
    const strategy = p.get('strategy');
    if (!out) return;
    try {
      let url = `/api/sir-results?output_dir=${encodeURIComponent(out)}&model=${encodeURIComponent(model)}`;
      if (model === 'dynamic') {
        const stratQ = strategy || 'betweenness';
        url += `&strategy=${encodeURIComponent(stratQ)}`;
        url += `&intervention_day=${encodeURIComponent(p.get('intervention_day') || '1')}`;
      }
      const r = await fetch(url);
      if (!r.ok) return;
      const d = await r.json();
      const pseudo = {
        peak_day: d.statistics.peak_day,
        peak_infected: d.statistics.peak_infected,
        final_day: d.statistics.final_day,
        history: d.history,
        output_directory: out,
        strategy: strategy || 'betweenness',
        intervention_day: parseInt(p.get('intervention_day') || '1', 10) || 1,
      };
      if (model === 'dynamic') {
        dynamicResults = pseudo;
        pureResults = null;
        switchModel('dynamic');
        const rk = `${pseudo.strategy}:${pseudo.intervention_day}`;
        dynamicRuns[rk] = pseudo;
        displayDynamicResults(pseudo);
      } else {
        pureResults = pseudo;
        dynamicResults = null;
        switchModel('pure');
        displayPureResults(pseudo);
      }
      updateResultsStrip(pseudo);
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
    } catch (e) {
      console.warn(e);
    }
  }

  async function reloadAfterDataChange() {
    pureResults = null;
    dynamicResults = null;
    resultsByKey.pure = null;
    activeSirRunKey = 'pure';
    Object.keys(dynamicRuns).forEach((k) => delete dynamicRuns[k]);
    const picker = document.getElementById('sirRunPicker');
    if (picker) picker.hidden = true;
    if (simLineChart) {
      simLineChart.destroy();
      simLineChart = null;
    }
    if (simCompareChart) {
      simCompareChart.destroy();
      simCompareChart = null;
    }
    const summary = await loadSidebarSummary();
    await tryLoadFromUrl();
    if (!new URLSearchParams(window.location.search).get('output_dir')) {
      await restoreSavedSirRuns(summary);
    }
  }

  window.onSharedDataReady = reloadAfterDataChange;

  async function init() {
    window.SharedNav?.init({
      onLangChange: () => {
        syncSirRunPicker(activeSirRunKey);
        refreshSirChartsForTab(getActiveSirResultTab());
        resizeSirCharts();
      },
    });
    setupSirRangeInputs();
    const resultsPanel = document.querySelector('.sir-page-main .sim-results-panel');
    if (resultsPanel && typeof ResizeObserver !== 'undefined') {
      const ro = new ResizeObserver(() => resizeSirCharts());
      ro.observe(resultsPanel);
    }
    window.addEventListener('resize', resizeSirCharts);
    document.querySelectorAll('.sim-tab-model').forEach((btn) => {
      btn.addEventListener('click', () => switchModel(btn.dataset.model));
    });
    document.querySelectorAll('.result-tab-btn[data-sir-tab]').forEach((btn) => {
      btn.addEventListener('click', (e) => switchSirResultTab(btn.dataset.sirTab, e));
    });
    document.getElementById('btnRunPureSimulation')?.addEventListener('click', runPureSimulation);
    document.getElementById('btnRunDynamicSimulation')?.addEventListener('click', runDynamicSimulation);
    document.getElementById('sirRunSelect')?.addEventListener('change', (e) => {
      setActiveSirRun(e.target.value);
    });
    const summary = await loadSidebarSummary();
    await tryLoadFromUrl();
    if (!new URLSearchParams(window.location.search).get('output_dir')) {
      await restoreSavedSirRuns(summary);
    }
  }

  window.addEventListener('DOMContentLoaded', () => {
    init().catch((err) => console.warn(err));
  });
})();
