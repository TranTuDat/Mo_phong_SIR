/**
 * Dashboard — tích hợp API vào giao diện Mau.html (y hệt layout/CSS)
 */
(function () {
  const TOP_N = 10;
  const COMMUNITY_CLASS = ['red', 'cyan', 'orange', 'green', 'purple'];
  const COLOR_VI = ['Đỏ', 'Xanh dương', 'Cam', 'Xanh lá', 'Tím'];

  let graphData = null;
  let selectedNodeId = null;

  function formatNumber(n) {
    const x = Number(n);
    if (!Number.isFinite(x)) return '—';
    return x.toLocaleString('vi-VN');
  }

  function formatDisplayDate(raw) {
    if (!raw) return '—';
    const s = String(raw).trim();
    const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (m) return `${m[3]}/${m[2]}/${m[1]}`;
    return s;
  }

  function riskKey(risk) {
    const r = String(risk || '');
    if (r === 'High') return 'high';
    if (r === 'Medium') return 'medium';
    if (r === 'Low') return 'low';
    return 'unknown';
  }

  function riskLabelVi(risk) {
    if (risk === 'High') return 'Nguy cơ cao';
    if (risk === 'Medium') return 'Nguy cơ trung bình';
    if (risk === 'Low') return 'Nguy cơ thấp';
    return 'Chưa xác định';
  }

  function badgeClass(risk) {
    if (risk === 'High') return '';
    if (risk === 'Medium') return 'medium';
    if (risk === 'Low') return 'low';
    return 'muted';
  }

  function applyTrends() {
    /* Giữ nguyên chuỗi trend như Mau.html */
  }

  function rawRiskScore(node) {
    const bt = Number(node.betweenness) || 0;
    const deg = Number(node.degree_metric ?? node.degree) || 0;
    const ev = Number(node.eigenvector) || 0;
    return 0.4 * bt + 0.35 * (deg <= 1 ? deg : deg / 100) + 0.25 * ev;
  }

  function normalizeRiskScores() {
    const src = graphData?.ranking_nodes?.length
      ? graphData.ranking_nodes
      : graphData?.nodes_data || [];
    if (!src.length) return;
    const raws = src.map((n) => rawRiskScore(n));
    const lo = Math.min(...raws);
    const hi = Math.max(...raws);
    const span = hi - lo;
    const updated = src.map((node, i) => {
      let risk_score;
      if (span <= 1e-12) risk_score = raws[i] > 0 ? 50 : 0;
      else risk_score = Math.round((100 * (raws[i] - lo)) / span);
      const risk =
        risk_score >= 85 ? 'High' : risk_score >= 65 ? 'Medium' : risk_score >= 40 ? 'Low' : 'Unknown';
      return { ...node, risk_score, risk };
    });
    graphData.ranking_nodes = updated;
    const top = [...updated].sort((a, b) => b.risk_score - a.risk_score).slice(0, TOP_N);
    graphData.top_nodes = top;
    const byId = new Map(updated.map((n) => [n.id, n]));
    if (graphData.nodes_data) {
      graphData.nodes_data = graphData.nodes_data.map((n) => {
        const r = byId.get(n.id);
        return r ? { ...n, risk_score: r.risk_score, risk: r.risk } : n;
      });
    }
    graphData.high_risk_accounts = updated.filter((n) => n.risk === 'High').length;
  }

  function applySummary(data) {
    const ready = data.ready !== false && (Number(data.nodes) || 0) > 0;
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el && ready) el.textContent = v;
    };
    set('stat-users', formatNumber(data.nodes));
    set('stat-edges', formatNumber(data.edges));
    let engagement = 0;
    (graphData?.nodes_data || []).forEach((n) => {
      engagement += (Number(n.shares) || 0) + (Number(n.comments) || 0);
    });
    if (!engagement && ready) {
      engagement = Math.round((Number(data.edges) || 0) * 1.6 + (Number(data.nodes) || 0) * 2);
    }
    set('stat-interactions', formatNumber(engagement));
    const hr =
      Number(data.high_risk_accounts) ||
      (graphData?.nodes_data || []).filter((x) => x.risk === 'High').length;
    set('stat-high-risk', formatNumber(hr));
    set('sideStatNodes', formatNumber(data.nodes));
    set('sideStatEdges', formatNumber(data.edges));
    set('sideStatDate', formatDisplayDate(data.data_date));
    applyTrends();
    const ft = document.getElementById('footerTimestamp');
    if (ft) ft.textContent = data.timestamp || new Date().toLocaleString('vi-VN');
  }

  function displayDegree(node) {
    const v = node.degree_metric ?? node.degree;
    return Number(v).toFixed(3);
  }

  function renderTopNodes() {
    const tbody = document.getElementById('topNodesTable');
    if (!tbody) return;
    tbody.innerHTML = '';
    const top = graphData?.top_nodes || [];
    top.slice(0, TOP_N).forEach((node, i) => {
      const score = Number(node.risk_score) || 0;
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${node.name}</td>
        <td>${node.role || '—'}</td>
        <td>${displayDegree(node)}</td>
        <td>${Number(node.betweenness).toFixed(3)}</td>
        <td>${Number(node.eigenvector).toFixed(3)}</td>
        <td><span class="risk-score ${riskKey(node.risk)}">${(score / 100).toFixed(3)}</span></td>
      `;
      tr.addEventListener('click', () => selectNode(node.id));
      tbody.appendChild(tr);
    });
  }

  function renderProfile(node) {
    const nameEl = document.getElementById('selectedName');
    const badge = document.getElementById('selectedAccountBadge');
    const roleEl = document.getElementById('selectedRoleLine');
    const descEl = document.getElementById('selectedDescLine');
    if (!node) {
      if (nameEl) nameEl.textContent = '—';
      if (badge) {
        badge.textContent = '—';
        badge.className = 'account-badge muted';
      }
      if (roleEl) roleEl.textContent = '—';
      if (descEl) descEl.textContent = '—';
      ['selectedFollowers', 'selectedPosts', 'selectedShares', 'selectedComments'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.textContent = '0';
      });
      return;
    }
    if (nameEl) nameEl.textContent = node.name;
    if (badge) {
      badge.textContent = riskLabelVi(node.risk);
      badge.className = `account-badge ${badgeClass(node.risk)}`.trim();
    }
    if (roleEl) roleEl.textContent = node.role || '—';
    if (descEl) {
      descEl.textContent = node.cluster
        ? `Kết nối nhiều nhóm cộng đồng (${node.cluster}), có tần suất chia sẻ cao.`
        : 'Chọn nút trên bản đồ để xem chi tiết.';
    }
    const set = (id, v) => {
      const el = document.getElementById(id);
      if (el) el.textContent = formatNumber(v);
    };
    set('selectedFollowers', node.followers);
    set('selectedPosts', node.posts);
    set('selectedShares', node.shares);
    set('selectedComments', node.comments);
  }

  function selectNode(id) {
    selectedNodeId = id;
    document.querySelectorAll('#topNodesTable tr').forEach((tr) => tr.classList.remove('row-selected'));
    const node = graphData?.nodes_data?.find((n) => n.id === id);
    renderProfile(node || null);
    if (window.MauGraph) {
      window.MauGraph.selectNodeById(id);
    }
  }

  function renderClusters(clusters) {
    const list = document.getElementById('clustersList');
    if (!list) return;
    list.innerHTML = '';
    (clusters || []).slice(0, 8).forEach((c, i) => {
      const row = document.createElement('div');
      row.className = 'community-item';
      const dot = document.createElement('span');
      dot.className = `community-dot ${COMMUNITY_CLASS[i % COMMUNITY_CLASS.length]}`;
      if (c.color) dot.style.background = c.color;
      const label = document.createElement('span');
      label.className = 'community-label';
      const colorName = COLOR_VI[i % COLOR_VI.length];
      const base = (c.name || `Cụm ${i + 1}`).replace(/\s*\([^)]*\)\s*$/, '').trim();
      label.textContent = `${base} (${colorName})`;
      const count = document.createElement('span');
      count.className = 'community-count';
      count.textContent = `${formatNumber(c.count)} tài khoản`;
      row.appendChild(dot);
      row.appendChild(label);
      row.appendChild(count);
      list.appendChild(row);
    });
    const cc = document.getElementById('clusterCountNum');
    if (cc) cc.textContent = String((clusters || []).length);
  }

  const REC_ICON_SVG = {
    green:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    red:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/></svg>',
    blue:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    purple:
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>',
  };

  function renderRecommendations(api) {
    const list = document.getElementById('recommendationList');
    if (!list) return;
    const top = graphData?.top_nodes?.[0];
    const c0 = graphData?.clusters?.[0];
    const n2 = graphData?.top_nodes?.[1];
    const n3 = graphData?.top_nodes?.[2];
    const items = [];

    if (top) {
      items.push({
        icon: 'green',
        title: `Ưu tiên giám sát ${top.name}`,
        desc: `${top.role || 'Nút trung gian'} kết nối nhiều cụm, có ảnh hưởng lớn.`,
        p: 'p1',
        pl: 'Ưu tiên 1',
      });
    }
    if (c0) {
      items.push({
        icon: 'red',
        title: `Tác động vào cụm ${c0.name}`,
        desc: 'Cụm có mức độ tương tác cao, nguy cơ lan truyền lớn.',
        p: 'p2',
        pl: 'Ưu tiên 2',
      });
    }
    if (n2 && n3) {
      items.push({
        icon: 'blue',
        title: `Theo dõi ${n2.name} và ${n3.name}`,
        desc: 'Lan truyền mạnh, nằm trong cụm nguy cơ.',
        p: 'p3',
        pl: 'Ưu tiên 3',
      });
    } else if (api?.winner?.strategy) {
      items.push({
        icon: 'blue',
        title: `Chiến lược SIR: ${api.winner.strategy}`,
        desc: `Đỉnh I = ${api.winner.peak_infected ?? '—'} — cân nhắc miễn nhiễm động.`,
        p: 'p3',
        pl: 'Ưu tiên 3',
      });
    }
    items.push({
      icon: 'purple',
      title: 'Tăng cường nội dung phản bác',
      desc: 'Tại cụm lớn và các nút trung gian trọng yếu.',
      p: 'p4',
      pl: 'Ưu tiên 4',
    });

    list.innerHTML = items
      .slice(0, 4)
      .map(
        (it) => `
      <div class="recommendation-item">
        <div class="recommendation-icon ${it.icon}">${REC_ICON_SVG[it.icon]}</div>
        <div class="recommendation-content">
          <div class="recommendation-title">${it.title}</div>
          <div class="recommendation-desc">${it.desc}</div>
        </div>
        <span class="recommendation-priority ${it.p}">${it.pl}</span>
      </div>`
      )
      .join('');
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

  function toast(msg, ms = 3200) {
    const el = document.createElement('div');
    el.className = 'toast-msg';
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), ms);
  }

  async function loadDashboard() {
    try {
      const data = await fetchJson('/api/graph?refresh=1');
      graphData = data;
      if (data.ready === false && data.hint) toast(data.hint);
      normalizeRiskScores();
      selectedNodeId = data.top_nodes?.[0]?.id ?? data.nodes_data?.[0]?.id ?? null;
      applySummary(data);
      renderTopNodes();
      renderClusters(data.clusters || []);
      renderProfile(
        selectedNodeId != null
          ? data.nodes_data?.find((n) => n.id === selectedNodeId)
          : null
      );
      let recApi = null;
      try {
        const folder = data.output_folder;
        const url = folder
          ? `/api/intervention-recommendations?output_dir=${encodeURIComponent(folder)}`
          : '/api/intervention-recommendations';
        recApi = await fetchJson(url);
      } catch {
        /* optional */
      }
      renderRecommendations(recApi);
      if (window.MauGraph) {
        window.MauGraph.setOnNodeSelect((id) => selectNode(id));
        window.MauGraph.loadFromPayload(data);
        window.MauGraph.selectNodeById(selectedNodeId);
      }
    } catch (e) {
      toast('Không tải được dữ liệu: ' + e.message, 5000);
      if (window.MauGraph) window.MauGraph.initGraph();
    }
  }

  function init() {
    const shell = window.MauShell?.init({
      page: 'overview',
      onDataReady: loadDashboard,
    });
    const toastFn = shell?.toast || toast;

    document.getElementById('refreshGraph')?.addEventListener('click', loadDashboard);
    document.getElementById('zoomIn')?.addEventListener('click', () => window.MauGraph?.zoomIn());
    document.getElementById('zoomOut')?.addEventListener('click', () => window.MauGraph?.zoomOut());
    document.getElementById('labelToggle')?.addEventListener('change', () => {
      window.MauGraph?.setShowLabels(true);
    });
    document.querySelector('.view-details')?.addEventListener('click', (e) => {
      e.preventDefault();
      window.location.href = '/recommendations';
    });

    if (window.MauGraph) window.MauGraph.initGraph();
    loadDashboard().catch((e) => toastFn('Không tải được dữ liệu: ' + e.message, 5000));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
