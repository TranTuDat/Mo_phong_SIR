/**
 * Trang mô phỏng SIR độc lập (/simulation)
 */
(function () {
  let simLineChart = null;
  let simCompareChart = null;
  let pureResults = null;
  let dynamicResults = null;
  let currentSimModel = 'pure';

  const I18N = {
    vi: {
      'sir.docTitle': 'Mô phỏng SIR — InfoOps Analyzer',
      'brand.sirSubtitle': 'Mô hình SIR trên đồ thị xã hội',
      'nav.networkOverview': 'Tổng quan mạng',
      'nav.sirActive': 'Mô phỏng SIR',
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
      'sir.cmpDynBet': 'Can thiệp (betweenness)',
      'sir.cmpDynDeg': 'Can thiệp (degree)',
      'sir.cmpPeak': 'Ngày đỉnh',
      'sir.cmpPeakI': 'Đỉnh I',
      'sir.cmpFinal': 'Ngày kết thúc',
      'sir.hintCompareHtml':
        'Gợi ý: chạy <strong>SIR thuần</strong> trước, sau đó chạy <strong>SIR + can thiệp</strong> để xem so sánh.',
      'sir.dataHintHtml':
        'Chưa có output. Về <a href=\"/\">Tổng quan</a> và bấm «Tạo dữ liệu» trước.',
      status_running_pure: 'Đang chạy SIR thuần trên mạng hiện tại…',
      status_running_dyn: 'Đang chạy SIR + can thiệp…',
      status_done_pure: 'Hoàn thành SIR thuần.',
      status_done_dyn: 'Hoàn thành SIR + can thiệp.',
      status_need_params: 'Vui lòng điền đầy đủ tham số',
    },
    en: {
      'sir.docTitle': 'SIR Simulation — InfoOps Analyzer',
      'brand.sirSubtitle': 'SIR model on a social graph',
      'nav.networkOverview': 'Network overview',
      'nav.sirActive': 'SIR simulation',
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
      'sir.cmpDynBet': 'Intervention (betweenness)',
      'sir.cmpDynDeg': 'Intervention (degree)',
      'sir.cmpPeak': 'Peak day',
      'sir.cmpPeakI': 'Peak I',
      'sir.cmpFinal': 'End day',
      'sir.hintCompareHtml':
        'Tip: run <strong>Pure SIR</strong> first, then run <strong>SIR + intervention</strong> to compare.',
      'sir.dataHintHtml':
        'No output yet. Go to <a href=\"/\">Dashboard</a> and click “Generate data” first.',
      status_running_pure: 'Running pure SIR…',
      status_running_dyn: 'Running SIR + intervention…',
      status_done_pure: 'Pure SIR completed.',
      status_done_dyn: 'SIR + intervention completed.',
      status_need_params: 'Please provide all parameters',
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
    } catch (err) {
      console.warn(err);
      const hint = document.getElementById('dataHint');
      if (hint) hint.style.display = 'block';
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

  const resultsByKey = {
    pure: null,
    dyn_bet: null,
    dyn_deg: null,
  };

  async function runDynamicSimulation() {
    const btn = document.getElementById('btnRunDynamicSimulation');
    const transmission = parseFloat(document.getElementById('dynTrans').value);
    const recovery = parseFloat(document.getElementById('dynRecov').value);
    const days = parseInt(document.getElementById('dynDays').value, 10);
    const topK = parseInt(document.getElementById('topK').value, 10);
    const seed = parseInt(document.getElementById('dynSeed').value, 10);
    const strategy = document.getElementById('interventionStrategy')?.value || 'betweenness';
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
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Lỗi mô phỏng');
      dynamicResults = data;
      resultsByKey[strategy === 'degree' ? 'dyn_deg' : 'dyn_bet'] = data;
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
      strat === 'degree'
        ? (getLang() === 'en' ? 'degree' : 'degree')
        : (getLang() === 'en' ? 'betweenness' : 'betweenness');
    document.getElementById('detailRuntimeSim').textContent =
      data.top_k != null
        ? (getLang() === 'en'
            ? `Immunize top-${data.top_k} nodes by ${stratLabel} (day 1)`
            : `Miễn nhiễm top-${data.top_k} nút theo ${stratLabel} (ngày 1)`)
        : '—';
  }

  function displayPureResults(data) {
    currentSimModel = 'pure';
    resultsByKey.pure = data;
    updateStatsSim(data, 'SIR thuần');
    drawSirSimChart(data.history, 'Đường cong S-I-R (SIR thuần)');
  }

  function displayDynamicResults(data) {
    currentSimModel = 'dynamic';
    updateStatsSim(data, 'SIR + can thiệp (miễn nhiễm động)');
    // Always refresh comparison if pure exists and at least one dynamic run exists
    if (resultsByKey.pure && (resultsByKey.dyn_bet || resultsByKey.dyn_deg)) {
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
    const labels = pure.history.map((h) => h.day);
    const pureI = pure.history.map((h) => h.I);
    const bet = resultsByKey.dyn_bet;
    const deg = resultsByKey.dyn_deg;
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
    if (bet) {
      datasets.push({
        label: getLang() === 'en' ? 'Intervention (betweenness) — I' : 'Can thiệp (betweenness) — I',
        data: bet.history.map((h) => h.I),
        borderColor: '#2563eb',
        backgroundColor: 'rgba(37, 99, 235, 0.08)',
        tension: 0.35,
        fill: true,
        borderWidth: 2,
      });
    }
    if (deg) {
      datasets.push({
        label: getLang() === 'en' ? 'Intervention (degree) — I' : 'Can thiệp (degree) — I',
        data: deg.history.map((h) => h.I),
        borderColor: '#34a853',
        backgroundColor: 'rgba(52, 168, 83, 0.08)',
        tension: 0.35,
        fill: true,
        borderWidth: 2,
      });
    }
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
    if (!pure) return;
    const bet = resultsByKey.dyn_bet;
    const deg = resultsByKey.dyn_deg;

    const safe = (v) => (v == null ? '—' : String(v));
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = safe(v);
    };

    set('compPeakDayPureSim', pure.peak_day);
    set('compPeakInfPureSim', pure.peak_infected);
    set('compFinalDayPureSim', pure.final_day);

    set('compPeakDayDynBetSim', bet?.peak_day);
    set('compPeakInfDynBetSim', bet?.peak_infected);
    set('compFinalDayDynBetSim', bet?.final_day);

    set('compPeakDayDynDegSim', deg?.peak_day);
    set('compPeakInfDynDegSim', deg?.peak_infected);
    set('compFinalDayDynDegSim', deg?.final_day);
  }

  function displayComparisonSir() {
    switchSirResultTab('comparison', {
      currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="comparison"]'),
    });
  }

  async function tryLoadFromUrl() {
    const p = new URLSearchParams(window.location.search);
    const out = p.get('output_dir');
    const model = p.get('model') || 'pure';
    if (!out) return;
    try {
      const r = await fetch(
        `/api/sir-results?output_dir=${encodeURIComponent(out)}&model=${encodeURIComponent(model)}`
      );
      if (!r.ok) return;
      const d = await r.json();
      const pseudo = {
        peak_day: d.statistics.peak_day,
        peak_infected: d.statistics.peak_infected,
        final_day: d.statistics.final_day,
        history: d.history,
        output_directory: out,
      };
      if (model === 'dynamic') {
        dynamicResults = pseudo;
        pureResults = null;
        switchModel('dynamic');
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

  function init() {
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
    loadSidebarSummary();
    tryLoadFromUrl();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
