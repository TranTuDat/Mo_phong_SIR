/** Trang graph độc lập — chỉ visualization, không dashboard. */
(function () {
  let viz = null;
  let graphPayload = null;

  async function fetchJson(path) {
    const res = await fetch(path, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.message || `HTTP ${res.status}`);
    return data;
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

  function updateCaption(data) {
    const el = document.getElementById('graphCaption');
    if (!el || !data) return;
    const shown = data.viz_nodes_shown ?? (data.nodes_data || []).length;
    const total = data.viz_nodes_total ?? data.nodes ?? shown;
    const edges = data.viz_edges_shown ?? (data.edges_data || []).length;
    const loc = window.I18N?.getLang?.() === 'en' ? 'en-GB' : 'vi-VN';
    const tpl =
      (window.I18N && window.I18N.t && window.I18N.t('msgs.graphCaption')) ||
      '{shown}/{total} nút · {edges} cạnh hiển thị';
    el.textContent = tpl
      .replace('{shown}', Number(shown).toLocaleString(loc))
      .replace('{total}', Number(total).toLocaleString(loc))
      .replace('{edges}', Number(edges).toLocaleString(loc));
  }

  async function loadGraph() {    const wrap = document.querySelector('.sna-graph-canvas-wrap');
    if (wrap) wrap.style.opacity = '0.6';
    try {
      const data = await fetchJson('/api/graph?refresh=1');
      graphPayload = data;
      if (!viz) {
        const mount = document.getElementById('networkGraphMount');
        viz = NetworkViz.create(mount);
      }
      if (!viz) throw new Error('Không khởi tạo được đồ thị');
      const labelMode = document.getElementById('labelToggle')?.value || 'smart';
      const filter = document.getElementById('graphFilter')?.value || 'all';
      viz.load(data, { labelMode, filter });
      renderClusterLegend(data.clusters || []);
      updateCaption(data);
    } catch (e) {
      const cap = document.getElementById('graphCaption');
      const err =
        (window.I18N && window.I18N.t && window.I18N.t('msgs.errLoad')) || 'Không tải được dữ liệu.';
      if (cap) cap.textContent = err + ' ' + e.message;      console.error(e);
    } finally {
      if (wrap) wrap.style.opacity = '1';
    }
  }

  function init() {
    window.onSharedDataReady = () => loadGraph();
    window.SharedNav?.init({});

    window.addEventListener('app:langchange', () => {
      if (graphPayload) updateCaption(graphPayload);
    });

    document.getElementById('refreshGraph')?.addEventListener('click', loadGraph);    document.getElementById('graphFilter')?.addEventListener('change', (e) => {
      if (viz) viz.setFilter(e.target.value);
    });
    document.getElementById('labelToggle')?.addEventListener('change', (e) => {
      if (viz) viz.setLabelMode(e.target.value);
    });
    document.getElementById('zoomIn')?.addEventListener('click', () => viz?.zoomIn());
    document.getElementById('zoomOut')?.addEventListener('click', () => viz?.zoomOut());
    document.getElementById('resetView')?.addEventListener('click', () => viz?.resetView());
    loadGraph();
  }

  window.addEventListener('DOMContentLoaded', init);
})();
