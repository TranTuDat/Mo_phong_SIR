// Theme Management
function initTheme() {
  const savedTheme = localStorage.getItem('theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeToggle(savedTheme);
}

function toggleTheme() {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  localStorage.setItem('theme', newTheme);
  updateThemeToggle(newTheme);
  if (graphData) drawGraph();
}

function updateThemeToggle(theme) {
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  }
}

// Language (i18n)
const I18N = {
  vi: {
    'dashboard.docTitle': 'InfoOps Analyzer — Tổng quan',
    'brand.subtitle': 'Phân tích mạng & lan truyền',
    'nav.overview': 'Tổng quan',
    'nav.sirPageLong': 'Mô phỏng SIR',
    'nav.recsPage': 'Đề xuất can thiệp',
    'dashboard.modalTitle': 'Tạo dữ liệu mạng',
    'dashboard.lblNumUsers': 'Số người dùng',
    'dashboard.hintUsers': '10–2000',
    'dashboard.lblProb': 'Xác suất có cạnh',
    'dashboard.hintProb': '0,001–0,1 (càng cao càng dày)',
    'dashboard.lblSeed': 'Seed',
    'dashboard.hintSeed': 'Tái lập kết quả',
    'dashboard.lblSource': 'Nguồn',
    'dashboard.srcGen': 'Sinh ngẫu nhiên',
    'dashboard.srcUp': 'Tải CSV',
    'dashboard.lblFile': 'File CSV',
    'dashboard.hintCsv': 'Cột: id, name, followers, posts, shares, comments, risk',
    'dashboard.cancel': 'Hủy',
    'dashboard.confirmGen': 'Tạo dữ liệu',
    'dashboard.title': 'Tổng quan',
    'dashboard.simLink': 'Trang mô phỏng SIR',
    'dashboard.generate': 'Tạo dữ liệu',
    'dashboard.sirPure': 'SIR thuần',
    'dashboard.sirDyn': 'SIR động',
    'dashboard.cleanup': 'Dọn output',
    'dashboard.metricUsers': 'Tổng tài khoản',
    'dashboard.metricEdges': 'Tổng quan hệ',
    'dashboard.metricEngagement': 'Tương tác',
    'dashboard.metricFootnote': 'Ước lượng từ mạng',
    'dashboard.graphTitle': 'Bản đồ mạng',
    'dashboard.graphSub': 'Bản đồ cộng đồng — màu theo cụm, hub trung tâm, nhấp nút để xem chi tiết.',
    'dashboard.graphSubSna':
      'Đồ thị đại diện: {shown}/{total} nút quan trọng · {edges} cạnh.',
    'dashboard.graphSubGalaxy':
      'Galaxy view · {shown}/{total} nút · {edges} cạnh — zoom/pan, nhấp để focus ego-network.',
    'dashboard.graphSubSummary': 'Đồ thị tóm lược: {shown}/{total} nút, {edges} cạnh chọn lọc.',
    'dashboard.clusterLegendTitle': 'Màu cụm',
    'dashboard.edgeIntra': 'Nội cụm',
    'dashboard.edgeInter': 'Liên cụm',
    'dashboard.labels': 'Nhãn',
    'dashboard.labelsSmart': 'Quan trọng + rê chuột',
    'dashboard.labelsAll': 'Tất cả',
    'dashboard.labelsHover': 'Chỉ khi rê chuột',
    'dashboard.refresh': 'Làm mới',
    'dashboard.graphHint': 'Nhấp nút để xem chi tiết.',
    'dashboard.sirPanel': 'Kết quả SIR (nhanh)',
    'dashboard.sirNone': 'Chưa chạy',
    'brand.tagline': 'Công cụ phân tích mạng xã hội',
    'nav.dataImport': 'Nhập dữ liệu',
    'nav.analysis': 'Bản đồ mạng',
    'nav.keyNodes': 'Nút quan trọng',
    'nav.clusters': 'Cụm cộng đồng',
    'nav.risks': 'Điểm nguy cơ',
    'nav.reports': 'Báo cáo',
    'dashboard.institution': 'Khóa luận · Mô phỏng mạng xã hội',
    'dashboard.guide': 'Hướng dẫn',
    'dashboard.report': 'Báo cáo',
    'dashboard.export': 'Xuất dữ liệu',
    'dashboard.metricTrendHint': 'Chỉ số minh họa theo mật độ mạng',
    'dashboard.metricHighRisk': 'Tài khoản nguy cơ cao',
    'dashboard.metricRiskFoot': 'Theo mức độ rủi ro (High)',
    'dashboard.graphMapTitle': 'Bản đồ mạng tương tác',
    'dashboard.riskLegendTitle': 'Độ đậm (trong cụm)',
    'dashboard.metricsCaption':
      'Phần trăm xu hướng minh họa theo mật độ mạng. «Nguy cơ cao» = số tài khoản mức High.',
    'dashboard.topbarHint': 'Tạo / tải dữ liệu và mô phỏng SIR: dùng menu bên trái.',
    'dashboard.riskHigh': 'Cao',
    'dashboard.riskMed': 'Trung bình',
    'dashboard.riskLow': 'Thấp',
    'dashboard.riskUnknown': 'Chưa xác định',
    'dashboard.topNodes': 'Top 10 nút',
    'dashboard.riskWeightsTitle': 'Trọng số',
    'dashboard.weightBetw': 'Betweenness',
    'dashboard.weightDeg': 'Degree',
    'dashboard.weightEig': 'Eigenvector',
    'dashboard.riskWeightsReset': 'Mặc định',
    'dashboard.riskFormula':
      'Điểm = (w₁×Betweenness + w₂×Degree + w₃×Eigenvector) × 100',
    'dashboard.topAuto': 'Tự động',
    'dashboard.thRank': '#',
    'dashboard.thAccount': 'Tài khoản',
    'dashboard.thRole': 'Vai trò',
    'dashboard.thDegree': 'Degree',
    'dashboard.thBetw': 'Betweenness',
    'dashboard.thEigen': 'Eigenvector',
    'dashboard.thRisk': 'Điểm nguy cơ',
    'dashboard.profileTitle': 'Tài khoản chọn',
    'dashboard.profileFollowers': 'Người theo dõi',
    'dashboard.profilePosts': 'Bài viết',
    'dashboard.profileShareLbl': 'Share',
    'dashboard.profileCommentLbl': 'Comment',
    'dashboard.clustersDetected': 'Cụm cộng đồng',
    'dashboard.clusterUnit': 'cụm',
    'dashboard.clusterCountFmt': '{n}',
    'dashboard.recPanelTitle': 'Đề xuất can thiệp',
    'dashboard.recR1': 'Kiểm soát nguy cơ cao',
    'dashboard.recR2': 'Giám sát betweenness',
    'dashboard.recR3': 'Cảnh báo nhóm bất thường',
    'dashboard.recR4': 'Rà soát cụm lạ',
    'dashboard.recSeeAll': 'Chi tiết →',
    'dashboard.metricEngagement': 'Tương tác',
    'dashboard.metricHighRisk': 'Nguy cơ cao',
    'dashboard.systemStatusLabel': 'Trạng thái hệ thống',
    'dashboard.systemStatusReady': 'Sẵn sàng',
    'dashboard.systemStatusWaiting': 'Chờ dữ liệu',
    'dashboard.systemStatusReadyMsg': 'Dữ liệu đã sẵn sàng — có thể phân tích mạng',
    'dashboard.systemStatusWaitingMsg': 'Chưa có bộ dữ liệu output',
    'dashboard.systemStatusDetail':
      '{users} tài khoản · {edges} quan hệ · {high} nguy cơ cao · {shown}/{total} nút trên đồ thị',
    'dashboard.systemStatusWaitingDetail': 'Dùng «Nhập dữ liệu» ở menu trái để sinh hoặc tải CSV',
    'dashboard.statGraphNodes': 'Nút trên đồ thị',
    'dashboard.statClustersFmt': '{n} cụm cộng đồng',
    'dashboard.footerVer': 'Phiên bản',
    'dashboard.footerUpd': 'Cập nhật',
    'dashboard.lblModel': 'Mô hình',
    'dashboard.lblPeakDay': 'Ngày đỉnh',
    'dashboard.lblPeakI': 'Đỉnh nhiễm',
    'dashboard.lblFinal': 'Ngày kết thúc',
    'dashboard.lblOutput': 'Thư mục kết quả',
    'dashboard.riskBadge.High': 'Nguy cơ cao',
    'dashboard.riskBadge.Medium': 'Nguy cơ trung bình',
    'dashboard.riskBadge.Low': 'Nguy cơ thấp',
    'dashboard.riskBadge.Unknown': 'Chưa xác định',
    'toast.guide': 'Chọn nút trên đồ thị để xem chỉ số; dùng «Tạo dữ liệu» để sinh mạng mới.',
    'toast.export': 'Dữ liệu nằm trong thư mục output_* trên máy chủ (CSV).',
    'toast.report': 'Phần báo cáo tóm tắt nằm ở cuối trang và khối đề xuất can thiệp.',
    'toast.menuReports': 'Cuộn xuống chân trang để xem phiên bản và thời gian cập nhật.',
    toast_generated: 'Tạo dữ liệu thành công. Dashboard đã cập nhật.',
    toast_uploaded: 'Tải lên & xử lý dữ liệu thành công. Dashboard đã cập nhật.',
    toast_cleanup_done: 'Đã dọn output cũ.',
    toast_sim_done: 'Đã chạy mô phỏng SIR. Kết quả đã lưu.',
    ask_open_sir: 'Mô phỏng hoàn thành. Mở trang «Mô phỏng SIR» để xem biểu đồ và chỉnh tham số?',
  },
  en: {
    'dashboard.docTitle': 'InfoOps Analyzer — Overview',
    'brand.subtitle': 'Network analysis & diffusion',
    'nav.overview': 'Overview',
    'nav.sirPageLong': 'SIR simulation',
    'nav.recsPage': 'Intervention suggestions',
    'dashboard.modalTitle': 'Generate network data',
    'dashboard.lblNumUsers': 'Users',
    'dashboard.hintUsers': '10–2000',
    'dashboard.lblProb': 'Edge probability',
    'dashboard.hintProb': '0.001–0.1 (higher = denser)',
    'dashboard.lblSeed': 'Seed',
    'dashboard.hintSeed': 'Reproducible results',
    'dashboard.lblSource': 'Source',
    'dashboard.srcGen': 'Generate',
    'dashboard.srcUp': 'Upload CSV',
    'dashboard.lblFile': 'CSV file',
    'dashboard.hintCsv': 'Columns: id, name, followers, posts, shares, comments, risk',
    'dashboard.cancel': 'Cancel',
    'dashboard.confirmGen': 'Generate',
    'dashboard.title': 'Overview',
    'dashboard.simLink': 'SIR simulation',
    'dashboard.generate': 'Generate data',
    'dashboard.sirPure': 'Pure SIR',
    'dashboard.sirDyn': 'Dynamic SIR',
    'dashboard.cleanup': 'Clean outputs',
    'dashboard.metricUsers': 'Accounts',
    'dashboard.metricEdges': 'Relationships',
    'dashboard.metricEngagement': 'Engagement',
    'dashboard.metricFootnote': 'Estimated from graph',
    'dashboard.graphTitle': 'Network map',
    'dashboard.graphSub': 'Community map — color by cluster, hub-centric. Click a node for details.',
    'dashboard.graphSubSna':
      '{shown}/{total} nodes · {edges} edges — network analysis map (force-directed).',
    'dashboard.graphSubGalaxy':
      'Galaxy view · {shown}/{total} nodes · {edges} edges — zoom/pan, click to focus ego-network.',
    'dashboard.graphSubSummary': 'Summary view: {shown}/{total} nodes, {edges} selected edges.',
    'dashboard.clusterLegendTitle': 'Cluster color',
    'dashboard.edgeIntra': 'Within cluster',
    'dashboard.edgeInter': 'Between clusters',
    'dashboard.labels': 'Labels',
    'dashboard.labelsSmart': 'Key nodes + hover',
    'dashboard.labelsAll': 'All',
    'dashboard.labelsHover': 'Hover only',
    'dashboard.refresh': 'Refresh',
    'dashboard.graphHint': 'Click a node to see details.',
    'dashboard.sirPanel': 'SIR results (quick)',
    'dashboard.sirNone': 'Not run',
    'brand.tagline': 'Social network analysis toolkit',
    'nav.dataImport': 'Data input',
    'nav.analysis': 'Network map',
    'nav.keyNodes': 'Important nodes',
    'nav.clusters': 'Communities',
    'nav.risks': 'Risk hotspots',
    'nav.reports': 'Reports',
    'dashboard.institution': 'Thesis · Social network simulation',
    'dashboard.guide': 'Guide',
    'dashboard.report': 'Report',
    'dashboard.export': 'Export',
    'dashboard.metricTrendHint': 'Illustrative index from network density',
    'dashboard.metricHighRisk': 'High-risk accounts',
    'dashboard.metricRiskFoot': 'By risk level (High)',
    'dashboard.graphMapTitle': 'Interaction network map',
    'dashboard.riskLegendTitle': 'Shade (in cluster)',
    'dashboard.riskHigh': 'High',
    'dashboard.riskMed': 'Medium',
    'dashboard.riskLow': 'Low',
    'dashboard.riskUnknown': 'Unknown',
    'dashboard.metricsCaption':
      'Trend percentages are illustrative (density). High risk = number of High-labeled accounts.',
    'dashboard.topbarHint': 'Generate data and SIR runs: use the left menu.',
    'dashboard.topNodes': 'Top 10 nodes',
    'dashboard.riskWeightsTitle': 'Weights',
    'dashboard.weightBetw': 'Betweenness',
    'dashboard.weightDeg': 'Degree',
    'dashboard.weightEig': 'Eigenvector',
    'dashboard.riskWeightsReset': 'Reset',
    'dashboard.riskFormula':
      'Score = (w₁×Betweenness + w₂×Degree + w₃×Eigenvector) × 100',
    'dashboard.topAuto': 'Auto',
    'dashboard.thRank': '#',
    'dashboard.thAccount': 'Account',
    'dashboard.thRole': 'Role',
    'dashboard.thDegree': 'Degree',
    'dashboard.thBetw': 'Betweenness',
    'dashboard.thEigen': 'Eigenvector',
    'dashboard.thRisk': 'Risk score',
    'dashboard.profileTitle': 'Selected account',
    'dashboard.profileFollowers': 'Followers',
    'dashboard.profilePosts': 'Posts',
    'dashboard.profileShareLbl': 'Shares',
    'dashboard.profileCommentLbl': 'Comments',
    'dashboard.clustersDetected': 'Communities',
    'dashboard.clusterUnit': 'clusters',
    'dashboard.clusterCountFmt': '{n}',
    'dashboard.recPanelTitle': 'Interventions',
    'dashboard.recR1': 'Control high risk',
    'dashboard.recR2': 'Monitor betweenness',
    'dashboard.recR3': 'Flag unusual groups',
    'dashboard.recR4': 'Review odd clusters',
    'dashboard.recSeeAll': 'Details →',
    'dashboard.metricEngagement': 'Engagement',
    'dashboard.metricHighRisk': 'High risk',
    'dashboard.systemStatusLabel': 'System status',
    'dashboard.systemStatusReady': 'Ready',
    'dashboard.systemStatusWaiting': 'Awaiting data',
    'dashboard.systemStatusReadyMsg': 'Data loaded — network analysis available',
    'dashboard.systemStatusWaitingMsg': 'No output dataset yet',
    'dashboard.systemStatusDetail':
      '{users} accounts · {edges} edges · {high} high risk · {shown}/{total} nodes on graph',
    'dashboard.systemStatusWaitingDetail': 'Use «Import data» in the left menu to generate or upload CSV',
    'dashboard.statGraphNodes': 'Nodes on graph',
    'dashboard.statClustersFmt': '{n} communities',
    'dashboard.footerVer': 'Version',
    'dashboard.footerUpd': 'Updated',
    'dashboard.lblModel': 'Model',
    'dashboard.lblPeakDay': 'Peak day',
    'dashboard.lblPeakI': 'Peak infected',
    'dashboard.lblFinal': 'End day',
    'dashboard.lblOutput': 'Output folder',
    'dashboard.riskBadge.High': 'High risk',
    'dashboard.riskBadge.Medium': 'Medium risk',
    'dashboard.riskBadge.Low': 'Low risk',
    'dashboard.riskBadge.Unknown': 'Unknown',
    'toast.guide': 'Click a node on the graph for metrics; use Generate data for a new network.',
    'toast.export': 'Data lives in output_* folders on the server (CSV).',
    'toast.report': 'Summary sections are at the bottom and in intervention suggestions.',
    'toast.menuReports': 'Scroll to the footer for version and timestamp.',
    toast_generated: 'Data generated. Dashboard updated.',
    toast_uploaded: 'Upload processed. Dashboard updated.',
    toast_cleanup_done: 'Old outputs cleaned.',
    toast_sim_done: 'SIR simulation completed. Results saved.',
    ask_open_sir: 'Simulation finished. Open the SIR page to view charts and tune parameters?',
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
  if (lastSummaryPayload) applySummary(lastSummaryPayload);
  if (graphData) updateGraphVizCaption(graphData);
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
  const t = dict['dashboard.docTitle'];
  if (t) document.title = t;
}

function initLanguage() {
  setLang(getLang());
  const btn = document.getElementById('langToggle');
  if (btn) btn.addEventListener('click', () => setLang(getLang() === 'en' ? 'vi' : 'en'));
}

// Toasts (replace alert spam)
function ensureToastRoot() {
  let root = document.getElementById('toastRoot');
  if (root) return root;
  root = document.createElement('div');
  root.id = 'toastRoot';
  root.className = 'toast-root';
  document.body.appendChild(root);
  return root;
}

function toast(message, variant = 'info', timeoutMs = 3200) {
  const root = ensureToastRoot();
  const item = document.createElement('div');
  item.className = `toast toast-${variant}`;
  item.textContent = message;
  root.appendChild(item);
  window.setTimeout(() => {
    item.classList.add('toast-hide');
    window.setTimeout(() => item.remove(), 220);
  }, timeoutMs);
}

// Modal Management
function openDataGenModal() {
  const modal = document.getElementById('dataGenModal');
  modal.classList.add('show');
  initDataGenForm();
}

function closeDataGenModal() {
  const modal = document.getElementById('dataGenModal');
  modal.classList.remove('show');
}

function initDataGenForm() {
  // Initialize form values
  document.getElementById('numUsers').value = 500;
  document.getElementById('relationshipProb').value = 0.025;
  document.getElementById('randomSeed').value = 42;
  document.getElementById('dataSource').value = 'generate';
  toggleFileUpload(false);

  // Add event listeners
  document.getElementById('dataSource').onchange = function() {
    toggleFileUpload(this.value === 'upload');
  };

  // Handle confirm button
  document.getElementById('btnConfirmGenerate').onclick = handleDataGeneration;
}

function toggleFileUpload(show) {
  const fileGroup = document.getElementById('fileUploadGroup');
  fileGroup.style.display = show ? 'grid' : 'none';
}

async function handleDataGeneration() {
  const dataSource = document.getElementById('dataSource').value;

  if (dataSource === 'generate') {
    await runGenerator();
  } else {
    await uploadAndProcessFile();
  }

  closeDataGenModal();
}

async function uploadAndProcessFile() {
  const fileInput = document.getElementById('dataFile');
  const file = fileInput.files[0];

  if (!file) {
    showError('Vui lòng chọn file CSV để upload');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  const btn = document.getElementById('btnConfirmGenerate');
  const originalText = btn.textContent;
  btn.textContent = 'Đang xử lý...';
  btn.disabled = true;

  try {
    const response = await fetch('/api/upload-data', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) throw new Error(`API lỗi ${response.status}`);

    await loadDashboard();
    clearSIRResult();
    toast(I18N[getLang()].toast_uploaded, 'success');
  } catch (error) {
    showError('Lỗi khi upload dữ liệu: ' + error.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

// Loading States
function showLoading(element, message = 'Đang tải...') {
  if (!element) {
    console.warn('Cannot show loading: element is null');
    return;
  }
  element.classList.add('loading');
  if (!element.querySelector('.loading-overlay')) {
    const overlay = document.createElement('div');
    overlay.className = 'loading-overlay';
    overlay.innerHTML = `
      <div class="spinner"></div>
      <p>${message}</p>
    `;
    element.appendChild(overlay);
  }
}

function hideLoading(element) {
  if (!element) {
    console.warn('Cannot hide loading: element is null');
    return;
  }
  element.classList.remove('loading');
  const overlay = element.querySelector('.loading-overlay');
  if (overlay) overlay.remove();
}

let graphData = null;
/** Bản payload graph/summary gần nhất — dùng khi đổi ngôn ngữ để cập nhật metric. */
let lastSummaryPayload = null;
let networkGalaxy = null;
let selectedNodeId = null;
let sirResultData = null;

/** Màu flat khớp backend RISK_COLORS */
const RISK_SOLID = {
  High: '#d94a4a',
  Medium: '#e8924a',
  Low: '#4b80c9',
  Unknown: '#c8cdd6',
};

function setSirField(panel, id, text) {
  const el = panel?.querySelector(id);
  if (el) el.textContent = text;
}

function renderSIRResult(result) {
  const panel = document.getElementById('sirResultPanel');
  if (!panel) return;

  setSirField(panel, '#sirModel', result.model === 'dynamic' ? 'SIR động' : 'SIR thuần');
  setSirField(panel, '#sirPeakDay', result.peak_day);
  setSirField(panel, '#sirPeakInfected', result.peak_infected);
  setSirField(panel, '#sirFinalDay', result.final_day);
  setSirField(panel, '#sirOutputPath', result.output_directory || 'N/A');
  setSirField(panel, '#sirStatusText', 'Đã chạy mô phỏng thành công');
  panel.classList.add('active');
}

function clearSIRResult() {
  const panel = document.getElementById('sirResultPanel');
  if (!panel) return;
  setSirField(panel, '#sirModel', '-');
  setSirField(panel, '#sirPeakDay', '-');
  setSirField(panel, '#sirPeakInfected', '-');
  setSirField(panel, '#sirFinalDay', '-');
  setSirField(panel, '#sirOutputPath', '-');
  setSirField(panel, '#sirStatusText', 'Chưa có kết quả mô phỏng');
  panel.classList.remove('active');
}

function formatNumber(value) {
  return Number(value).toLocaleString('vi-VN');
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: 'no-store' });
  let data = {};
  try {
    data = await response.json();
  } catch {
    /* ignore */
  }
  if (!response.ok) {
    const msg = data.error || data.hint || data.message || `HTTP ${response.status}`;
    throw new Error(msg);
  }
  return data;
}

function applySummary(data) {
  lastSummaryPayload = data;
  const n = Number(data.nodes) || 0;
  const e = Number(data.edges) || 0;
  const ready = data.ready !== false && n > 0;

  const setText = (id, text) => {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
  };

  const nodesList = data.nodes_data || [];
  const highRisk =
    Number(data.high_risk_accounts) ||
    nodesList.filter((x) => String(x.risk) === 'High').length;
  const kpiRow = document.getElementById('dashKpiRow');
  if (kpiRow) {
    kpiRow.classList.toggle('dash-kpi-row--disabled', !ready);
  }

  const setKpi = (id, value, empty) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = ready && !empty ? value : '—';
    el.closest('.dash-kpi')?.classList.toggle('dash-kpi--empty', !ready || empty);
  };

  setKpi('stat-users', formatNumber(n), n === 0);
  setKpi('stat-edges', formatNumber(e), e === 0);
  setKpi('stat-high-risk', formatNumber(highRisk), false);

  const riskCard = document.getElementById('statHighRiskCard');
  if (riskCard) {
    riskCard.classList.toggle('dash-kpi--alert', ready && highRisk > 0);
  }

  setText('footerTimestamp', data.timestamp || '—');
}

function riskScoreCellClass(score) {
  const s = Number(score) || 0;
  if (s >= 85) return 'risk-cell risk-cell--high';
  if (s >= 65) return 'risk-cell risk-cell--med';
  if (s >= 40) return 'risk-cell risk-cell--low';
  return 'risk-cell risk-cell--unknown';
}

const RISK_WEIGHTS_KEY = 'dashRiskWeights';
const DEFAULT_RISK_WEIGHTS = { betweenness: 0.4, degree: 0.35, eigenvector: 0.25 };
const TOP_NODES_LIMIT = 10;
const RISK_WEIGHT_MIN = 0.001;
const RISK_WEIGHT_MAX = 0.999;

/** Trọng số phải nằm trong (0, 1) — không bao gồm 0 hay 1. */
function clampRiskWeight(value, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(RISK_WEIGHT_MAX, Math.max(RISK_WEIGHT_MIN, n));
}

function normalizeRiskWeights(weights) {
  return {
    betweenness: clampRiskWeight(weights.betweenness, DEFAULT_RISK_WEIGHTS.betweenness),
    degree: clampRiskWeight(weights.degree, DEFAULT_RISK_WEIGHTS.degree),
    eigenvector: clampRiskWeight(weights.eigenvector, DEFAULT_RISK_WEIGHTS.eigenvector),
  };
}

function loadRiskWeights() {
  try {
    const raw = localStorage.getItem(RISK_WEIGHTS_KEY);
    if (!raw) return { ...DEFAULT_RISK_WEIGHTS };
    const parsed = JSON.parse(raw);
    const w = {
      betweenness: Number(parsed.betweenness),
      degree: Number(parsed.degree),
      eigenvector: Number(parsed.eigenvector),
    };
    if (w.betweenness >= 1 || w.degree >= 1 || w.eigenvector >= 1) {
      return { ...DEFAULT_RISK_WEIGHTS };
    }
    return normalizeRiskWeights(w);
  } catch {
    return { ...DEFAULT_RISK_WEIGHTS };
  }
}

function saveRiskWeights(weights) {
  localStorage.setItem(RISK_WEIGHTS_KEY, JSON.stringify(weights));
}

function syncRiskWeightInputs(weights) {
  const bet = document.getElementById('weightBetweenness');
  const deg = document.getElementById('weightDegree');
  const eig = document.getElementById('weightEigenvector');
  if (bet) bet.value = String(weights.betweenness);
  if (deg) deg.value = String(weights.degree);
  if (eig) eig.value = String(weights.eigenvector);
}

function readRiskWeightsFromInputs() {
  const bet = parseFloat(document.getElementById('weightBetweenness')?.value);
  const deg = parseFloat(document.getElementById('weightDegree')?.value);
  const eig = parseFloat(document.getElementById('weightEigenvector')?.value);
  return normalizeRiskWeights({
    betweenness: bet,
    degree: deg,
    eigenvector: eig,
  });
}

function rawRiskScore(node, weights) {
  const w = weights || loadRiskWeights();
  const bt = Number(node.betweenness) || 0;
  const degC = Number(node.degree_metric);
  const deg =
    Number.isFinite(degC) && degC <= 1
      ? degC
      : Number(node.degree_centrality) || 0;
  const ev = Number(node.eigenvector) || 0;
  return w.betweenness * bt + w.degree * deg + w.eigenvector * ev;
}

/** Chuẩn hóa điểm 0–100 theo min–max trong tập nút (khớp backend). */
function normalizeRiskScores(nodes, weights) {
  if (!nodes.length) return [];
  const w = weights || loadRiskWeights();
  const raws = nodes.map((n) => rawRiskScore(n, w));
  const lo = Math.min(...raws);
  const hi = Math.max(...raws);
  const span = hi - lo;
  return nodes.map((node, i) => {
    const raw = raws[i];
    let risk_score;
    if (span <= 1e-12) {
      risk_score = raw > 0 ? 50 : 0;
    } else {
      risk_score = Math.round((100 * (raw - lo)) / span);
    }
    const risk = riskLabelFromScore(risk_score);
    return { ...node, risk_score, risk };
  });
}

function computeRiskScore(node, weights) {
  return Number(node.risk_score) || 0;
}

function displayDegreeMetric(node) {
  const v = node.degree_metric ?? node.degree;
  return Number(v).toFixed(3);
}

function riskLabelFromScore(score) {
  const s = Number(score) || 0;
  if (s >= 85) return 'High';
  if (s >= 65) return 'Medium';
  if (s >= 40) return 'Low';
  return 'Unknown';
}

function getRankingSource() {
  if (!graphData) return [];
  if (graphData.ranking_nodes?.length) return graphData.ranking_nodes;
  if (graphData.nodes_data?.length) {
    return graphData.nodes_data.map((n) => ({
      id: n.id,
      name: n.name,
      role: n.role,
      degree: n.degree,
      degree_metric: n.degree_metric,
      betweenness: n.betweenness,
      eigenvector: n.eigenvector,
      risk_score: n.risk_score,
      risk: n.risk,
    }));
  }
  return graphData.top_nodes || [];
}

/** Cập nhật nhãn / opacity (risk_score đã có sau normalizeRiskScores). */
function patchNodeRiskFields(node, weights) {
  const risk_score = Number(node.risk_score) || 0;
  const risk = node.risk || riskLabelFromScore(risk_score);
  const opacity = Math.min(1, 0.42 + (risk_score / 100) * 0.48);
  const patched = { ...node, risk_score, risk, opacity };
  const total = graphData?.viz_nodes_total ?? graphData?.nodes ?? 0;
  const flatRiskColors =
    graphData && !graphData.viz_representative && total <= 2000;
  if (flatRiskColors) {
    const fill = RISK_SOLID[risk] || RISK_SOLID.Unknown;
    patched.node_fill = fill;
    patched.risk_fill = fill;
    patched.color = fill;
  }
  return patched;
}

function syncTopNodesFromGraph() {
  if (!graphData) return;
  const top =
    graphData.top_nodes?.length > 0
      ? graphData.top_nodes
      : [...(graphData.ranking_nodes || [])]
          .sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0))
          .slice(0, TOP_NODES_LIMIT);
  renderTopNodes(top);
  drawGraph();
}

function applyRiskWeights(weights) {
  if (!graphData) return;
  const w = weights || loadRiskWeights();
  const source = getRankingSource();
  if (!source.length) {
    if (graphData.top_nodes?.length) renderTopNodes(graphData.top_nodes);
    return;
  }

  const updated = normalizeRiskScores(source, w).map((node) => patchNodeRiskFields(node, w));
  graphData.ranking_nodes = updated;
  const top = [...updated].sort((a, b) => b.risk_score - a.risk_score).slice(0, TOP_NODES_LIMIT);
  graphData.top_nodes = top;

  if (graphData.nodes_data) {
    const byId = new Map(updated.map((n) => [n.id, n]));
    graphData.nodes_data = graphData.nodes_data.map((n) => {
      const ranked = byId.get(n.id);
      const base = ranked
        ? { ...n, risk_score: ranked.risk_score, risk: ranked.risk }
        : n;
      return patchNodeRiskFields(base, w);
    });
  }

  const highRisk = updated.filter((n) => n.risk === 'High').length;
  if (lastSummaryPayload) {
    applySummary({ ...lastSummaryPayload, high_risk_accounts: highRisk });
  }

  renderTopNodes(top);
  if (selectedNodeId != null) {
    const node = graphData.nodes_data?.find((item) => item.id === selectedNodeId);
    if (node) renderProfile(node);
  }
  drawGraph();
}

function initRiskWeightsUI() {
  const weights = loadRiskWeights();
  syncRiskWeightInputs(weights);

  let riskWeightTimer;
  const onChange = () => {
    const w = readRiskWeightsFromInputs();
    syncRiskWeightInputs(w);
    saveRiskWeights(w);
    applyRiskWeights(w);
  };
  const scheduleApply = () => {
    clearTimeout(riskWeightTimer);
    riskWeightTimer = setTimeout(onChange, 220);
  };

  ['weightBetweenness', 'weightDegree', 'weightEigenvector'].forEach((id) => {
    const el = document.getElementById(id);
    el?.addEventListener('change', onChange);
    el?.addEventListener('input', scheduleApply);
  });

  document.getElementById('btnResetRiskWeights')?.addEventListener('click', () => {
    saveRiskWeights({ ...DEFAULT_RISK_WEIGHTS });
    syncRiskWeightInputs(DEFAULT_RISK_WEIGHTS);
    applyRiskWeights(DEFAULT_RISK_WEIGHTS);
  });
}

function inferRiskScore(node) {
  if (node.risk_score != null) return Number(node.risk_score);
  return rawRiskScore(node, loadRiskWeights()) * 100;
}

function renderTopNodes(topNodes) {
  const tbody = document.getElementById('topNodesTable');
  if (!tbody) return;
  tbody.innerHTML = '';

  topNodes.slice(0, TOP_NODES_LIMIT).forEach((node, index) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${index + 1}</td>
      <td class="td-account">${node.name}</td>
      <td>${Number(node.betweenness).toFixed(3)}</td>
      <td>${displayDegreeMetric(node)}</td>
      <td>${Number(node.eigenvector).toFixed(3)}</td>
    `;
    tbody.appendChild(tr);
    tr.addEventListener('click', () => {
      setSelectedNode(node.id);
    });
  });
}

function renderClusters(clusters) {
  const list = document.getElementById('clustersList');
  if (!list) return;
  list.innerHTML = '';
  const fmt =
    (I18N[getLang()] || I18N.vi)['dashboard.clusterCountFmt'] || '{n} tài khoản';
  clusters.forEach((cluster) => {
    const li = document.createElement('li');
    li.className = 'cluster-item';
    li.innerHTML = `
      <div class="cluster-label"><span class="cluster-chip" style="background:${cluster.color}"></span>${cluster.name}</div>
      <div>${fmt.replace('{n}', formatNumber(cluster.count))}</div>
    `;
    list.appendChild(li);
  });
}

function renderClusterLegend(clusters) {
  const wrap = document.getElementById('clusterLegendItems');
  if (!wrap) return;
  wrap.innerHTML = '';
  (clusters || []).forEach((c) => {
    const span = document.createElement('span');
    const dot = document.createElement('span');
    dot.className = 'cluster-legend-dot';
    dot.style.background = c.color;
    span.appendChild(dot);
    span.appendChild(document.createTextNode(`${c.name} (${c.count})`));
    wrap.appendChild(span);
  });
}

function riskPillClass(risk) {
  const r = String(risk || '');
  if (r === 'High') return 'risk-pill risk-pill--high';
  if (r === 'Medium') return 'risk-pill risk-pill--medium';
  if (r === 'Low') return 'risk-pill risk-pill--low';
  if (r === 'Unknown') return 'risk-pill risk-pill--unknown';
  return 'risk-pill risk-pill--muted';
}

function riskPillLabel(risk) {
  const lang = getLang();
  const dict = I18N[lang] || I18N.vi;
  const key = `dashboard.riskBadge.${String(risk || '')}`;
  if (dict[key]) return dict[key];
  return risk || '—';
}

function renderProfile(node) {
  const nameEl = document.getElementById('selectedName');
  const roleLine = document.getElementById('selectedRoleLine');
  const riskBadge = document.getElementById('selectedRiskBadge');

  if (!node) {
    if (nameEl) nameEl.textContent = '—';
    if (roleLine) roleLine.textContent = '—';
    if (riskBadge) {
      riskBadge.textContent = '—';
      riskBadge.className = 'risk-pill risk-pill--muted';
    }
    const cb = document.getElementById('selectedClusterBadge');
    if (cb) {
      cb.textContent = '—';
      cb.style.borderLeft = '';
    }
    const z = (id) => document.getElementById(id);
    if (z('selectedFollowers')) z('selectedFollowers').textContent = '0';
    if (z('selectedPosts')) z('selectedPosts').textContent = '0';
    if (z('selectedShares')) z('selectedShares').textContent = '0';
    if (z('selectedComments')) z('selectedComments').textContent = '0';
    if (roleLine) roleLine.textContent = '—';
    return;
  }
  if (nameEl) nameEl.textContent = node.name;
  if (roleLine) roleLine.textContent = node.role || '—';
  if (riskBadge) {
    const rs = node.risk_score != null ? Number(node.risk_score) : null;
    riskBadge.textContent =
      rs != null ? `${riskPillLabel(node.risk)} · ${formatNumber(Math.round(rs))}` : riskPillLabel(node.risk);
    riskBadge.className = riskPillClass(node.risk);
  }
  const cb = document.getElementById('selectedClusterBadge');
  if (cb) {
    cb.textContent = node.cluster || '—';
    cb.style.borderLeft = `4px solid ${node.cluster_color || '#9ca3af'}`;
  }
  const setNum = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = formatNumber(val);
  };
  setNum('selectedFollowers', node.followers);
  setNum('selectedPosts', node.posts);
  setNum('selectedShares', node.shares);
  setNum('selectedComments', node.comments);
}

function setSelectedNode(nodeId) {
  selectedNodeId = nodeId;
  const node = graphData?.nodes_data?.find((item) => item.id === nodeId);
  if (node) renderProfile(node);
  if (networkGalaxy) networkGalaxy.setSelected(nodeId);
  else drawGraph();
}

function ensureNetworkGalaxy() {
  if (networkGalaxy) return networkGalaxy;
  const mount = document.getElementById('networkGraphMount');
  const Factory = globalThis.NetworkViz || globalThis.NetworkGalaxy;
  if (!mount || typeof Factory === 'undefined') return null;
  networkGalaxy = Factory.create(mount);
  return networkGalaxy;
}

function drawGraph() {
  if (!graphData) return;
  const viz = ensureNetworkGalaxy();
  if (!viz) return;
  const labelMode = document.getElementById('labelToggle')?.value || 'smart';
  const filter = document.getElementById('graphFilter')?.value || 'all';
  viz.load(graphData, {
    labelMode,
    filter,
    selectedId: selectedNodeId,
    onNodeSelect: (id) => {
      selectedNodeId = id;
      const node = graphData.nodes_data.find((item) => item.id === id);
      if (node) renderProfile(node);
    },
  });
}

function updateGraphVizCaption(data) {
  const el = document.querySelector('#dash-graph .subtext');
  if (!el || !data) return;
  const dict = I18N[getLang()] || I18N.vi;
  const total = data.viz_nodes_total ?? data.nodes ?? 0;
  const shown = data.viz_nodes_shown ?? (data.nodes_data || []).length;
  const edges = data.viz_edges_shown ?? (data.edges_data || []).length;
  const edgesTotal = data.viz_edges_total ?? data.edges ?? edges;
  if (data.viz_mode === 'full' || data.viz_mode === 'full_capped') {
    const tpl =
      dict['dashboard.graphSubFull'] ||
      'Toàn mạng: {shown}/{total} nút · {edges}/{edgesTotal} cạnh (lọc nhãn/bộ lọc áp dụng trên canvas).';
    el.textContent = tpl
      .replace('{shown}', formatNumber(shown))
      .replace('{total}', formatNumber(total))
      .replace('{edges}', formatNumber(edges))
      .replace('{edgesTotal}', formatNumber(edgesTotal));
  } else if (data.viz_mode === 'sna' || data.viz_mode === 'galaxy') {
    const tpl =
      dict['dashboard.graphSubSna'] ||
      dict['dashboard.graphSubGalaxy'] ||
      '{shown}/{total} nút · {edges} cạnh — phân tích mạng';
    el.textContent = tpl
      .replace('{shown}', formatNumber(shown))
      .replace('{total}', formatNumber(total))
      .replace('{edges}', formatNumber(edges));
  } else if (data.viz_mode === 'summary' && total > shown) {
    const tpl = dict['dashboard.graphSubSummary'] || '{shown}/{total}';
    el.textContent = tpl
      .replace('{shown}', formatNumber(shown))
      .replace('{total}', formatNumber(total))
      .replace('{edges}', formatNumber(edges));
  } else {
    el.textContent = dict['dashboard.graphSub'] || '';
  }
}

function showError(message) {
  console.error(message);
  // Create a better error notification
  const errorDiv = document.createElement('div');
  errorDiv.className = 'error-message';
  errorDiv.textContent = message;
  errorDiv.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--danger);
    color: white;
    padding: 12px 16px;
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    z-index: 1000;
    animation: slideIn 0.3s ease-out;
    max-width: 300px;
  `;
  document.body.appendChild(errorDiv);
  setTimeout(() => errorDiv.remove(), 5000);
}

async function loadDashboard() {
  const graphContainer =
    document.querySelector('.sna-graph-canvas-wrap') ||
    document.querySelector('.graph-container');
  showLoading(graphContainer, 'Đang tải dữ liệu...');

  try {
    const graph = await fetchJson('/api/graph?refresh=1');
    graphData = graph;
    if (graph.ready === false && graph.hint) {
      toast(graph.hint, 'info', 4500);
    }
    selectedNodeId =
      graph.top_nodes?.[0]?.id ?? graph.nodes_data?.[0]?.id ?? null;
    syncTopNodesFromGraph();
    applySummary(graphData);
    updateGraphVizCaption(graphData);
    renderClusters(graph.clusters || []);
    renderClusterLegend(graph.clusters || []);
    const cc = document.getElementById('clusterCountNum');
    if (cc) cc.textContent = String((graph.clusters || []).length);
    renderProfile(
      selectedNodeId != null
        ? graphData.nodes_data?.find((item) => item.id === selectedNodeId)
        : null
    );
  } catch (error) {
    showError('Không thể tải dữ liệu từ server: ' + error.message);
  } finally {
    hideLoading(graphContainer);
  }
}

async function runGenerator() {
  const numUsers = parseInt(document.getElementById('numUsers').value);
  const relationshipProb = parseFloat(document.getElementById('relationshipProb').value);
  const seed = parseInt(document.getElementById('randomSeed').value);

  const btn = document.getElementById('btnConfirmGenerate');
  const originalText = btn.textContent;
  btn.textContent = 'Đang tạo...';
  btn.disabled = true;

  try {
    const payload = {
      num_users: numUsers,
      relationship_prob: relationshipProb,
      seed: seed
    };
    const response = await fetch('/api/run-generator', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    let errBody = {};
    try {
      errBody = await response.json();
    } catch {
      /* ignore */
    }
    if (!response.ok) {
      throw new Error(errBody.error || `API lỗi ${response.status}`);
    }
    await loadDashboard();
    clearSIRResult();
    toast(I18N[getLang()].toast_generated, 'success');
  } catch (error) {
    showError('Lỗi khi tạo dữ liệu: ' + error.message);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
}

async function runSimulate(model) {
  const btn =
    model === 'pure'
      ? document.getElementById('btnRunPureSIR')
      : document.getElementById('btnRunDynamicSIR');
  const originalText = btn ? btn.textContent : '';
  if (btn) {
    btn.textContent = 'Đang chạy...';
    btn.disabled = true;
  }

  try {
    const payload = {
      model,
      transmission_rate: 0.3,
      recovery_rate: 0.02,
      days: 300,
      seed: 42,
      top_k: 10,
      strategy: 'betweenness'
    };
    const response = await fetch('/api/run-simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`API lỗi ${response.status}`);
    const result = await response.json();
    sirResultData = result;
    renderSIRResult(result);
    await loadDashboard();
    const go = window.confirm(
      I18N[getLang()].ask_open_sir
    );
    if (go && result.redirect_url) {
      window.location.href = result.redirect_url;
    } else if (!go) {
      toast(I18N[getLang()].toast_sim_done, 'success');
    }
  } catch (error) {
    showError('Lỗi khi chạy mô phỏng: ' + error.message);
  } finally {
    if (btn) {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }
}

async function cleanupOldOutputs() {
  const shouldCleanup = window.confirm('Giữ lại 3 bộ dữ liệu mới nhất và xóa các output cũ?');
  if (!shouldCleanup) return;

  const btn = document.getElementById('btnCleanupOutputs');
  const originalText = btn ? btn.textContent : '';
  if (btn) {
    btn.textContent = 'Đang dọn...';
    btn.disabled = true;
  }

  try {
    const response = await fetch('/api/cleanup-outputs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keep_latest: 3, include_uploaded: true }),
    });
    if (!response.ok) throw new Error(`API lỗi ${response.status}`);
    const result = await response.json();
    toast(`${I18N[getLang()].toast_cleanup_done} (${result.removed_count})`, 'success');
    await loadDashboard();
  } catch (error) {
    showError('Không thể dọn output cũ: ' + error.message);
  } finally {
    if (btn) {
      btn.textContent = originalText;
      btn.disabled = false;
    }
  }
}

function init() {
  initTheme();
  initLanguage();

  const themeToggle = document.getElementById('themeToggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', toggleTheme);
  }

  document.getElementById('refreshGraph')?.addEventListener('click', loadDashboard);
  const dataSource = document.getElementById('dataSource');
  if (dataSource) {
    dataSource.onchange = function () {
      toggleFileUpload(this.value === 'upload');
    };
  }
  document.getElementById('btnCleanupOutputs')?.addEventListener('click', cleanupOldOutputs);
  document.getElementById('graphFilter')?.addEventListener('change', (e) => {
    if (networkGalaxy) networkGalaxy.setFilter(e.target.value);
  });
  document.getElementById('labelToggle')?.addEventListener('change', () => {
    const mode = document.getElementById('labelToggle')?.value || 'smart';
    if (networkGalaxy) networkGalaxy.setLabelMode(mode);
  });
  document.getElementById('zoomIn')?.addEventListener('click', () => {
    if (networkGalaxy) networkGalaxy.zoomIn();
  });
  document.getElementById('zoomOut')?.addEventListener('click', () => {
    if (networkGalaxy) networkGalaxy.zoomOut();
  });

  const menuOpenData = document.getElementById('menuOpenData');
  if (menuOpenData) menuOpenData.addEventListener('click', openDataGenModal);

  loadDashboard();

  window.addEventListener('app:langchange', () => {
    if (graphData) updateGraphVizCaption(graphData);
  });
}

window.addEventListener('DOMContentLoaded', init);
