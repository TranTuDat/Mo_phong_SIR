"""
Vẽ đồ thị mạng kiểu Test.py: node nhỏ, cạnh mảnh — phù hợp mạng lớn (hàng nghìn nút).
Dùng cho graph_visualization.png và demo Test.py.
"""
from __future__ import annotations

import math
from typing import Any, Optional

import matplotlib.axes
import networkx as nx

from .graph_layout import spring_or_circular

# Tham số gốc từ Test.py (n=2500, m=6 BA demo)
_TEST_BASE_N = 2500
_TEST_NODE_SIZE = 5
_TEST_EDGE_WIDTH = 0.1


def test_style_draw_kwargs(n_nodes: int) -> dict[str, Any]:
    """
    Co giãn node_size / width theo số nút (giữ tỉ lệ như Test.py với n≈2500).
    """
    scale = max(1.0, n_nodes / _TEST_BASE_N)
    node_size = max(1.5, _TEST_NODE_SIZE / math.sqrt(scale))
    width = max(0.05, _TEST_EDGE_WIDTH / math.sqrt(scale))
    alpha = 0.35 if n_nodes >= 2000 else (0.45 if n_nodes >= 800 else 0.6)
    return {
        'node_size': node_size,
        'width': width,
        'with_labels': False,
        'alpha': alpha,
    }


def layout_for_network_draw(G: nx.Graph, *, seed: int = 42) -> dict:
    """Bố trí nút: mạng lớn dùng ít vòng spring (nhanh hơn)."""
    n = G.number_of_nodes()
    if n >= 1500:
        return nx.spring_layout(G, seed=seed, iterations=12, dim=2)
    if n >= 400:
        k = 2.0 / math.sqrt(max(n, 1))
        return spring_or_circular(G, seed=seed, iterations=25, k=k)
    return spring_or_circular(G, seed=seed, iterations=50, k=0.5)


def draw_network_test_style(
    G: nx.Graph,
    ax: matplotlib.axes.Axes,
    *,
    seed: int = 42,
    node_color: str = '#60a5fa',
    edge_color: str = '#94a3b8',
    use_degree_sizes: bool = False,
    metrics_degree: Optional[dict] = None,
) -> None:
    """
    Vẽ đồ thị lên axes (giống Test.py: nx.draw, không nhãn).

    use_degree_sizes: True chỉ khi n <= 300 — kích thước nút theo degree.
    """
    n = G.number_of_nodes()
    if n == 0:
        ax.text(0.5, 0.5, 'Không có nút', ha='center', va='center', transform=ax.transAxes)
        ax.axis('off')
        return

    kw = test_style_draw_kwargs(n)
    pos = layout_for_network_draw(G, seed=seed)

    if use_degree_sizes and n <= 300:
        degree = metrics_degree if metrics_degree is not None else dict(G.degree())
        base = kw['node_size']
        sizes = [max(base, float(degree.get(node, 1)) * base * 2.5) for node in G.nodes()]
        nx.draw_networkx_nodes(
            G, pos, ax=ax, node_size=sizes, node_color=node_color,
            edgecolors='#1e40af', linewidths=0.3, alpha=kw.get('alpha', 0.6),
        )
        nx.draw_networkx_edges(
            G, pos, ax=ax, width=kw['width'], edge_color=edge_color, alpha=kw.get('alpha', 0.6),
        )
    else:
        nx.draw(
            G,
            pos,
            ax=ax,
            node_size=kw['node_size'],
            width=kw['width'],
            with_labels=kw['with_labels'],
            node_color=node_color,
            edge_color=edge_color,
            alpha=kw.get('alpha', 0.5),
        )

    ax.axis('off')


def barabasi_albert_attachment_count(num_users: int, target_mean_degree: float = 6.0) -> int:
    """m cho BA — số cạnh gắn mỗi nút mới (Test.py dùng m=6 với n=2500)."""
    return max(1, int(round(target_mean_degree / 2)))


def test_style_canvas_radius(n_nodes: int) -> float:
    """Bán kính nút trên canvas web (px) — đồng bộ với node_size matplotlib Test.py."""
    kw = test_style_draw_kwargs(n_nodes)
    return max(1.5, min(4.0, float(kw['node_size']) * 0.42))


def normalize_positions_to_unit(positions: dict[int, tuple[float, float]]) -> dict[int, tuple[float, float]]:
    """Chuẩn hóa tọa độ layout về [-1, 1]² cho x_norm/y_norm trên web."""
    if not positions:
        return positions
    xs = [p[0] for p in positions.values()]
    ys = [p[1] for p in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span = max(max_x - min_x, max_y - min_y, 1e-6)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    scale = 1.85 / span
    return {
        int(nid): ((px - cx) * scale, (py - cy) * scale)
        for nid, (px, py) in positions.items()
    }
