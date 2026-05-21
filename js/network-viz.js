/**
 * Social network graph — clean analytical style (Canvas / force-graph).
 * Requires vendor/force-graph.min.js
 */
(function (global) {
  const BG = '#f8fafc';
  const EDGE_BASE = 'rgba(148, 163, 184,';
  const EDGE_REP = 'rgba(71, 85, 105,';
  const EDGE_HI = 'rgba(37, 99, 235, 0.72)';
  const PAD = 16;
  const LABEL_COLOR = '#475569';

  function hexToRgb(hex) {
    const h = (hex || '#94a3b8').replace('#', '');
    const n = parseInt(h.length === 3 ? h.split('').map((c) => c + c).join('') : h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }

  function rgba(hex, a) {
    const { r, g, b } = hexToRgb(hex);
    return `rgba(${r},${g},${b},${a})`;
  }

  function nodeDrawRadius(node, relSize) {
    const base = node.radius || Math.sqrt(Math.max(1, node.val || 4));
    return base * relSize * 1.05;
  }

  /** force-graph@1.49 không có .refresh() — kích hoạt vẽ lại qua accessor. */
  function redrawGraph(state) {
    const fg = state?.fg;
    if (!fg) return;
    try {
      if (typeof fg.nodeCanvasObject === 'function') {
        const draw = fg.nodeCanvasObject();
        if (draw) fg.nodeCanvasObject(draw);
      }
      if (typeof fg.linkColor === 'function') {
        const lc = fg.linkColor();
        if (lc) fg.linkColor(lc);
      }
      if (typeof fg.linkWidth === 'function') {
        const lw = fg.linkWidth();
        if (lw) fg.linkWidth(lw);
      }
    } catch (err) {
      console.warn('redrawGraph:', err);
    }
  }

  function refreshCanvasSize(state) {
    const fg = state.fg;
    if (!fg) return;
    const wrap = state.mountEl.parentElement;
    const isDashEmbed = document.body.classList.contains('dash-pro');
    const minH = isDashEmbed ? 140 : 500;
    const fallbackH = isDashEmbed ? 280 : 660;
    const w = Math.max(320, wrap?.clientWidth || state.mountEl.clientWidth || 800);
    const h = Math.max(minH, wrap?.clientHeight || state.mountEl.clientHeight || fallbackH);
    if (w === state.width && h === state.height) return;
    state.width = w;
    state.height = h;
    fg.width(w).height(h);
  }

  /** zoomToFit sau khi canvas đã có kích thước thật (dashboard flex / ResizeObserver). */
  function scheduleZoomToFit(state, ms = 520, pad = 72) {
    const fg = state.fg;
    if (!fg) return;
    const run = () => {
      refreshCanvasSize(state);
      try {
        fg.zoomToFit(ms, pad);
      } catch (err) {
        console.warn('zoomToFit:', err);
      }
    };
    requestAnimationFrame(() => {
      requestAnimationFrame(run);
    });
    setTimeout(run, 140);
    if (state.representative) {
      setTimeout(run, 360);
    } else {
      setTimeout(run, 720);
    }
  }

  function buildAdjacency(links) {
    const adj = new Map();
    const touch = (a, b) => {
      if (!adj.has(a)) adj.set(a, new Set());
      adj.get(a).add(b);
    };
    links.forEach((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      touch(a, b);
      touch(b, a);
    });
    return adj;
  }

  function edgeOpacity(state, link) {
    if (link.dimmed) return 0.04;
    if (link.highlight) return 0.72;
    if (state.representative) {
      return link.inter ? 0.22 : 0.34;
    }
    const n = state.graphData.nodes.length;
    if (n > 800) return 0.1;
    return 0.14;
  }

  function edgeWidth(state, link) {
    if (link.dimmed) return 0.18;
    if (link.highlight) return 1.25;
    if (state.representative) {
      const w = Number(link.weight) || 1;
      const boost = Math.min(0.2, Math.log1p(w) * 0.03);
      return link.inter ? 0.65 + boost : 0.82 + boost;
    }
    return state.graphData.nodes.length > 600 ? 0.5 : 0.7;
  }

  function create(mountEl) {
    if (!mountEl || typeof global.ForceGraph !== 'function') {
      console.error('force-graph chưa được tải');
      return null;
    }

    mountEl.innerHTML = '';
    mountEl.classList.add('sna-graph-mount');

    const state = {
      mountEl,
      fg: null,
      width: 0,
      height: 0,
      graphData: { nodes: [], links: [] },
      fullData: { nodes: [], links: [] },
      adjacency: new Map(),
      labelMode: 'smart',
      filter: 'all',
      selectedId: null,
      hoverId: null,
      egoId: null,
      resizeObs: null,
      representative: false,
      clusterLayout: false,
      frameTick: 0,
    };

    const fg = global.ForceGraph()(mountEl)
      .backgroundColor(BG)
      .enableNodeDrag(true)
      .enableZoomInteraction(true)
      .enablePanInteraction(true)
      .nodeId('id')
      .nodeVal((n) => Math.max(1, (n.radius || 4) * 0.72))
      .nodeRelSize(0.62)
      .linkSource('source')
      .linkTarget('target')
      .linkWidth((l) => edgeWidth(state, l))
      .linkColor((l) => linkColor(state, l))
      .linkCurvature(0)
      .linkDirectionalParticles(0)
      .nodeCanvasObjectMode(() => 'replace')
      .nodeCanvasObject((node, ctx, globalScale) => drawNode(node, ctx, globalScale, state))
      .onNodeHover((node) => onNodeHover(node, state))
      .onNodeClick((node) => onNodeClick(node, state))
      .onBackgroundClick(() => {
        clearEgo(state);
        fg.zoomToFit(480, 52);
      })
      .cooldownTicks(80)
      .warmupTicks(40)
      .d3AlphaDecay(0.04)
      .d3VelocityDecay(0.45);

    state.fg = fg;

    const applySize = () => refreshCanvasSize(state);

    applySize();
    if (typeof ResizeObserver !== 'undefined') {
      state.resizeObs = new ResizeObserver(() => {
        const prevW = state.width;
        const prevH = state.height;
        applySize();
        clampNodes(state);
        redrawGraph(state);
        if (state.graphData?.nodes?.length && (state.width !== prevW || state.height !== prevH)) {
          scheduleZoomToFit(state, 400, 64);
        }
      });
      const observeEl = mountEl.parentElement || mountEl;
      state.resizeObs.observe(observeEl);
    }

    let tickN = 0;
    fg.onEngineTick(() => {
      state.frameTick += 1;
      clampNodes(state);
      tickN += 1;
      if (tickN > 90 && tickN < 95) {
        state.graphData.nodes.forEach((n) => {
          n.vx *= 0.4;
          n.vy *= 0.4;
        });
      }
    });

    mountEl.addEventListener('dblclick', () => {
      clearEgo(state);
      state.selectedId = null;
      fg.zoomToFit(480, 52);
    });

    return {
      load(payload, opts = {}) {
        loadPayload(state, payload, opts);
      },
      setFilter(filter) {
        state.filter = filter || 'all';
        applyFilter(state);
      },
      setSelected(id) {
        state.selectedId = id;
        state.egoId = null;
        resetDim(state);
        if (id != null) highlightEgo(state, id, false);
        redrawGraph(state);
      },
      setLabelMode(mode) {
        state.labelMode = mode || 'smart';
        redrawGraph(state);
      },
      zoomIn() {
        fg.zoom(fg.zoom() * 1.2, 300);
      },
      zoomOut() {
        fg.zoom(fg.zoom() / 1.2, 300);
      },
      resetView() {
        clearEgo(state);
        state.selectedId = null;
        resetDim(state);
        fg.zoomToFit(480, 52);
      },
      destroy() {
        if (state.resizeObs) state.resizeObs.disconnect();
        mountEl.innerHTML = '';
      },
    };
  }

  function linkColor(state, link) {
    if (link.dimmed) return `${EDGE_BASE}0.06)`;
    if (link.highlight) return EDGE_HI;
    const col = link.color || '#94a3b8';
    const op = edgeOpacity(state, link);
    if (state.representative) {
      return `${EDGE_REP}${op})`;
    }
    return `${EDGE_BASE}${op})`;
  }

  function shouldDrawLabel(node, state) {
    if (node.dimmed && state.egoId != null) return false;
    if (state.labelMode === 'off') return false;
    if (state.labelMode === 'hover') return state.hoverId === node.id;
    if (state.hoverId === node.id || state.selectedId === node.id) return true;
    if (node.show_label || node.viz_tier === 'hub') return true;
    if (node.risk === 'High' && (node.viz_tier === 'hub' || node.viz_tier === 'medium')) return true;
    return false;
  }

  function drawNode(node, ctx, globalScale, state) {
    const rel = state.fg.nodeRelSize();
    const r = nodeDrawRadius(node, rel) / Math.max(globalScale, 0.45);
    const dim = node.dimmed;
    const color = node.color || '#c8cdd6';
    const alpha = dim ? 0.15 : node.opacity ?? 0.9;
    const tier = node.viz_tier || 'medium';
    const hub = tier === 'hub' || node.cluster_hub;

    if (hub && !dim) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, r + 3 / globalScale, 0, 2 * Math.PI);
      ctx.fillStyle = rgba(color, 0.1);
      ctx.fill();
    }

    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = rgba(color, alpha);
    ctx.fill();
    ctx.strokeStyle = dim
      ? 'rgba(203,213,225,0.35)'
      : state.selectedId === node.id
        ? '#2563eb'
        : '#ffffff';
    ctx.lineWidth =
      state.selectedId === node.id ? 2.2 / globalScale : hub ? 1.5 / globalScale : 1 / globalScale;
    ctx.stroke();

    if (shouldDrawLabel(node, state)) {
      const label = node.shortName || node.name || '';
      if (!label) return;
      const fs = Math.max(8, Math.min(11, 9 / globalScale));
      ctx.font = `600 ${fs}px system-ui, "Segoe UI", sans-serif`;
      ctx.fillStyle = LABEL_COLOR;
      ctx.textAlign = 'left';
      ctx.textBaseline = 'middle';
      ctx.fillText(label, node.x + r + 4, node.y);
    }
  }

  function clampNodes(state) {
    const { width: w, height: h, graphData } = state;
    if (!graphData?.nodes?.length) return;
    graphData.nodes.forEach((n) => {
      if (n.x == null || n.y == null) return;
      n.x = Math.max(PAD, Math.min(w - PAD, n.x));
      n.y = Math.max(PAD, Math.min(h - PAD, n.y));
    });
  }

  function resetDim(state) {
    state.graphData.nodes.forEach((n) => {
      n.dimmed = false;
    });
    state.graphData.links.forEach((l) => {
      l.dimmed = false;
      l.highlight = false;
    });
  }

  function highlightEgo(state, centerId, zoom) {
    const ego = new Set([centerId]);
    (state.adjacency.get(centerId) || []).forEach((nid) => ego.add(nid));
    state.graphData.nodes.forEach((n) => {
      n.dimmed = !ego.has(n.id);
    });
    state.graphData.links.forEach((l) => {
      const a = l.source.id ?? l.source;
      const b = l.target.id ?? l.target;
      const inEgo = ego.has(a) && ego.has(b);
      l.dimmed = !inEgo;
      l.highlight = inEgo && (a === centerId || b === centerId);
    });
    if (zoom) {
      const node = state.graphData.nodes.find((n) => n.id === centerId);
      if (node) {
        state.fg.centerAt(node.x, node.y, 380);
        state.fg.zoom(Math.min(3.2, state.fg.zoom() * 1.28), 380);
      }
    }
  }

  function onNodeHover(node, state) {
    const next = node ? node.id : null;
    if (state.hoverId === next) return;
    state.hoverId = next;
    if (state.egoId != null) {
      redrawGraph(state);
      return;
    }
    if (next != null) {
      const ego = new Set([next]);
      (state.adjacency.get(next) || []).forEach((nid) => ego.add(nid));
      state.graphData.nodes.forEach((n) => {
        n.dimmed = !ego.has(n.id);
      });
      state.graphData.links.forEach((l) => {
        const a = l.source.id ?? l.source;
        const b = l.target.id ?? l.target;
        const onPath = a === next || b === next;
        l.dimmed = !onPath && !(ego.has(a) && ego.has(b));
        l.highlight = onPath;
      });
    } else {
      resetDim(state);
      if (state.selectedId != null) highlightEgo(state, state.selectedId, false);
    }
    redrawGraph(state);
  }

  function onNodeClick(node, state) {
    if (!node) return;
    if (state.egoId === node.id) {
      clearEgo(state);
      return;
    }
    state.egoId = node.id;
    state.selectedId = node.id;
    highlightEgo(state, node.id, true);
    if (typeof state.onNodeSelect === 'function') state.onNodeSelect(node.id);
    redrawGraph(state);
  }

  function clearEgo(state) {
    state.egoId = null;
    resetDim(state);
    redrawGraph(state);
  }

  function nodeSeparation(a, b) {
    const ra = (a.radius || 4) * 1.2 + 10;
    const rb = (b.radius || 4) * 1.2 + 10;
    return Math.max(56, ra + rb + 24);
  }

  function clampNodeToCanvas(node, pad, w, h) {
    node.x = Math.max(pad, Math.min(w - pad, node.x));
    node.y = Math.max(pad, Math.min(h - pad, node.y));
  }

  function sameClusterNode(a, b) {
    const ca = a.cluster || '';
    const cb = b.cluster || '';
    return Boolean(ca && cb && ca === cb);
  }

  /** Giữ cụm từ server: hút theo cạnh, chỉ đẩy mạnh trong cùng cụm. */
  function refineClusterGroupedLayout(nodes, links, w, h) {
    const n = nodes.length;
    if (n < 2) return;

    const pad = 52;
    const idMap = new Map(nodes.map((nd) => [nd.id, nd]));
    const edges = [];
    links.forEach((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      if (idMap.has(a) && idMap.has(b)) edges.push([a, b]);
    });

    nodes.forEach((node) => {
      if (node.x == null || node.y == null) {
        node.x = w / 2;
        node.y = h / 2;
      }
    });

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    nodes.forEach((nd) => {
      minX = Math.min(minX, nd.x);
      maxX = Math.max(maxX, nd.x);
      minY = Math.min(minY, nd.y);
      maxY = Math.max(maxY, nd.y);
    });
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const span = Math.max(maxX - minX, maxY - minY, 80);
    const targetSpan = Math.min(w, h) * 0.82;
    const scale = Math.min(1.2, Math.max(0.9, targetSpan / span));
    nodes.forEach((nd) => {
      nd.x = (nd.x - cx) * scale + w / 2;
      nd.y = (nd.y - cy) * scale + h / 2;
      clampNodeToCanvas(nd, pad, w, h);
    });

    const targetEdge = Math.min(w, h) * 0.055;
    const iters = 64;
    const linkInter = new Map();
    links.forEach((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      const key = a < b ? `${a}|${b}` : `${b}|${a}`;
      linkInter.set(key, !!(l.inter || l.inter_cluster));
    });

    for (let step = 0; step < iters; step += 1) {
      const t = step / Math.max(iters - 1, 1);
      const repelK = 0.5 + 0.18 * t;
      const attractK = 0.38 + 0.2 * t;

      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const same = sameClusterNode(a, b);
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.hypot(dx, dy) || 0.01;
          const need = same ? nodeSeparation(a, b) : Math.min(28, nodeSeparation(a, b) * 0.45);
          if (d < need) {
            const push = (need - d) * (same ? repelK : repelK * 0.12);
            const ux = dx / d;
            const uy = dy / d;
            a.x -= ux * push;
            a.y -= uy * push;
            b.x += ux * push;
            b.y += uy * push;
          }
        }
      }

      edges.forEach(([aid, bid]) => {
        const a = idMap.get(aid);
        const b = idMap.get(bid);
        if (!a || !b) return;
        const key = aid < bid ? `${aid}|${bid}` : `${bid}|${aid}`;
        const isInter = linkInter.get(key);
        const ideal = isInter ? targetEdge * 1.05 : targetEdge * 0.88;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const pullBoost = isInter ? 1.15 : 1.35;
        if (d > ideal * 1.02) {
          const pull = (d - ideal) * attractK * pullBoost;
          const ux = dx / d;
          const uy = dy / d;
          a.x += ux * pull;
          a.y += uy * pull;
          b.x -= ux * pull;
          b.y -= uy * pull;
        }
      });

      nodes.forEach((nd) => clampNodeToCanvas(nd, pad, w, h));
    }
  }

  function refineRepresentativeLayout(nodes, links, w, h) {
    const n = nodes.length;
    if (n < 2) return;

    const pad = 58;
    const idMap = new Map(nodes.map((nd) => [nd.id, nd]));
    const edges = [];
    links.forEach((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      if (idMap.has(a) && idMap.has(b)) edges.push([a, b]);
    });

    nodes.forEach((node) => {
      if (node.x == null || node.y == null) {
        node.x = w / 2;
        node.y = h / 2;
      }
    });

    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    nodes.forEach((nd) => {
      minX = Math.min(minX, nd.x);
      maxX = Math.max(maxX, nd.x);
      minY = Math.min(minY, nd.y);
      maxY = Math.max(maxY, nd.y);
    });
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;
    const span = Math.max(maxX - minX, maxY - minY, 80);
    const targetSpan = Math.min(w, h) * 0.78;
    const scale = Math.min(1.35, Math.max(0.85, targetSpan / span));
    nodes.forEach((nd) => {
      nd.x = (nd.x - cx) * scale + w / 2;
      nd.y = (nd.y - cy) * scale + h / 2;
      clampNodeToCanvas(nd, pad, w, h);
    });

    const targetEdge = Math.min(w, h) * 0.062;
    const iters = 80;
    const linkInter = new Map();
    links.forEach((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      const key = a < b ? `${a}|${b}` : `${b}|${a}`;
      linkInter.set(key, !!(l.inter || l.inter_cluster));
    });

    for (let step = 0; step < iters; step += 1) {
      const t = step / Math.max(iters - 1, 1);
      const repelK = 0.58 + 0.22 * t;
      const attractK = 0.3 + 0.22 * t;

      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.hypot(dx, dy) || 0.01;
          const need = nodeSeparation(a, b);
          if (d < need) {
            const push = (need - d) * repelK;
            const ux = dx / d;
            const uy = dy / d;
            a.x -= ux * push;
            a.y -= uy * push;
            b.x += ux * push;
            b.y += uy * push;
          }
        }
      }

      edges.forEach(([aid, bid]) => {
        const a = idMap.get(aid);
        const b = idMap.get(bid);
        if (!a || !b) return;
        const key = aid < bid ? `${aid}|${bid}` : `${bid}|${aid}`;
        const isInter = linkInter.get(key);
        const ideal = isInter ? targetEdge * 0.9 : targetEdge;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.hypot(dx, dy) || 0.01;
        const pullBoost = isInter ? 1.2 : 1.0;
        if (d > ideal * 1.04) {
          const pull = (d - ideal) * attractK * pullBoost;
          const ux = dx / d;
          const uy = dy / d;
          a.x += ux * pull;
          a.y += uy * pull;
          b.x -= ux * pull;
          b.y -= uy * pull;
        } else if (d < ideal * 0.5) {
          const push = (ideal * 0.5 - d) * 0.14;
          const ux = dx / d;
          const uy = dy / d;
          a.x -= ux * push;
          a.y -= uy * push;
          b.x += ux * push;
          b.y += uy * push;
        }
      });

      nodes.forEach((nd) => clampNodeToCanvas(nd, pad, w, h));
    }
  }

  function spreadNodesOnCanvas(nodes, links, w, h, state) {
    if (state?.representative) {
      if (state.clusterLayout) {
        refineClusterGroupedLayout(nodes, links || [], w, h);
      } else {
        refineRepresentativeLayout(nodes, links || [], w, h);
      }
      return;
    }
    const n = nodes.length;
    if (n < 2) return;
    const pad = 52;
    const minGap = 38;
    nodes.forEach((node) => {
      if (node.x == null || node.y == null) {
        node.x = w / 2;
        node.y = h / 2;
      }
      clampNodeToCanvas(node, pad, w, h);
    });
    for (let pass = 0; pass < 32; pass += 1) {
      let moved = false;
      for (let i = 0; i < n; i += 1) {
        for (let j = i + 1; j < n; j += 1) {
          const a = nodes[i];
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const d = Math.hypot(dx, dy) || 0.01;
          const need = minGap + (a.radius || 4) + (b.radius || 4);
          if (d < need) {
            const push = (need - d) * 0.55;
            const ux = dx / d;
            const uy = dy / d;
            a.x -= ux * push;
            a.y -= uy * push;
            b.x += ux * push;
            b.y += uy * push;
            moved = true;
          }
        }
      }
      nodes.forEach((node) => clampNodeToCanvas(node, pad, w, h));
      if (!moved) break;
    }
  }

  function pinAllNodes(state) {
    state.graphData.nodes.forEach((n) => {
      if (n.x != null && n.y != null) {
        n.fx = n.x;
        n.fy = n.y;
      }
    });
  }

  function mapNode(n, w, h) {
    const xn = n.x_norm != null ? n.x_norm : (n.x || 0) / 900;
    const yn = n.y_norm != null ? n.y_norm : (n.y || 0) / 700;
    const name = n.name || `User_${n.id}`;
    const rad = n.radius || 4;
    return {
      id: n.id,
      name,
      shortName: name.replace(/\s+/g, '_').slice(0, 24),
      radius: rad,
      val: Math.max(0.8, rad),
      color: n.node_fill || n.risk_fill || n.color || '#c8cdd6',
      cluster: n.cluster || '',
      cluster_color: n.cluster_color || '#94a3b8',
      opacity: n.opacity ?? 0.72,
      viz_tier: n.viz_tier || 'background',
      cluster_hub: n.cluster_hub,
      viz_bridge: n.viz_bridge,
      show_label: n.show_label,
      influence: n.influence ?? 0,
      risk: n.risk,
      x: xn * w,
      y: yn * h,
      _raw: n,
    };
  }

  function applyFilter(state) {
    const { fullData, filter, width: w, height: h } = state;
    let nodes = [...fullData.nodes];
    if (filter === 'high') nodes = nodes.filter((n) => n.risk === 'High');
    else if (filter === 'medium') nodes = nodes.filter((n) => n.risk === 'Medium');
    else if (filter === 'low') nodes = nodes.filter((n) => n.risk === 'Low');
    else if (filter === 'hubs') nodes = nodes.filter((n) => n.viz_tier === 'hub' || n.cluster_hub);

    const ids = new Set(nodes.map((n) => n.id));
    const links = fullData.links.filter((l) => {
      const a = typeof l.source === 'object' ? l.source.id : l.source;
      const b = typeof l.target === 'object' ? l.target.id : l.target;
      return ids.has(a) && ids.has(b);
    });

    state.graphData = { nodes, links };
    state.adjacency = buildAdjacency(links);

    if (state.representative) {
      spreadNodesOnCanvas(nodes, links, state.width, state.height, state);
      pinAllNodes(state);
      state.fg.graphData(state.graphData);
      configureForces(state);
      state.fg.cooldownTicks(0);
      scheduleZoomToFit(state, 520, 88);
      redrawGraph(state);
      return;
    }

    unpinLayout(state);
    state.fg.graphData(state.graphData);
    configureForces(state);
    state.fg.d3ReheatSimulation();
    scheduleZoomToFit(state, 480, 64);
  }

  function pinLayout(state) {
    state.graphData.nodes.forEach((n) => {
      if (n.x != null && n.y != null) {
        n.fx = n.x;
        n.fy = n.y;
      }
    });
  }

  function unpinLayout(state) {
    state.graphData.nodes.forEach((n) => {
      n.fx = undefined;
      n.fy = undefined;
    });
  }

  function configureForces(state) {
    const n = state.graphData.nodes.length;
    const fg = state.fg;
    const rep = state.representative || n <= 55;

    if (rep) {
      fg.d3Force('charge')?.strength(0);
      fg.d3Force('link')?.strength(0);
      const collide = fg.d3Force('collide');
      if (collide) {
        collide.radius((node) => (node.radius || 4) + 20);
      }
    } else {
      const charge = -8 - Math.sqrt(Math.max(n, 1)) * 2.8;
      const linkDist = n > 600 ? 22 : 28;
      fg.d3Force('charge')?.strength(charge);
      fg.d3Force('link')?.distance(linkDist).strength(0.48);
      const collide = fg.d3Force('collide');
      if (collide) {
        collide.radius((node) => nodeDrawRadius(node, fg.nodeRelSize()) + 2);
      }
    }
  }

  function loadPayload(state, payload, opts) {
    refreshCanvasSize(state);
    const w = state.width;
    const h = state.height;
    const nodes = (payload.nodes_data || []).map((n) => mapNode(n, w, h));
    const links = (payload.edges_data || []).map((e) => ({
      source: e.source,
      target: e.target,
      inter: Boolean(e.inter_cluster),
      color: e.color || null,
      weight: e.weight,
      dimmed: false,
      highlight: false,
    }));

    state.fullData = {
      nodes: nodes.map((n) => ({ ...n })),
      links: links.map((l) => ({ ...l })),
    };
    state.filter = opts.filter || state.filter;
    state.labelMode = opts.labelMode || state.labelMode;
    state.selectedId = opts.selectedId ?? state.selectedId;
    state.onNodeSelect = opts.onNodeSelect;
    state.egoId = null;
    state.representative = payload.viz_representative === true;
    state.clusterLayout = payload.viz_cluster_layout === true;
    applyFilter(state);

    if (opts.selectedId != null) highlightEgo(state, opts.selectedId, false);
  }

  global.NetworkViz = { create };
  global.NetworkGalaxy = global.NetworkViz;
})(typeof window !== 'undefined' ? window : globalThis);
