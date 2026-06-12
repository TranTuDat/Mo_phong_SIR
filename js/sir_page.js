/**
 * Trang mô phỏng SIR độc lập (/simulation)
 */
(function () {
  let simLineChart = null;
  let simCompareChart = null;
  let pureResults = null;
  let dynamicResults = null;
  let currentSimModel = 'pure';
  /** @type {Record<string, object>} misinfo_mode → kết quả SIR thuần */
  const pureRuns = {};
  /** @type {Record<string, object>} key = `dyn:${misinfo}:${strategy}:${day}:${k}` */
  const dynamicRuns = {};
  /** `pure:<misinfo>` | `dyn:...` — lần chạy đang xem */
  let activeSirRunKey = 'pure:random';

  function t(key, vars) {
    return window.I18N && window.I18N.t ? window.I18N.t(key, vars) : key;
  }

  function getLang() {
    return window.I18N && window.I18N.getLang ? window.I18N.getLang() : 'vi';
  }

  async function fetchJson(path) {
    const url = window.MauShell?.withOutputDir ? window.MauShell.withOutputDir(path) : path;
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) throw new Error(`API lỗi ${r.status}`);
    return r.json();
  }

  function getActiveOutputDir() {
    return window.MauShell?.getActiveOutputDir?.()?.trim() || '';
  }

  /** Bộ dữ liệu đang chọn (localStorage) hoặc từ /api/summary — dùng cho POST mô phỏng. */
  async function resolveSimulationOutputDir() {
    const stored = getActiveOutputDir();
    if (stored) return stored;
    const summary = await fetchJson('/api/summary').catch(() => null);
    return summary?.output_folder || '';
  }

  async function simulationRequestBody(extra) {
    const output_dir = await resolveSimulationOutputDir();
    if (!output_dir) {
      throw new Error(
        getLang() === 'en'
          ? 'No dataset selected. Open «Input data» and generate or pick an output folder.'
          : 'Chưa chọn bộ dữ liệu. Mở «Nhập dữ liệu» để tạo mới hoặc chọn output có sẵn.'
      );
    }
    return { output_dir, ...extra };
  }

  async function loadSidebarSummary(force) {
    try {
      const data = window.MauShell?.fetchSummaryCached
        ? await window.MauShell.fetchSummaryCached(!!force)
        : await fetchJson('/api/summary');
      const n = document.getElementById('summary-nodes');
      const e = document.getElementById('summary-edges');
      if (n) n.textContent = data.nodes;
      if (e) e.textContent = data.edges;
      return data;
    } catch (err) {
      console.warn(err);
      return null;
    }
  }

  function cacheOutputDir(summary) {
    const stored = getActiveOutputDir();
    if (stored) return stored;
    const raw = summary?.output_folder || '';
    if (!raw) return '';
    const parts = String(raw).replace(/\\/g, '/').split('/').filter(Boolean);
    return parts.length ? parts[parts.length - 1] : String(raw);
  }

  function persistSirSession(summary) {
    const out = cacheOutputDir(summary);
    const cache = window.MauSessionCache;
    if (!out || !cache) return;
    const count = Object.keys(pureRuns).length + Object.keys(dynamicRuns).length;
    if (!count) return;
    cache.set(cache.KIND.SIR, out, {
      pureRuns: { ...pureRuns },
      dynamicRuns: { ...dynamicRuns },
      activeSirRunKey,
    });
    cache.remove(cache.KIND.RECOMMENDATIONS, out);
  }

  function hydrateSirSessionFromCache(summary) {
    const out = cacheOutputDir(summary);
    const cached = window.MauSessionCache?.get(window.MauSessionCache.KIND.SIR, out);
    if (!cached) return false;
    const pr = cached.pureRuns || {};
    const dr = cached.dynamicRuns || {};
    if (!Object.keys(pr).length && !Object.keys(dr).length) return false;
    Object.keys(pureRuns).forEach((k) => delete pureRuns[k]);
    Object.keys(dynamicRuns).forEach((k) => delete dynamicRuns[k]);
    Object.assign(pureRuns, pr);
    Object.assign(dynamicRuns, dr);
    activeSirRunKey = cached.activeSirRunKey || activeSirRunKey;
    return true;
  }

  async function bootstrapSirFromCacheOrApi(summary) {
    if (hydrateSirSessionFromCache(summary)) {
      const all = listSirRunOptions();
      if (all.length) {
        const key = all.some((o) => o.key === activeSirRunKey)
          ? activeSirRunKey
          : all[all.length - 1].key;
        switchSirResultTab('chart', {
          currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
        });
        syncSirRunPicker(key);
        setActiveSirRun(key);
      }
      const strip = document.getElementById('sirResultsStrip');
      if (strip) strip.hidden = false;
      updateComparisonEmptyState();
      updateReportButton();
      return;
    }
    await restoreSavedSirRuns(summary);
    persistSirSession(summary);
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

  function pureRunKey(mode) {
    return `pure:${mode || misinfoSourceMode() || 'random'}`;
  }

  function isPureRunKey(key) {
    return String(key || '').startsWith('pure:');
  }

  function parsePureRunKey(key) {
    return String(key || '').replace(/^pure:/, '') || 'random';
  }

  function dynamicRunKeyFromRun(run) {
    const m = run.misinfo_source_mode || misinfoSourceMode();
    const strat = run.strategy || 'betweenness';
    const day = run.intervention_day != null ? run.intervention_day : 1;
    const k = run.top_k != null ? run.top_k : 0;
    return `dyn:${m}:${strat}:${day}:${k}`;
  }

  /** Parse khóa: dyn:misinfo:strategy:day:k hoặc legacy strategy:day:k */
  function parseDynamicRunKey(key) {
    const s = String(key || '');
    if (s.startsWith('dyn:')) {
      const parts = s.split(':');
      const kPart = parts.length >= 5 ? parseInt(parts[4], 10) : null;
      return {
        misinfo_source_mode: parts[1] || 'random',
        strategy: parts[2] || 'betweenness',
        intervention_day: parseInt(parts[3], 10) || 1,
        top_k: Number.isFinite(kPart) ? kPart : null,
      };
    }
    const parts = s.split(':');
    const strat = parts[0] || 'betweenness';
    const day = parseInt(parts[1], 10) || 1;
    const k = parts.length >= 3 ? parseInt(parts[2], 10) : null;
    return {
      misinfo_source_mode: 'random',
      strategy: strat,
      intervention_day: day,
      top_k: Number.isFinite(k) ? k : null,
    };
  }

  function misinfoModeShortLabel(mode) {
    const labels = {
      random: getLang() === 'en' ? 'Random' : 'Ngẫu nhiên',
      betweenness: 'Betweenness',
      degree: 'Degree',
      eigenvector: 'Eigenvector',
      pagerank: 'PageRank',
    };
    return labels[mode] || mode;
  }

  function getRunByKey(key) {
    if (isPureRunKey(key)) return pureRuns[parsePureRunKey(key)] || null;
    return dynamicRuns[key] || null;
  }

  function sortPureRunModes(modes) {
    return modes.slice().sort((a, b) => a.localeCompare(b));
  }

  function listAllComparableRuns() {
    const items = [];
    sortPureRunModes(Object.keys(pureRuns)).forEach((mode) => {
      items.push({
        key: pureRunKey(mode),
        type: 'pure',
        run: pureRuns[mode],
        misinfo_source_mode: mode,
      });
    });
    sortDynamicRunKeys(Object.keys(dynamicRuns)).forEach((key) => {
      const p = parseDynamicRunKey(key);
      items.push({
        key,
        type: 'dynamic',
        run: dynamicRuns[key],
        misinfo_source_mode: p.misinfo_source_mode,
        strategy: p.strategy,
        intervention_day: p.intervention_day,
        top_k: p.top_k,
      });
    });
    return items;
  }

  function getPrimaryPureRun() {
    const cur = misinfoSourceMode();
    if (pureRuns[cur]) return pureRuns[cur];
    const modes = Object.keys(pureRuns);
    return modes.length ? pureRuns[modes[0]] : null;
  }

  function strategyShortName(strat) {
    const map = {
      random: 'sir.strategyShortRandom',
      betweenness: 'sir.strategyShortBetweenness',
      degree: 'sir.strategyShortDegree',
      eigenvector: 'sir.strategyShortEigenvector',
      pagerank: 'sir.strategyShortPagerank',
    };
    return t(map[strat] || 'sir.strategyShortBetweenness');
  }

  function simModelLabel(model) {
    return model === 'pure' ? t('sir.modelPure') : t('sir.modelDyn');
  }

  function misinfoSourceMode() {
    return document.getElementById('misinfoSourceMode')?.value || 'random';
  }

  function misinfoPayloadExtra() {
    return {
      misinfo_source_mode: misinfoSourceMode(),
      num_initial_sources: 1,
    };
  }

  function formatMisinfoSourceLabel(data) {
    const mode = data?.misinfo_source_mode || misinfoSourceMode();
    const nodes = data?.misinfo_source_nodes || [];
    const ids = data?.misinfo_source_node_ids || nodes.map((n) => n.id);
    const modeLabels = {
      random: getLang() === 'en' ? 'Random' : 'Ngẫu nhiên',
      betweenness: 'Betweenness',
      degree: 'Degree',
      eigenvector: 'Eigenvector',
      pagerank: 'PageRank',
    };
    const modeText = modeLabels[mode] || mode;
    const names = nodes.length
      ? nodes.map((n) => n.name || n.id).join(', ')
      : ids.map((id) => String(id)).join(', ');
    return `${modeText}${names ? ` — ${names}` : ''}`;
  }

  function sortDynamicRunKeys(keys) {
    return keys.slice().sort((a, b) => {
      const pa = parseDynamicRunKey(a);
      const pb = parseDynamicRunKey(b);
      if (pa.misinfo_source_mode !== pb.misinfo_source_mode) {
        return pa.misinfo_source_mode.localeCompare(pb.misinfo_source_mode);
      }
      if (pa.strategy !== pb.strategy) return pa.strategy.localeCompare(pb.strategy);
      if (pa.intervention_day !== pb.intervention_day) return pa.intervention_day - pb.intervention_day;
      return (pa.top_k ?? 0) - (pb.top_k ?? 0);
    });
  }

  function formatComparisonColumnLabel(item) {
    const src = misinfoModeShortLabel(item.misinfo_source_mode || 'random');
    if (item.type === 'pure') {
      return `${t('sir.comparisonPurePrefix')} (${src})`;
    }
    const strat = strategyShortName(item.strategy || 'betweenness');
    const day = item.intervention_day != null ? item.intervention_day : 1;
    const k = item.top_k != null ? item.top_k : '—';
    const dayWord = t('sir.comparisonDayWord');
    return `${src} · ${strat} ${dayWord} ${day}, k=${k}`;
  }

  function formatComparisonSeriesLabel(item) {
    const base = formatComparisonColumnLabel(item);
    return `${base} — I`;
  }

  function clearDynamicRuns() {
    Object.keys(dynamicRuns).forEach((k) => delete dynamicRuns[k]);
    dynamicResults = null;
    if (simCompareChart) {
      simCompareChart.destroy();
      simCompareChart = null;
    }
  }

  function updateReportButton() {
    const btn = document.getElementById('btnReport');
    if (!btn) return;
    const hasData = listAllComparableRuns().length > 0;
    btn.disabled = !hasData;
    btn.title = hasData ? t('sir.exportPdf') : t('sir.exportPdfNeedPure');
  }

  async function ensureAllRunsLoadedForExport(outputFolder) {
    if (!outputFolder) return;
    try {
      const list = await fetchJson(
        `/api/sir-saved-runs?output_dir=${encodeURIComponent(outputFolder)}`
      );
      for (const item of list.pure_runs || (list.pure_available ? [{ misinfo_source_mode: 'random' }] : [])) {
        const mode = item.misinfo_source_mode || 'random';
        if (pureRuns[mode]) continue;
        try {
          const d = await fetchSirResultsFromApi(outputFolder, 'pure', null, null, null, mode);
          const run = sirApiDataToRunModel(d, 'pure');
          pureRuns[mode] = run;
        } catch (e) {
          console.warn('load pure for export', mode, e);
        }
      }
      for (const item of list.dynamic_runs || []) {
        const rk = dynamicRunKeyFromRun(item);
        if (dynamicRuns[rk]) continue;
        try {
          const d = await fetchSirResultsFromApi(
            outputFolder,
            'dynamic',
            item.strategy,
            item.intervention_day,
            item.top_k,
            item.misinfo_source_mode || 'random'
          );
          const run = sirApiDataToRunModel(d, 'dynamic');
          dynamicRuns[rk] = run;
        } catch (e) {
          console.warn('load run for export', rk, e);
        }
      }
    } catch (e) {
      console.warn('ensureAllRunsLoadedForExport', e);
    }
  }

  function slimRunForExport(run, model) {
    if (!run) return null;
    return {
      model,
      strategy: run.strategy,
      intervention_day: run.intervention_day,
      top_k: run.top_k,
      misinfo_source_mode: run.misinfo_source_mode,
      peak_day: run.peak_day,
      peak_infected: run.peak_infected,
      final_day: run.final_day,
      total_infected: run.total_infected != null ? run.total_infected : totalInfectedFromData(run),
      history: run.history || [],
    };
  }

  function collectSirExportPayload(outputFolder) {
    const pure = slimRunForExport(getPrimaryPureRun(), 'pure');
    const dynamic_runs = sortDynamicRunKeys(Object.keys(dynamicRuns)).map((k) =>
      slimRunForExport(dynamicRuns[k], 'dynamic')
    );
    return {
      output_folder: outputFolder || '',
      lang: getLang(),
      pure,
      dynamic_runs,
    };
  }

  function comparisonMetricsRows() {
    const items = listAllComparableRuns();
    if (items.length < 2) return [];
    const defs = [
      { label: t('sir.cmpPeak'), key: 'peak_day' },
      { label: t('sir.cmpPeakI'), key: 'peak_infected' },
      { label: t('sir.cmpFinal'), key: 'final_day' },
      { label: t('sir.cmpTotalInfected'), key: 'total_infected' },
    ];
    const header = [t('sir.cmpMetric')].concat(items.map((it) => formatComparisonColumnLabel(it)));
    const rows = [header];
    for (const def of defs) {
      const row = [def.label];
      for (const it of items) {
        const v = it.run[def.key];
        row.push(v != null ? String(v) : '—');
      }
      rows.push(row);
    }
    return rows;
  }

  function downloadPdfBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  function exportSirPdfInBrowser(outputFolder) {
    const jsPDF = window.jspdf && window.jspdf.jsPDF;
    if (!jsPDF) throw new Error('Thiếu thư viện jsPDF');
    const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a4' });
    const pageW = doc.internal.pageSize.getWidth();
    const pageH = doc.internal.pageSize.getHeight();
    const lang = getLang();

    const addPageHeader = (title) => {
      doc.setFontSize(16);
      doc.text(title, 40, 36);
      doc.setFontSize(10);
      if (outputFolder) {
        doc.text(`${lang === 'en' ? 'Folder' : 'Thư mục'}: ${outputFolder}`, 40, 54);
      }
    };

    addPageHeader(lang === 'en' ? 'Full SIR report (browser)' : 'Báo cáo SIR đầy đủ (trình duyệt)');
    let y = 72;
    doc.setFontSize(11);
    const keys = sortDynamicRunKeys(Object.keys(dynamicRuns));
    const lines = [
      lang === 'en' ? 'Simulations included:' : 'Các mô phỏng trong báo cáo:',
      ...sortPureRunModes(Object.keys(pureRuns)).map(
        (m) => `• Pure (${misinfoModeShortLabel(m)})`
      ),
      ...keys.map((k) => {
        const run = dynamicRuns[k];
        const p = parseDynamicRunKey(k);
        const src = misinfoModeShortLabel(run.misinfo_source_mode || p.misinfo_source_mode);
        const s = run.strategy || p.strategy;
        const d = run.intervention_day != null ? run.intervention_day : p.intervention_day;
        const tk = run.top_k != null ? run.top_k : p.top_k;
        return `• ${src} · ${s}, day ${d}, k=${tk}`;
      }),
    ].filter(Boolean);
    for (const line of lines) {
      if (y > pageH - 40) {
        doc.addPage();
        y = 40;
      }
      doc.text(line, 40, y);
      y += 14;
    }

    const addChartPage = (chart, caption) => {
      if (!chart) return;
      let img;
      try {
        img = chart.toBase64Image('image/jpeg', 0.95);
        if (!img || img.length < 200 || !/^data:image\/jpe?g;base64,/.test(img)) {
          return;
        }
      } catch (e) {
        console.warn('chart image export failed', e);
        return;
      }
      doc.addPage();
      addPageHeader(caption);
      const imgW = pageW - 80;
      const imgH = pageH - 100;
      doc.addImage(img, 'JPEG', 40, 64, imgW, imgH);
    };

    if (simLineChart && getPrimaryPureRun()) {
      addChartPage(
        simLineChart,
        lang === 'en' ? 'Pure SIR (active view)' : 'SIR thuần (đang xem)'
      );
    }
    if (simCompareChart && canShowComparison()) {
      addChartPage(
        simCompareChart,
        lang === 'en' ? 'Compare I — all runs' : 'So sánh I — tất cả kịch bản'
      );
    } else if (simCompareChart) {
      addChartPage(simCompareChart, lang === 'en' ? 'Comparison chart' : 'Đồ thị so sánh');
    }

    doc.addPage();
    addPageHeader(lang === 'en' ? 'Metrics table' : 'Bảng so sánh chỉ số');
    y = 80;
    doc.setFontSize(8);
    const rows = comparisonMetricsRows();
    for (const row of rows) {
      if (y > pageH - 36) {
        doc.addPage();
        y = 40;
        doc.setFontSize(8);
      }
      doc.text(row.join('  |  '), 36, y, { maxWidth: pageW - 72 });
      y += 12;
    }

    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    const fname =
      lang === 'en' ? `sir_full_report_${stamp}.pdf` : `sir_bao_cao_day_du_${stamp}.pdf`;
    doc.save(fname);
  }

  function refreshChartsBeforePdfExport() {
    const { model, data } = getActiveSirRunData();
    if (data?.history?.length) {
      drawSirSimChart(data.history, sirChartTitleForModel(model));
    }
    if (canShowComparison()) {
      drawSirComparisonChart();
    }
  }

  async function fetchSirPdfBlob(outputFolder) {
    const payload = {
      action: 'export_pdf',
      ...collectSirExportPayload(outputFolder),
    };
    const attempts = [
      () =>
        fetch('/api/simulate-sir', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }),
      () =>
        fetch('/api/sir-export-pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(collectSirExportPayload(outputFolder)),
        }),
      () =>
        fetch('/api/sir_export_pdf', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(collectSirExportPayload(outputFolder)),
        }),
    ];
    let lastStatus = 0;
    for (const run of attempts) {
      const response = await run();
      lastStatus = response.status;
      if (response.ok) {
        const ct = (response.headers.get('Content-Type') || '').toLowerCase();
        if (ct.includes('application/pdf')) {
          return response;
        }
      }
      if (response.status !== 404 && response.status !== 405) {
        break;
      }
    }
    const err = new Error(`HTTP ${lastStatus}`);
    err.status = lastStatus;
    throw err;
  }

  async function exportSirPdf() {
    const btn = document.getElementById('btnReport');
    if (btn) btn.disabled = true;
    showSimStatus(t('sir.exportPdfRunning'), 'loading');
    try {
      let outputFolder = '';
      try {
        const summary = await fetchJson('/api/summary');
        outputFolder = summary.output_folder || '';
      } catch {
        /* optional */
      }

      await ensureAllRunsLoadedForExport(outputFolder);
      if (!listAllComparableRuns().length) {
        showSimStatus(t('sir.exportPdfNeedPure'), 'error');
        return;
      }

      if (canShowComparison() && getActiveSirResultTab() !== 'comparison') {
        await refreshComparisonTab();
      }
      refreshChartsBeforePdfExport();

      try {
        const response = await fetchSirPdfBlob(outputFolder);
        const blob = await response.blob();
        const disp = response.headers.get('Content-Disposition') || '';
        let filename = 'sir_bao_cao.pdf';
        const m = /filename\*?=(?:UTF-8'')?["']?([^"';]+)/i.exec(disp);
        if (m) filename = decodeURIComponent(m[1].trim());
        downloadPdfBlob(blob, filename);
        showSimStatus(t('sir.exportPdfDone'), 'success');
      } catch (apiErr) {
        exportSirPdfInBrowser(outputFolder);
        showSimStatus(t('sir.exportPdfDone'), 'success');
      }
    } catch (error) {
      showSimStatus(`${t('sir.exportPdfErr')}: ${error.message}`, 'error');
    } finally {
      updateReportButton();
    }
  }

  function canShowComparison() {
    return listAllComparableRuns().length >= 2;
  }

  async function ensureRunsLoadedForComparison() {
    if (canShowComparison()) return true;
    let folder;
    try {
      const s = await fetchJson('/api/summary');
      if (!s?.ready || !s.output_folder) return false;
      folder = s.output_folder;
    } catch {
      return false;
    }
    try {
      const list = await fetchJson(
        `/api/sir-saved-runs?output_dir=${encodeURIComponent(folder)}`
      );
      for (const item of list.pure_runs || []) {
        const mode = item.misinfo_source_mode || 'random';
        if (pureRuns[mode]) continue;
        const d = await fetchSirResultsFromApi(folder, 'pure', null, null, null, mode);
        pureRuns[mode] = sirApiDataToRunModel(d, 'pure');
      }
      for (const item of list.dynamic_runs || []) {
        const rk = dynamicRunKeyFromRun(item);
        if (dynamicRuns[rk]) continue;
        const d = await fetchSirResultsFromApi(
          folder,
          'dynamic',
          item.strategy,
          item.intervention_day,
          item.top_k,
          item.misinfo_source_mode || 'random'
        );
        dynamicRuns[rk] = sirApiDataToRunModel(d, 'dynamic');
      }
      return canShowComparison();
    } catch {
      return false;
    }
  }

  function updateComparisonEmptyState() {
    const empty = document.getElementById('sirComparisonEmpty');
    const content = document.getElementById('sirComparisonContent');
    const cmpBtn = document.querySelector('.result-tab-btn[data-sir-tab="comparison"]');
    const can = canShowComparison();

    if (empty) {
      empty.hidden = true;
      empty.textContent = '';
    }
    if (content) content.hidden = !can;
    if (cmpBtn) {
      cmpBtn.classList.toggle('sir-tab-disabled', !can);
      cmpBtn.title = '';
    }
  }

  function formatDynamicRunLabel(run, key) {
    const parsed = parseDynamicRunKey(key);
    const src = misinfoModeShortLabel(run?.misinfo_source_mode || parsed.misinfo_source_mode);
    const strat = run?.strategy || parsed.strategy || 'betweenness';
    const day = run?.intervention_day != null ? run.intervention_day : parsed.intervention_day;
    const topK = run?.top_k != null ? run.top_k : parsed.top_k != null ? parsed.top_k : '—';
    return `${src} · ${t('sir.runDynFmt', {
      strategy: strategyShortName(strat),
      day,
      k: topK,
    })}`;
  }

  function formatPureRunLabel(mode) {
    return `${t('sir.runPure')} (${misinfoModeShortLabel(mode)})`;
  }

  function listSirRunOptions() {
    const opts = [];
    sortPureRunModes(Object.keys(pureRuns)).forEach((mode) => {
      opts.push({ key: pureRunKey(mode), type: 'pure', run: pureRuns[mode], mode });
    });
    for (const k of sortDynamicRunKeys(Object.keys(dynamicRuns))) {
      opts.push({ key: k, type: 'dynamic', run: dynamicRuns[k] });
    }
    return opts;
  }

  function getActiveSirRunData() {
    if (isPureRunKey(activeSirRunKey)) {
      return { model: 'pure', data: getRunByKey(activeSirRunKey) };
    }
    return { model: 'dynamic', data: dynamicRuns[activeSirRunKey] };
  }

  function syncSirRunPicker(preferredKey) {
    const picker = document.getElementById('sirRunPicker');
    const sel = document.getElementById('sirRunSelect');
    const countBadge = document.getElementById('sirRunPickerCount');
    if (!picker || !sel) return;
    const opts = listSirRunOptions();
    picker.hidden = opts.length < 2;
    if (opts.length < 2) return;

    sel.replaceChildren();
    for (const o of opts) {
      const opt = document.createElement('option');
      opt.value = o.key;
      opt.textContent =
        o.type === 'pure' ? formatPureRunLabel(o.mode) : formatDynamicRunLabel(o.run, o.key);
      sel.appendChild(opt);
    }
    const keys = opts.map((o) => o.key);
    let next = keys[keys.length - 1];
    if (preferredKey && keys.includes(preferredKey)) next = preferredKey;
    else if (keys.includes(activeSirRunKey)) next = activeSirRunKey;
    sel.value = next;
    const total = opts.length;
    if (countBadge) {
      countBadge.textContent = total >= 2 ? t('sir.runCount', { n: total }) : '';
      countBadge.hidden = total < 2;
    }
    resizeSirCharts();
  }

  function setActiveSirRun(key) {
    if (key === 'pure') key = pureRunKey(misinfoSourceMode());
    if (isPureRunKey(key)) {
      const run = getRunByKey(key);
      if (!run) return;
      activeSirRunKey = key;
      currentSimModel = 'pure';
      pureResults = run;
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
    updateStatsSim(data, simModelLabel(model));
    updateResultsStrip(data);
    updateComparisonEmptyState();
    if (canShowComparison()) {
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
    if (!isPureRunKey(activeSirRunKey) && dynamicRuns[activeSirRunKey]) {
      return `${base} — ${formatDynamicRunLabel(dynamicRuns[activeSirRunKey], activeSirRunKey)}`;
    }
    if (isPureRunKey(activeSirRunKey)) {
      return `${base} — ${formatPureRunLabel(parsePureRunKey(activeSirRunKey))}`;
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
    if (tab === 'comparison' && !canShowComparison()) {
      return;
    }
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
      refreshComparisonTab();
    } else if (tab === 'stats' && data) {
      updateStatsSim(data, simModelLabel(model));
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

  function totalInfectedFromData(data) {
    if (data.total_infected != null) return data.total_infected;
    if (!data.history || !data.history.length) return null;
    const hist = data.history;
    const finalDay = data.final_day != null ? data.final_day : hist[hist.length - 1].day;
    let row = hist.find((h) => h.day === finalDay);
    if (!row) row = hist[hist.length - 1];
    if (row.cum_infected != null) {
      const sub = hist.filter((h) => h.day <= finalDay);
      return Math.max(...sub.map((h) => Number(h.cum_infected) || 0));
    }
    return row.R;
  }

  function updateResultsStrip(data) {
    const peakDay = document.getElementById('stripPeakDay');
    const peakI = document.getElementById('stripPeakInfected');
    const finalD = document.getElementById('stripFinalDay');
    const totalInf = document.getElementById('stripTotalInfected');
    const total = totalInfectedFromData(data);
    if (peakDay) peakDay.textContent = data.peak_day;
    if (peakI) peakI.textContent = data.peak_infected;
    if (finalD) finalD.textContent = data.final_day;
    if (totalInf) totalInf.textContent = total != null ? total : '—';
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
        body: JSON.stringify(
          await simulationRequestBody({
            model: 'pure',
            transmission_rate: transmission,
            recovery_rate: recovery,
            days,
            seed,
            ...misinfoPayloadExtra(),
          })
        ),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Lỗi mô phỏng');
      const mode = data.misinfo_source_mode || misinfoSourceMode();
      pureRuns[mode] = data;
      pureResults = data;
      updateComparisonEmptyState();
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      displayPureResults(data);
      updateReportButton();
      const nodeHint =
        data.nodes != null
          ? getLang() === 'en'
            ? ` Dataset: ${data.nodes} nodes.`
            : ` Mạng: ${data.nodes} nút.`
          : '';
      showSimStatus(t('msgs.donePure') + nodeHint, 'success');
      persistSirSession();
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
        body: JSON.stringify(
          await simulationRequestBody({
            model: 'dynamic',
            transmission_rate: transmission,
            recovery_rate: recovery,
            days,
            top_k: topK,
            seed,
            strategy,
            intervention_day: interventionDay,
            ...misinfoPayloadExtra(),
          })
        ),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Lỗi mô phỏng');
      const rk = dynamicRunKeyFromRun({
        misinfo_source_mode: data.misinfo_source_mode || misinfoSourceMode(),
        strategy: data.strategy || strategy,
        intervention_day: data.intervention_day != null ? data.intervention_day : interventionDay,
        top_k: data.top_k != null ? data.top_k : topK,
      });
      dynamicRuns[rk] = data;
      dynamicResults = data;
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      displayDynamicResults(data, rk);
      updateComparisonEmptyState();
      updateReportButton();
      if (canShowComparison() && getActiveSirResultTab() === 'comparison') {
        drawSirComparisonChart();
        updateComparisonTableSim();
      }
      const nodeHint =
        data.nodes != null
          ? getLang() === 'en'
            ? ` Dataset: ${data.nodes} nodes.`
            : ` Mạng: ${data.nodes} nút.`
          : '';
      showSimStatus(t('msgs.doneDyn') + nodeHint, 'success');
      persistSirSession();
    } catch (error) {
      showSimStatus('Lỗi: ' + error.message, 'error');
    } finally {
      btn.disabled = false;
    }
  }

  function updateStatsSim(data, modelLabel) {
    const total = totalInfectedFromData(data);
    const recovered =
      data.history && data.history.length ? data.history[data.history.length - 1].R : 0;
    document.getElementById('statPeakDaySim').textContent = data.peak_day;
    document.getElementById('statPeakInfectedSim').textContent = data.peak_infected;
    document.getElementById('statFinalDaySim').textContent = data.final_day;
    const elTotal = document.getElementById('statTotalInfectedSim');
    if (elTotal) elTotal.textContent = total != null ? total : '—';
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
    const stratLabel = strategyShortName(strat);
    const iday = data.intervention_day != null ? data.intervention_day : 1;
    const misEl = document.getElementById('detailMisinfoSourceSim');
    if (misEl) misEl.textContent = formatMisinfoSourceLabel(data);
    document.getElementById('detailRuntimeSim').textContent =
      data.top_k != null
        ? t('sir.detailRuntimeFmt', { k: data.top_k, strategy: stratLabel, day: iday })
        : '—';
  }

  function displayPureResults(data) {
    const mode = data.misinfo_source_mode || misinfoSourceMode();
    pureRuns[mode] = data;
    pureResults = data;
    const pk = pureRunKey(mode);
    syncSirRunPicker(pk);
    setActiveSirRun(pk);
  }

  function displayDynamicResults(data, runKey) {
    const rk = runKey || dynamicRunKeyFromRun(data);
    dynamicRuns[rk] = data;
    dynamicResults = data;
    syncSirRunPicker(rk);
    setActiveSirRun(rk);
  }

  function markSirChartHasData() {
    document.getElementById('sirChartWrap')?.classList.add('sir-chart-has-data');
    document.getElementById('sirCmpChartWrap')?.classList.add('sir-chart-has-data');
  }

  const SIR_CHART_FONT = 12;
  const SIR_CMP_CHART_FONT = 14;

  function sirChartTextOpts(fontSize) {
    const fs = fontSize || SIR_CHART_FONT;
    return {
      plugins: {
        legend: {
          position: 'top',
          labels: { font: { size: fs }, boxWidth: 14, padding: 14 },
        },
        title: { font: { size: fs + 1 } },
        tooltip: { titleFont: { size: fs }, bodyFont: { size: fs } },
      },
      scales: {
        x: {
          ticks: { font: { size: fs - 1 }, maxRotation: 0 },
          title: { font: { size: fs } },
        },
        y: {
          ticks: { font: { size: fs - 1 } },
          title: { font: { size: fs } },
        },
      },
    };
  }

  function sirCmpChartOpts() {
    const base = sirChartTextOpts(SIR_CMP_CHART_FONT);
    return {
      ...base,
      plugins: {
        ...base.plugins,
        legend: {
          ...base.plugins.legend,
          labels: { ...base.plugins.legend.labels, boxWidth: 16, padding: 16 },
        },
      },
    };
  }

  function drawSirSimChart(history, titleText) {
    const canvas = document.getElementById('sirSimChart');
    if (!canvas || typeof Chart === 'undefined' || !history || !history.length) return;
    markSirChartHasData();
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
            label: t('sir.datasetS'),
            data: S,
            borderColor: '#4285f4',
            backgroundColor: 'rgba(66, 133, 244, 0.1)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
          },
          {
            label: t('sir.datasetI'),
            data: I,
            borderColor: '#ea4335',
            backgroundColor: 'rgba(234, 67, 53, 0.1)',
            tension: 0.35,
            fill: true,
            borderWidth: 2,
          },
          {
            label: t('sir.datasetR'),
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
          ...sirChartTextOpts().plugins,
          title: { display: true, text: titleText, font: { size: SIR_CHART_FONT + 1 } },
          tooltip: {
            ...sirChartTextOpts().plugins.tooltip,
            callbacks: {
              label(ctx) {
                return `${ctx.dataset.label}: ${ctx.parsed.y}`;
              },
            },
          },
        },
        scales: {
          x: {
            ...sirChartTextOpts().scales.x,
            title: { display: true, text: t('sir.chartAxisX'), font: { size: SIR_CHART_FONT } },
          },
          y: {
            ...sirChartTextOpts().scales.y,
            beginAtZero: true,
            title: { display: true, text: t('sir.chartAxisY'), font: { size: SIR_CHART_FONT } },
          },
        },
      },
    });
    resizeSirCharts();
  }

  async function refreshComparisonTab() {
    updateComparisonEmptyState();
    if (!canShowComparison()) {
      await ensureRunsLoadedForComparison();
      updateComparisonEmptyState();
    }
    if (!canShowComparison()) {
      if (simCompareChart) {
        simCompareChart.destroy();
        simCompareChart = null;
      }
      document.getElementById('sirCmpChartWrap')?.classList.remove('sir-chart-has-data');
      return;
    }
    drawSirComparisonChart();
    updateComparisonTableSim();
  }

  function drawSirComparisonChart() {
    const canvas = document.getElementById('comparisonSimChart');
    if (!canvas || typeof Chart === 'undefined') return;
    const ctx = canvas.getContext('2d');
    if (simCompareChart) simCompareChart.destroy();
    const items = listAllComparableRuns();
    if (items.length < 2) return;
    markSirChartHasData();

    let maxDay = 0;
    for (const it of items) {
      for (const h of it.run.history || []) maxDay = Math.max(maxDay, h.day);
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

    const palette = [
      ['#ea4335', 'rgba(234, 67, 53, 0.08)'],
      ['#2563eb', 'rgba(37, 99, 235, 0.08)'],
      ['#34a853', 'rgba(52, 168, 83, 0.08)'],
      ['#9333ea', 'rgba(147, 51, 234, 0.08)'],
      ['#f59e0b', 'rgba(245, 158, 11, 0.08)'],
      ['#ec4899', 'rgba(236, 72, 153, 0.08)'],
      ['#0ea5e9', 'rgba(14, 165, 233, 0.08)'],
    ];

    const datasets = items.map((it, idx) => {
      const [bc, fill] = palette[idx % palette.length];
      return {
        label: formatComparisonSeriesLabel(it),
        data: alignI(it.run.history),
        borderColor: bc,
        backgroundColor: fill,
        tension: 0.35,
        fill: true,
        borderWidth: 2.5,
      };
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
          ...sirCmpChartOpts().plugins,
          title: {
            display: true,
            text: t('sir.chartCmp') || 'So sánh đường cong I',
            font: { size: SIR_CMP_CHART_FONT + 2 },
          },
        },
        scales: {
          x: {
            ...sirCmpChartOpts().scales.x,
            title: {
              display: true,
              text: t('sir.chartAxisX'),
              font: { size: SIR_CMP_CHART_FONT },
            },
          },
          y: {
            ...sirCmpChartOpts().scales.y,
            beginAtZero: true,
            title: {
              display: true,
              text: t('sir.chartCmpAxisY'),
              font: { size: SIR_CMP_CHART_FONT },
            },
          },
        },
      },
    });
    resizeSirCharts();
  }

  function updateComparisonTableSim() {
    const items = listAllComparableRuns();
    const headRow = document.getElementById('comparisonSimTableHeadRow');
    const bodyEl = document.getElementById('comparisonSimTableBody');
    if (!headRow || !bodyEl || items.length < 2) return;

    headRow.replaceChildren();
    const thMetric = document.createElement('th');
    thMetric.setAttribute('data-i18n', 'sir.cmpMetric');
    thMetric.textContent = t('sir.cmpMetric');
    headRow.appendChild(thMetric);
    for (const it of items) {
      const th = document.createElement('th');
      th.textContent = formatComparisonColumnLabel(it);
      headRow.appendChild(th);
    }

    bodyEl.replaceChildren();
    const rowsDef = [
      { tKey: 'sir.cmpPeak', key: 'peak_day' },
      { tKey: 'sir.cmpPeakI', key: 'peak_infected' },
      { tKey: 'sir.cmpFinal', key: 'final_day' },
      { tKey: 'sir.cmpTotalInfected', key: 'total_infected' },
    ];
    for (const def of rowsDef) {
      const tr = document.createElement('tr');
      const td0 = document.createElement('td');
      td0.setAttribute('data-i18n', def.tKey);
      td0.textContent = t(def.tKey);
      tr.appendChild(td0);
      for (const it of items) {
        const td = document.createElement('td');
        td.className = 'tabular-nums';
        const v = it.run[def.key];
        td.textContent = v != null ? String(v) : '—';
        tr.appendChild(td);
      }
      bodyEl.appendChild(tr);
    }
  }

  async function fetchSirResultsFromApi(
    datasetFolder,
    model,
    strategy,
    interventionDay,
    topK,
    misinfoMode
  ) {
    const misinfo = misinfoMode || misinfoSourceMode();
    let url = `/api/sir-results?output_dir=${encodeURIComponent(datasetFolder)}&model=${encodeURIComponent(model)}&misinfo_source_mode=${encodeURIComponent(misinfo)}`;
    if (model === 'dynamic') {
      url += `&strategy=${encodeURIComponent(strategy)}&intervention_day=${encodeURIComponent(String(interventionDay))}`;
      if (topK != null && topK !== '') {
        url += `&top_k=${encodeURIComponent(String(topK))}`;
      }
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
      total_infected: st.total_infected,
      never_infected: st.never_infected,
      history: d.history,
      output_directory: d.output_directory || null,
      strategy: d.strategy,
      intervention_day: d.intervention_day != null ? d.intervention_day : 1,
      top_k: d.top_k,
      misinfo_source_mode: d.misinfo_source_mode || 'random',
      misinfo_source_node_ids: d.misinfo_source_node_ids,
      misinfo_source_nodes: d.misinfo_source_nodes,
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
    const pureList =
      list.pure_runs || (list.pure_available ? [{ misinfo_source_mode: 'random' }] : []);
    for (const row of pureList) {
      const mode = row.misinfo_source_mode || 'random';
      try {
        const d = await fetchSirResultsFromApi(s.output_folder, 'pure', null, null, null, mode);
        const run = sirApiDataToRunModel(d, 'pure');
        pureRuns[mode] = run;
        restored += 1;
      } catch (e) {
        console.warn('restore pure', mode, e);
      }
    }
    for (const row of list.dynamic_runs || []) {
      try {
        const d = await fetchSirResultsFromApi(
          s.output_folder,
          'dynamic',
          row.strategy,
          row.intervention_day,
          row.top_k,
          row.misinfo_source_mode || 'random'
        );
        const run = sirApiDataToRunModel(d, 'dynamic');
        if (run.top_k == null && row.top_k != null) run.top_k = row.top_k;
        dynamicRuns[dynamicRunKeyFromRun(run)] = run;
        restored += 1;
      } catch (e) {
        console.warn('restore dynamic', row, e);
      }
    }
    if (!restored) return;
    showSimStatus(t('msgs.restoredSir', { n: restored }), 'success');
    updateComparisonEmptyState();
    const all = listSirRunOptions();
    if (all.length) {
      const lastKey = all[all.length - 1].key;
      switchSirResultTab('chart', {
        currentTarget: document.querySelector('.sim-results-panel .result-tab-btn[data-sir-tab="chart"]'),
      });
      syncSirRunPicker(lastKey);
      setActiveSirRun(lastKey);
    }
    const strip = document.getElementById('sirResultsStrip');
    if (strip) strip.hidden = false;
    updateReportButton();
    persistSirSession(summary);
  }

  async function tryLoadFromUrl() {
    const p = new URLSearchParams(window.location.search);
    const out = p.get('output_dir');
    const model = p.get('model') || 'pure';
    const strategy = p.get('strategy');
    if (!out) return;
    try {
      const misinfoQ = p.get('misinfo_source_mode') || 'random';
      let url = `/api/sir-results?output_dir=${encodeURIComponent(out)}&model=${encodeURIComponent(model)}&misinfo_source_mode=${encodeURIComponent(misinfoQ)}`;
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
        top_k: p.get('top_k') ? parseInt(p.get('top_k'), 10) : null,
        misinfo_source_mode: misinfoQ,
      };
      if (model === 'dynamic') {
        dynamicResults = pseudo;
        pureResults = null;
        switchModel('dynamic');
        const rk = dynamicRunKeyFromRun(pseudo);
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
    const out = getActiveOutputDir();
    window.MauShell?.invalidatePageCaches?.(out);
    pureResults = null;
    dynamicResults = null;
    Object.keys(pureRuns).forEach((k) => delete pureRuns[k]);
    activeSirRunKey = pureRunKey('random');
    clearDynamicRuns();
    updateComparisonEmptyState();
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
    const summary = await loadSidebarSummary(true);
    await tryLoadFromUrl();
    if (!new URLSearchParams(window.location.search).get('output_dir')) {
      await bootstrapSirFromCacheOrApi(summary);
    }
  }

  window.onSharedDataReady = reloadAfterDataChange;

  async function init() {
    window.MauShell?.init({ page: 'simulation', onDataReady: reloadAfterDataChange });
    setupSirRangeInputs();
    const resultsPanel = document.querySelector('.sim-results-panel');
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
    document.getElementById('btnReport')?.addEventListener('click', exportSirPdf);
    window.addEventListener('app:langchange', () => updateReportButton());
    document.getElementById('sirRunSelect')?.addEventListener('change', (e) => {
      setActiveSirRun(e.target.value);
    });
    window.addEventListener('app:langchange', () => {
      window.I18N?.applyI18n?.();
      syncSirRunPicker(activeSirRunKey);
      setActiveSirRun(activeSirRunKey);
      updateComparisonEmptyState();
      if (canShowComparison()) {
        updateComparisonTableSim();
        if (getActiveSirResultTab() === 'comparison') drawSirComparisonChart();
      }
    });
    const summary = await loadSidebarSummary();
    await tryLoadFromUrl();
    if (!new URLSearchParams(window.location.search).get('output_dir')) {
      await bootstrapSirFromCacheOrApi(summary);
    }
    updateComparisonEmptyState();
    updateReportButton();
  }

  window.addEventListener('DOMContentLoaded', () => {
    init().catch((err) => console.warn(err));
  });
})();
