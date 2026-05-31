/* Canvas graph */
(function (global) {
// Advanced Force-Directed Graph with D3-style physics
    const canvas = document.getElementById('networkCanvas');
    const ctx = canvas.getContext('2d');
    
    let scale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let isDragging = false;
    let dragNode = null;
    let lastX, lastY;
    let nodes = [];
    let links = [];
    let animationId;
    let alpha = 1; // Simulation temperature
    let showLabels = true;
    let onNodeSelect = null;
    let useApiLayout = false;
    let selectedApiId = null;

    // Cluster configuration with better spacing
    const clusterCenters = [
      { x: 0.25, y: 0.28, color: '#ef4444', name: 'Red' },
      { x: 0.75, y: 0.25, color: '#06b6d4', name: 'Cyan' },
      { x: 0.5, y: 0.5, color: '#f97316', name: 'Orange' },
      { x: 0.2, y: 0.75, color: '#22c55e', name: 'Green' },
      { x: 0.8, y: 0.75, color: '#8b5cf6', name: 'Purple' },
    ];

    const riskColors = { 
      high: '#ef4444', 
      medium: '#f97316', 
      low: '#3b82f6', 
      unknown: '#9ca3af' 
    };

    // Key nodes data matching the table
    const keyNodesData = [
      { label: 'User_15', cluster: 0, risk: 'high', importance: 0.912 },
      { label: 'User_03', cluster: 0, risk: 'high', importance: 0.845 },
      { label: 'User_22', cluster: 1, risk: 'high', importance: 0.768 },
      { label: 'User_07', cluster: 2, risk: 'medium', importance: 0.742 },
      { label: 'User_11', cluster: 2, risk: 'medium', importance: 0.712 },
      { label: 'User_45', cluster: 3, risk: 'medium', importance: 0.658 },
      { label: 'User_29', cluster: 1, risk: 'low', importance: 0.612 },
      { label: 'User_31', cluster: 4, risk: 'low', importance: 0.578 },
      { label: 'User_02', cluster: 3, risk: 'low', importance: 0.551 },
      { label: 'User_18', cluster: 4, risk: 'low', importance: 0.523 },
    ];

    function generateNodes() {
      nodes = [];
      
      // Create key nodes first
      keyNodesData.forEach((data, i) => {
        const center = clusterCenters[data.cluster];
        const angle = Math.random() * Math.PI * 2;
        const r = 0.03 + Math.random() * 0.05;
        nodes.push({
          id: i,
          label: data.label,
          x: center.x + Math.cos(angle) * r,
          y: center.y + Math.sin(angle) * r,
          vx: 0,
          vy: 0,
          cluster: data.cluster,
          risk: data.risk,
          importance: data.importance,
          size: 8 + data.importance * 8,
          isKey: true,
          fixed: false
        });
      });

      // Generate cluster nodes with varying densities
      const clusterSizes = [28, 24, 22, 18, 16];
      
      clusterSizes.forEach((count, c) => {
        const center = clusterCenters[c];
        
        for (let i = 0; i < count; i++) {
          // Use golden angle for better distribution
          const goldenAngle = Math.PI * (3 - Math.sqrt(5));
          const angle = i * goldenAngle + Math.random() * 0.3;
          const radius = 0.06 + Math.sqrt(i / count) * 0.1 + Math.random() * 0.03;
          
          const riskRoll = Math.random();
          let risk;
          if (c === 0 && riskRoll < 0.35) risk = 'high';
          else if (riskRoll < 0.2) risk = 'high';
          else if (riskRoll < 0.45) risk = 'medium';
          else if (riskRoll < 0.8) risk = 'low';
          else risk = 'unknown';
          
          nodes.push({
            id: nodes.length,
            label: '',
            x: center.x + Math.cos(angle) * radius,
            y: center.y + Math.sin(angle) * radius,
            vx: 0,
            vy: 0,
            cluster: c,
            risk: risk,
            importance: 0.1 + Math.random() * 0.3,
            size: 2.5 + Math.random() * 2.5,
            isKey: false,
            fixed: false
          });
        }
      });
    }

    function generateLinks() {
      links = [];
      const linkSet = new Set();
      
      const addLink = (s, t, strength, isInterCluster = false) => {
        const key = s < t ? `${s}-${t}` : `${t}-${s}`;
        if (!linkSet.has(key) && s !== t) {
          linkSet.add(key);
          links.push({ 
            source: s, 
            target: t, 
            strength: strength,
            isInterCluster: isInterCluster
          });
        }
      };
      
      // Dense intra-cluster connections
      for (let c = 0; c < 5; c++) {
        const clusterNodes = nodes.filter(n => n.cluster === c);
        const keyNodes = clusterNodes.filter(n => n.isKey);
        const regularNodes = clusterNodes.filter(n => !n.isKey);
        
        // Connect key nodes to many cluster members
        keyNodes.forEach(keyNode => {
          regularNodes.forEach(node => {
            if (Math.random() < 0.6) {
              addLink(keyNode.id, node.id, 0.3 + Math.random() * 0.3);
            }
          });
        });
        
        // Connect regular nodes to nearby nodes
        regularNodes.forEach((node, i) => {
          const connections = 2 + Math.floor(Math.random() * 3);
          for (let j = 0; j < connections; j++) {
            const target = regularNodes[Math.floor(Math.random() * regularNodes.length)];
            if (target.id !== node.id) {
              addLink(node.id, target.id, 0.2 + Math.random() * 0.2);
            }
          }
        });
      }
      
      // Inter-cluster connections through key nodes (bridges)
      const bridgeConnections = [
        [0, 2], [0, 1], [1, 2], [2, 3], [2, 4], [3, 4], [0, 3], [1, 4]
      ];
      
      bridgeConnections.forEach(([c1, c2]) => {
        const keys1 = nodes.filter(n => n.cluster === c1 && n.isKey);
        const keys2 = nodes.filter(n => n.cluster === c2 && n.isKey);
        
        if (keys1.length && keys2.length && Math.random() < 0.7) {
          const k1 = keys1[Math.floor(Math.random() * keys1.length)];
          const k2 = keys2[Math.floor(Math.random() * keys2.length)];
          addLink(k1.id, k2.id, 0.15 + Math.random() * 0.15, true);
        }
      });
      
      // Special connections for User_15 (main hub)
      const user15 = nodes.find(n => n.label === 'User_15');
      if (user15) {
        nodes.filter(n => n.isKey && n.id !== user15.id).forEach(keyNode => {
          if (Math.random() < 0.5) {
            addLink(user15.id, keyNode.id, 0.25, true);
          }
        });
      }
    }

    function simulate() {
      if (useApiLayout) {
        alpha *= 0.92;
        return;
      }
      if (alpha < 0.001) return;
      
      const width = canvas.width;
      const height = canvas.height;
      
      // Simulation parameters
      const clusterStrength = 0.08 * alpha;
      const repulsionStrength = 0.0015 * alpha;
      const linkStrength = 0.15 * alpha;
      const centerGravity = 0.01 * alpha;
      const damping = 0.4;
      
      // Reset forces
      nodes.forEach(node => {
        if (!node.fixed) {
          node.fx = 0;
          node.fy = 0;
        }
      });
      
      // Cluster attraction force
      nodes.forEach(node => {
        if (node.fixed) return;
        const center = clusterCenters[node.cluster];
        const dx = center.x - node.x;
        const dy = center.y - node.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const force = dist * clusterStrength * (node.isKey ? 0.5 : 1);
        node.fx += dx * force;
        node.fy += dy * force;
      });
      
      // Center gravity
      nodes.forEach(node => {
        if (node.fixed) return;
        const dx = 0.5 - node.x;
        const dy = 0.5 - node.y;
        node.fx += dx * centerGravity;
        node.fy += dy * centerGravity;
      });
      
      // Node-node repulsion (with spatial optimization)
      for (let i = 0; i < nodes.length; i++) {
        if (nodes[i].fixed) continue;
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let dist = Math.sqrt(dx * dx + dy * dy);
          
          if (dist < 0.001) {
            dx = (Math.random() - 0.5) * 0.01;
            dy = (Math.random() - 0.5) * 0.01;
            dist = 0.01;
          }
          
          // Stronger repulsion for same cluster
          const sameCluster = a.cluster === b.cluster;
          const minDist = sameCluster ? 0.04 : 0.08;
          
          if (dist < 0.3) {
            const force = repulsionStrength * (a.size + b.size) / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            
            if (!a.fixed) { a.fx += fx; a.fy += fy; }
            if (!b.fixed) { b.fx -= fx; b.fy -= fy; }
          }
        }
      }
      
      // Link attraction
      links.forEach(link => {
        const source = nodes[link.source];
        const target = nodes[link.target];
        
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.001;
        
        // Target distance based on link type
        const targetDist = link.isInterCluster ? 0.25 : 0.06;
        const force = (dist - targetDist) * linkStrength * link.strength;
        
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        
        if (!source.fixed) { source.fx += fx; source.fy += fy; }
        if (!target.fixed) { target.fx -= fx; target.fy -= fy; }
      });
      
      // Apply forces with velocity
      nodes.forEach(node => {
        if (node.fixed) return;
        
        node.vx = (node.vx + node.fx) * damping;
        node.vy = (node.vy + node.fy) * damping;
        
        // Limit velocity
        const speed = Math.sqrt(node.vx * node.vx + node.vy * node.vy);
        const maxSpeed = 0.02;
        if (speed > maxSpeed) {
          node.vx = (node.vx / speed) * maxSpeed;
          node.vy = (node.vy / speed) * maxSpeed;
        }
        
        node.x += node.vx;
        node.y += node.vy;
        
        // Boundary constraints
        node.x = Math.max(0.05, Math.min(0.95, node.x));
        node.y = Math.max(0.05, Math.min(0.95, node.y));
      });
      
      // Cool down
      alpha *= 0.995;
    }

    function drawCurvedLink(ctx, x1, y1, x2, y2, color1, color2, width, isInterCluster) {
      const dx = x2 - x1;
      const dy = y2 - y1;
      const dist = Math.sqrt(dx * dx + dy * dy);
      
      // Calculate perpendicular offset for curve
      const curvature = isInterCluster ? 0.15 : 0.08;
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;
      
      // Perpendicular vector
      const px = -dy / dist;
      const py = dx / dist;
      
      // Control point
      const offset = dist * curvature;
      const cx = mx + px * offset;
      const cy = my + py * offset;
      
      // Create gradient
      const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
      gradient.addColorStop(0, color1);
      gradient.addColorStop(1, color2);
      
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.quadraticCurveTo(cx, cy, x2, y2);
      ctx.strokeStyle = gradient;
      ctx.lineWidth = width;
      ctx.lineCap = 'round';
      ctx.stroke();
    }

    function canvasLogicalSize() {
      const dpr = window.devicePixelRatio || 1;
      return {
        width: canvas.width / dpr,
        height: canvas.height / dpr,
      };
    }

    function draw() {
      const { width, height } = canvasLogicalSize();
      const size = Math.min(width, height);
      
      // Clear with subtle gradient background
      ctx.fillStyle = '#fafbfc';
      ctx.fillRect(0, 0, width, height);
      
      ctx.save();
      ctx.translate(width / 2 + offsetX, height / 2 + offsetY);
      ctx.scale(scale, scale);
      ctx.translate(-width / 2, -height / 2);
      
      // Draw cluster backgrounds (subtle)
      clusterCenters.forEach((center, i) => {
        const x = center.x * width;
        const y = center.y * height;
        const radius = size * 0.12;
        
        const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius);
        gradient.addColorStop(0, center.color + '08');
        gradient.addColorStop(0.7, center.color + '04');
        gradient.addColorStop(1, center.color + '00');
        
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fillStyle = gradient;
        ctx.fill();
      });

      // Draw links - inter-cluster first (behind)
      links.filter(l => l.isInterCluster).forEach(link => {
        const source = nodes[link.source];
        const target = nodes[link.target];
        const sx = source.x * width;
        const sy = source.y * height;
        const tx = target.x * width;
        const ty = target.y * height;
        
        const c1 = riskColors[source.risk] + '30';
        const c2 = riskColors[target.risk] + '30';
        
        drawCurvedLink(ctx, sx, sy, tx, ty, c1, c2, 1.5, true);
      });
      
      // Draw intra-cluster links
      links.filter(l => !l.isInterCluster).forEach(link => {
        const source = nodes[link.source];
        const target = nodes[link.target];
        const sx = source.x * width;
        const sy = source.y * height;
        const tx = target.x * width;
        const ty = target.y * height;
        
        const c1 = riskColors[source.risk] + '25';
        const c2 = riskColors[target.risk] + '25';
        const lineWidth = 0.5 + link.strength * 1.5;
        
        drawCurvedLink(ctx, sx, sy, tx, ty, c1, c2, lineWidth, false);
      });

      // Draw nodes (regular first, then key nodes on top)
      const sortedNodes = [...nodes].sort((a, b) => {
        if (a.isKey !== b.isKey) return a.isKey ? 1 : -1;
        return a.importance - b.importance;
      });
      
      sortedNodes.forEach(node => {
        const x = node.x * width;
        const y = node.y * height;
        const color = riskColors[node.risk];
        const nodeSize = node.size * (size / 400);
        
        // Outer glow for high-risk or key nodes
        if (node.risk === 'high' || node.isKey) {
          const glowSize = nodeSize * (node.isKey ? 2.5 : 2);
          const glow = ctx.createRadialGradient(x, y, nodeSize * 0.5, x, y, glowSize);
          glow.addColorStop(0, color + '40');
          glow.addColorStop(0.5, color + '15');
          glow.addColorStop(1, color + '00');
          
          ctx.beginPath();
          ctx.arc(x, y, glowSize, 0, Math.PI * 2);
          ctx.fillStyle = glow;
          ctx.fill();
        }
        
        // Node body with gradient
        const nodeGradient = ctx.createRadialGradient(
          x - nodeSize * 0.3, y - nodeSize * 0.3, 0,
          x, y, nodeSize
        );
        nodeGradient.addColorStop(0, lightenColor(color, 30));
        nodeGradient.addColorStop(0.7, color);
        nodeGradient.addColorStop(1, darkenColor(color, 20));
        
        ctx.beginPath();
        ctx.arc(x, y, nodeSize, 0, Math.PI * 2);
        ctx.fillStyle = nodeGradient;
        ctx.fill();
        
        // White border
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
        ctx.lineWidth = node.isKey ? 2 : 1;
        ctx.stroke();
        
        if (node.apiId === selectedApiId) {
          ctx.strokeStyle = '#1d4ed8';
          ctx.lineWidth = node.isKey ? 3 : 2;
          ctx.stroke();
        }

        // Label for key nodes
        if (node.isKey && node.label && showLabels) {
          ctx.save();
          ctx.fillStyle = '#1f2937';
          ctx.font = `600 ${Math.max(9, 10 * scale)}px -apple-system, BlinkMacSystemFont, sans-serif`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'top';
          
          // Text shadow for readability
          ctx.shadowColor = 'rgba(255, 255, 255, 0.9)';
          ctx.shadowBlur = 3;
          ctx.fillText(node.label, x, y + nodeSize + 4);
          ctx.restore();
        }
      });

      ctx.restore();
    }
    
    function lightenColor(hex, percent) {
      const num = parseInt(hex.slice(1), 16);
      const r = Math.min(255, (num >> 16) + Math.round(2.55 * percent));
      const g = Math.min(255, ((num >> 8) & 0x00FF) + Math.round(2.55 * percent));
      const b = Math.min(255, (num & 0x0000FF) + Math.round(2.55 * percent));
      return `rgb(${r}, ${g}, ${b})`;
    }
    
    function darkenColor(hex, percent) {
      const num = parseInt(hex.slice(1), 16);
      const r = Math.max(0, (num >> 16) - Math.round(2.55 * percent));
      const g = Math.max(0, ((num >> 8) & 0x00FF) - Math.round(2.55 * percent));
      const b = Math.max(0, (num & 0x0000FF) - Math.round(2.55 * percent));
      return `rgb(${r}, ${g}, ${b})`;
    }

    function animate() {
      simulate();
      draw();
      animationId = requestAnimationFrame(animate);
    }

    function riskKey(risk) {
      const r = String(risk || '');
      if (r === 'High') return 'high';
      if (r === 'Medium') return 'medium';
      if (r === 'Low') return 'low';
      return 'unknown';
    }

    function loadFromPayload(payload) {
      if (!payload || !payload.nodes_data || !payload.nodes_data.length) {
        initGraph();
        return;
      }
      cancelAnimationFrame(animationId);
      const nd = payload.nodes_data;
      const ed = payload.edges_data || [];
      const clusters = payload.clusters || [];
      clusters.forEach((c, i) => {
        if (clusterCenters[i]) {
          clusterCenters[i].color = c.color || clusterCenters[i].color;
        }
      });
      const clusterIndex = {};
      clusters.forEach((c, i) => {
        clusterIndex[c.name] = i % clusterCenters.length;
      });
      const topIds = new Set((payload.top_nodes || []).map((n) => n.id));
      nodes = nd.map((n, i) => {
        const ci =
          clusterIndex[n.cluster] != null ? clusterIndex[n.cluster] : i % clusterCenters.length;
        const imp = (Number(n.risk_score) || 0) / 100;
        const isKey = topIds.has(n.id) || n.viz_spotlight || n.show_label;
        let x = Number(n.x_norm);
        let y = Number(n.y_norm);
        if (!Number.isFinite(x) || !Number.isFinite(y)) {
          const center = clusterCenters[ci];
          x = center.x + (Math.random() - 0.5) * 0.12;
          y = center.y + (Math.random() - 0.5) * 0.12;
        }
        return {
          id: i,
          apiId: n.id,
          label: isKey ? String(n.name) : '',
          x: Math.max(0.05, Math.min(0.95, x)),
          y: Math.max(0.05, Math.min(0.95, y)),
          vx: 0,
          vy: 0,
          cluster: ci,
          risk: riskKey(n.risk),
          importance: Math.max(0.15, imp),
          size: isKey ? 8 + imp * 8 : 2.5 + imp * 3,
          isKey,
          fixed: true,
        };
      });
      const idToIdx = new Map(nodes.map((nn) => [nn.apiId, nn.id]));
      links = [];
      const linkSet = new Set();
      ed.forEach((e) => {
        const s = idToIdx.get(e.source);
        const t = idToIdx.get(e.target);
        if (s == null || t == null) return;
        const key = s < t ? `${s}-${t}` : `${t}-${s}`;
        if (linkSet.has(key)) return;
        linkSet.add(key);
        const ns = nodes[s];
        const nt = nodes[t];
        links.push({
          source: s,
          target: t,
          strength: 0.25 + Math.random() * 0.2,
          isInterCluster: ns.cluster !== nt.cluster,
        });
      });
      useApiLayout = true;
      alpha = 0.015;
      scale = 1;
      offsetX = 0;
      offsetY = 0;
      resizeCanvas();
      animate();
    }

    function selectNodeById(apiId) {
      selectedApiId = apiId;
    }

    function setShowLabels(on) {
      showLabels = !!on;
    }

    function setOnNodeSelect(fn) {
      onNodeSelect = typeof fn === 'function' ? fn : null;
    }

    function initGraph() {
      cancelAnimationFrame(animationId);
      useApiLayout = false;
      alpha = 1;
      scale = 1;
      offsetX = 0;
      offsetY = 0;
      generateNodes();
      generateLinks();
      animate();
    }

    function resizeCanvas() {
      const container = canvas.parentElement;
      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth;
      const h = container.clientHeight;
      canvas.width = Math.max(1, w * dpr);
      canvas.height = Math.max(1, h * dpr);
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw();
    }

    function zoomIn() {
      scale = Math.min(scale * 1.25, 4);
      draw();
    }

    function zoomOut() {
      scale = Math.max(scale / 1.25, 0.4);
      draw();
    }

    function getNodeAtPosition(mx, my) {
      const width = canvas.width / (window.devicePixelRatio || 1);
      const height = canvas.height / (window.devicePixelRatio || 1);
      
      const x = (mx - width / 2 - offsetX) / scale + width / 2;
      const y = (my - height / 2 - offsetY) / scale + height / 2;
      
      for (let i = nodes.length - 1; i >= 0; i--) {
        const node = nodes[i];
        const nx = node.x * width;
        const ny = node.y * height;
        const dist = Math.sqrt((x - nx) ** 2 + (y - ny) ** 2);
        if (dist < node.size * 2) {
          return node;
        }
      }
      return null;
    }

    // Mouse interactions
    canvas.addEventListener('mousedown', (e) => {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      
      dragNode = getNodeAtPosition(mx, my);
      if (dragNode) {
        dragNode.fixed = true;
        alpha = Math.max(alpha, 0.3);
      } else {
        isDragging = true;
      }
      lastX = e.clientX;
      lastY = e.clientY;
    });

    canvas.addEventListener('mousemove', (e) => {
      const rect = canvas.getBoundingClientRect();
      
      if (dragNode) {
        const width = canvas.width / (window.devicePixelRatio || 1);
        const height = canvas.height / (window.devicePixelRatio || 1);
        
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        
        const x = (mx - width / 2 - offsetX) / scale + width / 2;
        const y = (my - height / 2 - offsetY) / scale + height / 2;
        
        dragNode.x = x / width;
        dragNode.y = y / height;
        alpha = Math.max(alpha, 0.1);
      } else if (isDragging) {
        offsetX += e.clientX - lastX;
        offsetY += e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
      }
      
      // Cursor style
      const node = getNodeAtPosition(e.clientX - rect.left, e.clientY - rect.top);
      canvas.style.cursor = node ? 'grab' : (isDragging ? 'grabbing' : 'default');
    });

    canvas.addEventListener('mouseup', (e) => {
      if (dragNode) {
        const moved = Math.abs(e.clientX - lastX) + Math.abs(e.clientY - lastY);
        if (moved < 6 && dragNode.apiId != null && onNodeSelect) {
          onNodeSelect(dragNode.apiId);
        }
        if (!useApiLayout) dragNode.fixed = false;
        dragNode = null;
      }
      isDragging = false;
    });
    
    canvas.addEventListener('mouseleave', () => {
      if (dragNode) {
        dragNode.fixed = false;
        dragNode = null;
      }
      isDragging = false;
    });

    canvas.addEventListener('wheel', (e) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.4, Math.min(4, scale * delta));
      
      // Zoom toward mouse position
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left - canvas.width / 2 / (window.devicePixelRatio || 1);
      const my = e.clientY - rect.top - canvas.height / 2 / (window.devicePixelRatio || 1);
      
      offsetX = mx - (mx - offsetX) * (newScale / scale);
      offsetY = my - (my - offsetY) * (newScale / scale);
      scale = newScale;
    });

    window.addEventListener('resize', resizeCanvas);

    resizeCanvas();

  global.MauGraph = {
    initGraph,
    zoomIn,
    zoomOut,
    loadFromPayload,
    selectNodeById,
    setShowLabels,
    setOnNodeSelect,
    getNodes: () => nodes,
  };
})(typeof window !== 'undefined' ? window : global);
