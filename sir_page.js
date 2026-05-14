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

  const I18N = {
    vi: {
      'sir.docTitle': 'Mô phỏng SIR — InfoOps Analyzer',
      'brand.sirSubtitle': 'Mô hình SIR trên đồ thị xã hội',
      'nav.networkOverview': 'Tổng quan mạng',
      'nav.sirActive': 'Mô phỏng SIR',
      'nav.recsPage': 'Gợi ý can thiệp',
      'sidebar.nodesShort': 'Node (bộ hiện tại)',
      'sidebar.edgesShort': 'Edge',
      'sir.pageTitle': 'Mô phỏng SIR trên mạng xã hội',
      'sir.backDash': 'Về tổng quan',
      'sir.intro':
        'Điều chỉnh tham số rồi chạy mô phỏng trên <strong>bộ dữ liệu output mới nhất</strong>. Sau khi chạy, hệ thống hiển thị biểu đồ S–I–R, đỉnh dịch và ngày kết thúc.',
      'sir.params': 'Tham số mô hình',
      'sir.tabPure': 'SIR thuần',
      'sir.tabDyn': 'SIR + can thiệp',
      'sir.beta': 'Tỷ lệ lây (β)',
      'sir.gamma': 'Tỷ lệ hồi phục (γ)',
      'sir.maxDays': 'Số ngày tối đa',
      'sir.seed': 'Seed',
      'sir.topK': 'Top-k miễn nhiễm',
      'sir.strategy': 'Chiến lược can thiệp',
      'sir.strategyBet': 'Theo betweenness',
      'sir.strategyDeg': 'Theo degree',
      'sir.strategyEig': 'Theo eigenvector',
      'sir.interventionDay': 'Ngày can thiệp',
      'sir.interventionDayHint': '(1 = ngày đầu tiên của mô phỏng; có thể chạy nhiều lần với ngày khác nhau để so sánh)',
      'sir.runPure': 'Chạy SIR thuần',
      'sir.runDyn': 'Chạy SIR + can thiệp',
      'sir.stripPeak': 'Ngày đỉnh',
      'sir.stripPeakI': 'Max I',
      'sir.stripFinal': 'Ngày kết thúc',
      'sir.stripS': 'S cuối',
      'sir.tabChart': 'Đồ thị',
      'sir.tabStats': 'Chỉ số',
      'sir.tabCompare': 'So sánh',
      'sir.chartFoot': 'Trục ngang: ngày mô phỏng · Trục dọc: số cá thể trong từng trạng thái.',
      'sir.statPeakLabel': 'Ngày đỉnh',
      'sir.statPeakI': 'Max I',
      'sir.statFinal': 'Ngày kết thúc',
      'sir.statR': 'R cuối',
      'sir.detailTitle': 'Chi tiết lần chạy',
      'sir.rowModel': 'Mô hình',
      'sir.rowRates': 'β / γ',
      'sir.rowOut': 'Thư mục kết quả',
      'sir.rowNote': 'Ghi chú',
      'sir.cmpMetric': 'Chỉ số',
      'sir.cmpPure': 'SIR thuần',
      'sir.cmpDynCol': 'Can thiệp',
      'sir.cmpPeak': 'Ngày đỉnh',
      'sir.cmpPeakI': 'Đỉnh I',
      'sir.cmpFinal': 'Ngày kết thúc',
      'sir.footerNote': 'Dữ liệu mạng (gốc output_*) + simulation_sir/pure | simulation_sir/dynamic/…',
      'sir.hintCompareHtml':
        'Gợi ý: chạy <strong>SIR thuần</strong> trước, sau đó chạy một hoặc nhiều lần <strong>SIR + can thiệp</strong> (có thể đổi chiến lược và/hoặc <strong>ngày can thiệp</strong>) rồi mở tab <strong>So sánh</strong>.',
      'sir.dataHintHtml':
        'Chưa có output. Về <a href=\"/\">Tổng quan</a> và bấm «Tạo dữ liệu» trước.',
      status_running_pure: 'Đang chạy SIR thuần trên mạng hiện tại…',
      status_running_dyn: 'Đang chạy SIR + can thiệp…',
      status_done_pure: 'Hoàn thành SIR thuần.',
      status_done_dyn: 'Hoàn thành SIR + can thiệp.',
      status_need_params: 'Vui lòng điền đầy đủ tham số',
      status_restored_sir: 'Đã tải lại {n} mô phỏng đã lưu trong thư mục output.',
    },
    en: {
      'sir.docTitle': 'SIR Simulation — InfoOps Analyzer',
      'brand.sirSubtitle': 'SIR model on a social graph',
      'nav.networkOverview': 'Network overview',
      'nav.sirActive': 'SIR simulation',
      'nav.recsPage': 'Intervention suggestions',
      'sidebar.nodesShort': 'Nodes (current)',
      'sidebar.edgesShort': 'Edges',
      'sir.pageTitle': 'SIR simulation on social network',
      'sir.backDash': 'Back to dashboard',
      'sir.intro':
        'Tune parameters and run on the <strong>latest output dataset</strong>. After running, the system shows the S–I–R chart, peak day, and end day.',
      'sir.params': 'Model parameters',
      'sir.tabPure': 'Pure SIR',
      'sir.tabDyn': 'SIR + intervention',
      'sir.beta': 'Transmission (β)',
      'sir.gamma': 'Recovery (γ)',
      'sir.maxDays': 'Max days',
      'sir.seed': 'Seed',
      'sir.topK': 'Top-k immunized',
      'sir.strategy': 'Intervention strategy',
      'sir.strategyBet': 'By betweenness',
      'sir.strategyDeg': 'By degree',
      'sir.strategyEig': 'By eigenvector',
      'sir.interventionDay': 'Intervention day',
      'sir.interventionDayHint': '(1 = first simulation day; run again with another day to compare)',
      'sir.runPure': 'Run pure SIR',
      'sir.runDyn': 'Run SIR + intervention',
      'sir.stripPeak': 'Peak day',
      'sir.stripPeakI': 'Peak I',
      'sir.stripFinal': 'End day',
      'sir.stripS': 'Final S',
      'sir.tabChart': 'Chart',
      'sir.tabStats': 'Stats',
      'sir.tabCompare': 'Compare',
      'sir.chartFoot': 'X-axis: day · Y-axis: population in each state.',
      'sir.statPeakLabel': 'Peak day',
      'sir.statPeakI': 'Peak I',
      'sir.statFinal': 'End day',
      'sir.statR': 'Final R',
      'sir.detailTitle': 'Run details',
      'sir.rowModel': 'Model',
      'sir.rowRates': 'β / γ',
      'sir.rowOut': 'Results folder',
      'sir.rowNote': 'Note',
      'sir.cmpMetric': 'Metric',
      'sir.cmpPure': 'Pure SIR',
      'sir.cmpDynCol': 'Intervention',
      'sir.cmpPeak': 'Peak day',
      'sir.cmpPeakI': 'Peak I',
      'sir.cmpFinal': 'End day',
      'sir.footerNote': 'Network CSVs (output_* root) + simulation_sir/pure | simulation_sir/dynamic/…',
      'sir.hintCompareHtml':
        'Tip: run <strong>Pure SIR</strong> first, then run <strong>SIR + intervention</strong> one or more times (change strategy and/or <strong>intervention day</strong>), then open <strong>Compare</strong>.',
      'sir.dataHintHtml':
        'No output yet. Go to <a href=\"/\">Dashboard</a> and click “Generate data” first.',
      status_running_pure: 'Running pure SIR…',
      status_running_dyn: 'Running SIR + intervention…',
      status_done_pure: 'Pure SIR completed.',
      status_done_dyn: 'SIR + intervention completed.',
      status_need_params: 'Please provide all parameters',
      status_restored_sir: 'Reloaded {n} saved simulation(s) from the output folder.',
    }
  };

  function getLang() {
    const raw = localStorage.getItem('lang') || 'vi';
    return raw === 'en' ? 'en' : 'vi';
  }

  function setLang(lang) {
    const next = lang === 'en' ? 'en' : 'vi';
    localStorage.setItem('lang', next);
    document.documentElement.lang = next;
    const btn = document.getElementById('langToggle');
    if (btn) {
      btn.textContent = next === 'en' ? 'VI' : 'EN';
      btn.title = next === 'en' ? 'Tiếng Việt' : 'English';
    }
    translatePage(next);
  }

  function translatePage(lang) {
    const dict = I18N[lang] || I18N.vi;
    document.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;
      if (dict[key] != null) el.textContent = dict[key];
    });
    document.querySelectorAll('[data-i18n-html]').forEach((el) => {
      const key = el.getAttribute('data-i18n-html');
      if (!key) return;
      if (dict[key] != null) el.innerHTML = dict[key];
    });
    const t = dict['sir.docTitle'];
    if (t) document.title = t;
    if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
      updateComparisonTableSim();
    }
  }

  function initTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    const t = document.getElementById('themeToggle');
    if (t) t.textContent = saved === 'dark' ? '☀️' : '🌙';
  }

  function toggleTheme() {
    const cur = document.documentElement.getAttribute('data-theme');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    const t = document.getElementById('themeToggle');
    if (t) t.textContent = next === 'dark' ? '☀️' : '🌙';
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

  function switchSirResultTab(tab, evt) {
    document.querySelectorAll('.sim-results-panel .result-tab-content').forEach((el) => {
      el.classList.remove('active');
    });
    document.querySelectorAll('.sim-results-panel .result-tab-btn').forEach((btn) => {
      btn.classList.remove('active');
    });
    const pane = document.getElementById(`sir-${tab}-tab`);
    if (pane) pane.classList.add('active');
    if (evt && evt.currentTarget) evt.currentTarget.classList.add('active');
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
      showSimStatus(I18N[getLang()].status_need_params, 'error');
      return;
    }
    btn.disabled = true;
    showSimStatus(I18N[getLang()].status_running_pure, 'loading');
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
      displayPureResults(data);
      updateResultsStrip(data);
      showSimStatus(I18N[getLang()].status_done_pure, 'success');
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
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
      showSimStatus(I18N[getLang()].status_need_params, 'error');
      return;
    }
    btn.disabled = true;
    showSimStatus(I18N[getLang()].status_running_dyn, 'loading');
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
      dynamicResults = data;
      const rk = `${strategy}:${data.intervention_day != null ? data.intervention_day : interventionDay}`;
      dynamicRuns[rk] = data;
      displayDynamicResults(data);
      updateResultsStrip(data);
      showSimStatus(I18N[getLang()].status_done_dyn, 'success');
      switchSirResultTab(pureResults ? 'comparison' : 'chart', {
        currentTarget: document.querySelector(
          `.sim-results-panel .result-tab-btn[data-sir-tab="${pureResults ? 'comparison' : 'chart'}"]`
        ),
      });
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
    currentSimModel = 'pure';
    resultsByKey.pure = data;
    updateStatsSim(data, 'SIR thuần');
    drawSirSimChart(data.history, 'Đường cong S-I-R (SIR thuần)');
    if (Object.keys(dynamicRuns).length) {
      drawSirComparisonChart();
      updateComparisonTableSim();
    }
  }

  function displayDynamicResults(data) {
    currentSimModel = 'dynamic';
    updateStatsSim(data, 'SIR + can thiệp (miễn nhiễm động)');
    // Always refresh comparison if pure exists and at least one dynamic run exists
    if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
      drawSirComparisonChart();
      updateComparisonTableSim();
      displayComparisonSir();
      return;
    }
    drawSirSimChart(data.history, 'Đường cong S-I-R (SIR + can thiệp)');
  }

  function drawSirSimChart(history, titleText) {
    const canvas = document.getElementById('sirSimChart');
    if (!canvas || typeof Chart === 'undefined') return;
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
        label: getLang() === 'en' ? 'Pure SIR — I' : 'SIR thuần — I',
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
      const label =
        getLang() === 'en'
          ? `Intervention (${sShort}, day ${day}) — I`
          : `Can thiệp (${sShort}, ngày ${day}) — I`;
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
            text: getLang() === 'en' ? 'Compare concurrent infected (I)' : 'So sánh số ca nhiễm đồng thời (I)',
          },
        },
        scales: {
          y: { beginAtZero: true },
        },
      },
    });
  }

  function updateComparisonTableSim() {
    const pure = resultsByKey.pure;
    const headRow = document.getElementById('comparisonSimTableHeadRow');
    const bodyEl = document.getElementById('comparisonSimTableBody');
    if (!pure || !headRow || !bodyEl) return;

    const keys = Object.keys(dynamicRuns).sort();
    const lang = getLang();
    const dict = I18N[lang] || I18N.vi;

    headRow.replaceChildren();
    const thMetric = document.createElement('th');
    thMetric.setAttribute('data-i18n', 'sir.cmpMetric');
    thMetric.textContent = dict['sir.cmpMetric'];
    const thPure = document.createElement('th');
    thPure.setAttribute('data-i18n', 'sir.cmpPure');
    thPure.textContent = dict['sir.cmpPure'];
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
      th.textContent = `${dict['sir.cmpDynCol']}: ${sShort}, ${lang === 'en' ? 'day' : 'ngày'} ${day}`;
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
      td0.textContent = dict[def.tKey];
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

  function displayComparisonSir() {
    switchSirResultTab('comparison', {
      currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="comparison"]'),
    });
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
    const msg = (I18N[getLang()] || I18N.vi).status_restored_sir || '';
    showSimStatus(msg.replace(/\{n\}/g, String(restored)), 'success');
    if (resultsByKey.pure && Object.keys(dynamicRuns).length) {
      const dkLast = Object.keys(dynamicRuns).sort();
      dynamicResults = dynamicRuns[dkLast[dkLast.length - 1]];
      drawSirComparisonChart();
      updateComparisonTableSim();
      switchSirResultTab('comparison', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="comparison"]'),
      });
    } else if (resultsByKey.pure) {
      displayPureResults(resultsByKey.pure);
    } else {
      const dk = Object.keys(dynamicRuns).sort();
      if (dk.length) {
        const last = dynamicRuns[dk[dk.length - 1]];
        dynamicResults = last;
        displayDynamicResults(last);
      }
    }
    const dk = Object.keys(dynamicRuns).sort();
    const stripData = resultsByKey.pure || (dk.length ? dynamicRuns[dk[dk.length - 1]] : null);
    if (stripData) updateResultsStrip(stripData);
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

  async function init() {
    initTheme();
    document.getElementById('themeToggle')?.addEventListener('click', toggleTheme);
    setLang(getLang());
    document.getElementById('langToggle')?.addEventListener('click', () => setLang(getLang() === 'en' ? 'vi' : 'en'));
    setupSirRangeInputs();
    document.querySelectorAll('.sim-tab-model').forEach((btn) => {
      btn.addEventListener('click', () => switchModel(btn.dataset.model));
    });
    document.querySelectorAll('.result-tab-btn[data-sir-tab]').forEach((btn) => {
      btn.addEventListener('click', (e) => switchSirResultTab(btn.dataset.sirTab, e));
    });
    document.getElementById('btnRunPureSimulation')?.addEventListener('click', runPureSimulation);
    document.getElementById('btnRunDynamicSimulation')?.addEventListener('click', runDynamicSimulation);
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
