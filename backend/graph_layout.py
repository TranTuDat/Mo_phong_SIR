"""
Layout an toàn cho NetworkX: spring_layout cần SciPy; nếu lỗi thì dùng circular_layout.
Dùng chung cho app (dashboard) và Tao_nguoi_dung_va_do_thi (xuất PNG).

dashboard_spring_layout: spring toàn đồ thị — cụm tách tự nhiên như dashboard phân tích mạng.

cluster_focus_layout: đặt từng cộng đồng trong ô lưới (giữ lại cho tùy chọn / PNG).
"""
import logging
import math
from typing import Any, Dict, Iterable, Optional, Set

import networkx as nx

logger = logging.getLogger(__name__)


def _repel_overlaps(
    pos: Dict[int, tuple[float, float]],
    *,
    passes: int,
    min_dist_factor: float = 1.0,
) -> Dict[int, tuple[float, float]]:
    """
    Đẩy các cặp nút quá gần nhau — giảm blob / chồng kín (kiểu post-process sau spring).
    Tọa độ cùng hệ với pos đầu vào (đã căn tâm).
    """
    keys = list(pos.keys())
    if len(keys) < 2:
        return pos
    arr = {k: [float(pos[k][0]), float(pos[k][1])] for k in keys}

    xs = [arr[k][0] for k in keys]
    ys = [arr[k][1] for k in keys]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    n = len(keys)
    min_dist = span * max(0.052, 5.6 / math.sqrt(n)) * max(0.9, min_dist_factor)

    for _ in range(max(1, passes)):
        for i, u in enumerate(keys):
            for v in keys[i + 1 :]:
                dx = arr[v][0] - arr[u][0]
                dy = arr[v][1] - arr[u][1]
                d = math.hypot(dx, dy) + 1e-9
                if d < min_dist:
                    push = (min_dist - d) * 0.78
                    ux, uy = dx / d, dy / d
                    arr[u][0] -= ux * push
                    arr[u][1] -= uy * push
                    arr[v][0] += ux * push
                    arr[v][1] += uy * push

    return {k: (arr[k][0], arr[k][1]) for k in keys}


def _normalize_positions(
    pos: Dict[int, tuple[float, float]], *, margin: float = 0.1
) -> Dict[int, tuple[float, float]]:
    """Căn giữa và scale vào [-1+margin, 1-margin]²."""
    if not pos:
        return pos
    keys = list(pos.keys())
    xs = [pos[k][0] for k in keys]
    ys = [pos[k][1] for k in keys]
    midx = (min(xs) + max(xs)) / 2.0
    midy = (min(ys) + max(ys)) / 2.0
    w = max(max(xs) - min(xs), 1e-9)
    h = max(max(ys) - min(ys), 1e-9)
    s = min(2.0 * (1.0 - margin) / w, 2.0 * (1.0 - margin) / h)
    return {k: ((pos[k][0] - midx) * s, (pos[k][1] - midy) * s) for k in keys}


def polish_representative_layout(
    graph: nx.Graph,
    pos: Dict[int, tuple[float, float]],
    *,
    iterations: int = 52,
    edge_ideal_frac: float = 0.11,
    min_sep_factor: float = 7.2,
    inter_edge_keys: Optional[Set[tuple[int, int]]] = None,
) -> Dict[int, tuple[float, float]]:
    """
    Tách nút (không chồng), đồng thời rút ngắn cạnh giữa các nút có quan hệ — bố cục thoáng, tự nhiên.
    """
    keys = [int(k) for k in pos]
    n = len(keys)
    if n < 2:
        return pos

    arr = {k: [float(pos[k][0]), float(pos[k][1])] for k in keys}
    edges = [
        (int(u), int(v))
        for u, v in graph.edges()
        if int(u) in arr and int(v) in arr
    ]

    def current_span() -> float:
        xs = [arr[k][0] for k in keys]
        ys = [arr[k][1] for k in keys]
        return max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)

    for step in range(max(8, iterations)):
        span = current_span()
        min_sep = span * max(0.07, 7.0 / math.sqrt(n)) * (min_sep_factor / 7.2)
        ideal = span * edge_ideal_frac
        repel_k = 0.55 + 0.2 * (step / max(iterations - 1, 1))
        attract_k = 0.18 + 0.14 * (step / max(iterations - 1, 1))

        for i, u in enumerate(keys):
            for v in keys[i + 1 :]:
                dx = arr[v][0] - arr[u][0]
                dy = arr[v][1] - arr[u][1]
                d = math.hypot(dx, dy) + 1e-9
                if d < min_sep:
                    push = (min_sep - d) * repel_k
                    ux, uy = dx / d, dy / d
                    arr[u][0] -= ux * push
                    arr[u][1] -= uy * push
                    arr[v][0] += ux * push
                    arr[v][1] += uy * push

        inter_keys = inter_edge_keys or set()
        for u, v in edges:
            dx = arr[v][0] - arr[u][0]
            dy = arr[v][1] - arr[u][1]
            d = math.hypot(dx, dy) + 1e-9
            is_inter = (u, v) in inter_keys
            local_ideal = ideal
            if d > ideal * 2.4:
                local_ideal = ideal * 1.12
            if is_inter:
                local_ideal *= 0.92
            if d > local_ideal * 1.06:
                pull = (d - local_ideal) * attract_k
                if d > ideal * 1.85:
                    pull *= 1.18
                if is_inter:
                    pull *= 1.32
                ux, uy = dx / d, dy / d
                arr[u][0] += ux * pull
                arr[u][1] += uy * pull
                arr[v][0] -= ux * pull
                arr[v][1] -= uy * pull
            elif d < ideal * 0.55:
                push = (ideal * 0.55 - d) * 0.12
                ux, uy = dx / d, dy / d
                arr[u][0] -= ux * push
                arr[u][1] -= uy * push
                arr[v][0] += ux * push
                arr[v][1] += uy * push

    out = {k: (arr[k][0], arr[k][1]) for k in keys}
    return _normalize_positions(out, margin=0.08)


def _repel_overlaps_fixed(
    pos: Dict[int, tuple[float, float]],
    fixed: Set[int],
    *,
    passes: int,
    min_dist_factor: float = 1.0,
) -> Dict[int, tuple[float, float]]:
    """Đẩy chồng lấn nhưng giữ nút trong `fixed` (thường là hub) không đổi vị trí."""
    fixed = {int(x) for x in fixed}
    keys = [k for k in pos if int(k) not in fixed]
    if len(keys) < 2:
        return pos
    arr = {k: [float(pos[k][0]), float(pos[k][1])] for k in pos}
    all_keys = list(pos.keys())

    xs = [arr[k][0] for k in all_keys]
    ys = [arr[k][1] for k in all_keys]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-6)
    n = len(all_keys)
    min_dist = span * max(0.058, 6.2 / math.sqrt(max(n, 2))) * max(0.95, min_dist_factor)

    for _ in range(max(1, passes)):
        for i, u in enumerate(all_keys):
            for v in all_keys[i + 1 :]:
                dx = arr[v][0] - arr[u][0]
                dy = arr[v][1] - arr[u][1]
                d = math.hypot(dx, dy) + 1e-9
                if d >= min_dist:
                    continue
                push = (min_dist - d) * 0.82
                ux, uy = dx / d, dy / d
                if int(u) not in fixed:
                    arr[u][0] -= ux * push
                    arr[u][1] -= uy * push
                if int(v) not in fixed:
                    arr[v][0] += ux * push
                    arr[v][1] += uy * push

    return {k: (arr[k][0], arr[k][1]) for k in pos}


def _radial_hub_layout(
    sub: nx.Graph,
    hub: int,
    cx: float,
    cy: float,
    max_radius: float,
    *,
    seed: int,
) -> Dict[Any, tuple[float, float]]:
    """Vệ tinh bố trí vòng tròn quanh hub — tránh khối dính khi cụm ít nút."""
    nodes = list(sub.nodes())
    hub = int(hub)
    out: Dict[Any, tuple[float, float]] = {hub: (cx, cy)}
    others = sorted((int(v) for v in nodes if int(v) != hub), key=lambda x: sub.degree(x), reverse=True)
    if not others:
        return out

    golden = 2.399963229728653
    per_ring = 5
    for i, v in enumerate(others):
        ring = i // per_ring
        idx = i % per_ring
        count_ring = min(per_ring, len(others) - ring * per_ring)
        angle = (seed % 97) * 0.04 + ring * 0.65 + idx * (2.0 * math.pi / max(count_ring, 1))
        angle += i * golden * 0.18
        r_frac = 0.48 + ring * 0.24 + (idx % 2) * 0.06
        r = max_radius * min(0.98, r_frac)
        out[v] = (cx + r * math.cos(angle), cy + r * math.sin(angle))

    return _repel_overlaps_fixed(out, {hub}, passes=36, min_dist_factor=2.4)


def spring_or_circular(
    graph: nx.Graph,
    *,
    seed: int = 42,
    iterations: int = 50,
    k: Optional[float] = None,
) -> Any:
    n = graph.number_of_nodes()
    if n == 0:
        return {}
    # Cho phép caller (dashboard) dùng iteration cao; tránh trần quá lớn trên đồ thị khổng lồ
    it = max(10, min(int(iterations), 400))
    try:
        kwargs: dict[str, Any] = {'seed': seed, 'iterations': it}
        if k is not None:
            kwargs['k'] = k
        return nx.spring_layout(graph, **kwargs)
    except Exception as exc:
        logger.warning('spring_layout failed (%s); using circular_layout', exc)
        return nx.circular_layout(graph)


def dashboard_spring_layout(
    graph: nx.Graph,
    *,
    center_nodes: Optional[Iterable[Any]] = None,
    seed: int = 42,
) -> Dict[Any, tuple[float, float]]:
    """
    Spring layout toàn đồ thị với k lớn (lực đẩy mạnh, gần tinh thần ForceAtlas2),
    sau đó tách chồng lấn và chuẩn hóa vào [-1,1]² với margin rộng.
    Không kéo cụm về một điểm — tránh blob ở giữa canvas.
    """
    _ = center_nodes  # giữ tham số API; hub nổi bật bằng bán kính ở client, không nén layout
    n = graph.number_of_nodes()
    if n == 0:
        return {}
    if n == 1:
        nid = int(next(iter(graph.nodes())))
        return {nid: (0.0, 0.0)}

    # k lớn → nút xa nhau hơn; iteration cao → ổn định, ít cụm tròn dày
    it = min(320, max(90, int(55 * math.sqrt(n))))
    k = max(0.42, 9.5 / math.sqrt(n)) if n > 1 else None
    raw = spring_or_circular(graph, seed=seed, iterations=it, k=k)
    pos = {int(v): (float(raw[v][0]), float(raw[v][1])) for v in raw}

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    midx = (min(xs) + max(xs)) / 2.0
    midy = (min(ys) + max(ys)) / 2.0
    pos = {v: (x - midx, y - midy) for v, (x, y) in pos.items()}

    rep_passes = min(32, max(14, 8000 // max(n, 1)))
    pos = _repel_overlaps(pos, passes=rep_passes, min_dist_factor=1.35)

    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    w = max(max(xs) - min(xs), 1e-9)
    h = max(max(ys) - min(ys), 1e-9)
    margin = 0.18
    s = min(2.0 * (1.0 - margin) / w, 2.0 * (1.0 - margin) / h)
    return {v: (p[0] * s, p[1] * s) for v, p in pos.items()}


def _layout_community_organic(
    sub: nx.Graph,
    cx: float,
    cy: float,
    max_radius: float,
    hub_nodes: Set[Any],
    *,
    seed: int,
) -> Dict[Any, tuple[float, float]]:
    """
    Spring nội cụm với k lớn + đẩy chồng lấn; hub ở tâm, vệ tinh lan tỏa (tránh khối tròn dày).
    """
    nodes = list(sub.nodes())
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: (cx, cy)}

    comm_hubs = [v for v in nodes if v in hub_nodes]
    if comm_hubs:
        hub = max(comm_hubs, key=lambda v: sub.degree(v))
    else:
        hub = max(nodes, key=lambda v: sub.degree(v))
    hub = int(hub)

    if n <= 18:
        out = _radial_hub_layout(sub, hub, cx, cy, max_radius, seed=seed)
        return out

    k_spread = max(3.5, 8.5 / math.sqrt(max(n, 2)))
    iters = min(180, max(80, 26 * n))
    raw = spring_or_circular(sub, seed=seed, iterations=iters, k=k_spread)
    pos_local: Dict[int, tuple[float, float]] = {
        int(v): (float(raw[v][0]), float(raw[v][1])) for v in raw
    }

    hx, hy = pos_local.get(hub, (0.0, 0.0))
    pos_local = {v: (x - hx, y - hy) for v, (x, y) in pos_local.items()}

    rep_passes = min(56, max(28, 14 + n * 3))
    pos_local = _repel_overlaps(pos_local, passes=rep_passes, min_dist_factor=2.85)

    xs = [p[0] for p in pos_local.values()]
    ys = [p[1] for p in pos_local.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys), 1e-9)
    target = max_radius * 1.28
    scale = target / span

    out: Dict[Any, tuple[float, float]] = {}
    for v, (x, y) in pos_local.items():
        if int(v) == hub:
            out[v] = (cx, cy)
            continue
        r0 = math.hypot(x, y)
        if r0 < 1e-9:
            ang = ((int(v) * 0.6180339887) % 1.0) * 2.0 * math.pi
            r1 = max_radius * 0.58
            x = math.cos(ang) * r1
            y = math.sin(ang) * r1
        else:
            r1 = min(r0 * scale, max_radius * 0.99)
            x = x / r0 * r1
            y = y / r0 * r1
        out[v] = (cx + x, cy + y)

    return _repel_overlaps_fixed(out, {hub}, passes=40, min_dist_factor=3.2)


def cluster_focus_layout(
    graph: nx.Graph,
    communities: Iterable[Set[Any]],
    hub_nodes: Set[Any],
    *,
    seed: int = 42,
) -> Dict[Any, tuple[float, float]]:
    """
    Mỗi cụm (community) nằm trong một ô lưới; spring nội bộ trong subgraph;
    các nút trong hub_nodes được kéo về gần tâm cụm để nổi bật.
    Tọa độ trả về gần trong [-1, 1]² (sẽ được map pixel ở app).
    """
    comms = sorted([set(c) for c in communities if len(c) > 0], key=lambda s: (-len(s), min(s)))
    n = graph.number_of_nodes()
    if n == 0:
        return {}
    if len(comms) <= 1:
        return spring_or_circular(graph, seed=seed, iterations=80)

    K = len(comms)
    cols = int(math.ceil(math.sqrt(K)))
    rows = int(math.ceil(K / cols))
    grid_pad = 0.16
    span = 2.0 - 2.0 * grid_pad
    cell_w = span / cols
    cell_h = span / rows
    max_local_radius = 0.22 * min(cell_w, cell_h)
    hubs_set = {int(h) for h in hub_nodes}

    positions: Dict[Any, tuple[float, float]] = {}

    for idx, comm in enumerate(comms):
        row, col = divmod(idx, cols)
        cx = -1.0 + grid_pad + cell_w * (col + 0.5)
        cy = -1.0 + grid_pad + cell_h * (row + 0.5)

        sub = graph.subgraph(comm).copy()
        if sub.number_of_nodes() == 0:
            continue
        if sub.number_of_nodes() == 1:
            nid = next(iter(comm))
            positions[nid] = (cx, cy)
            continue

        local_pos = _layout_community_organic(
            sub,
            cx,
            cy,
            max_local_radius,
            hubs_set,
            seed=seed + idx * 17,
        )
        positions.update(local_pos)

    for v in graph.nodes():
        if v not in positions:
            positions[v] = (0.0, 0.0)

    xs_all = [positions[v][0] for v in positions]
    ys_all = [positions[v][1] for v in positions]
    minx, maxx = min(xs_all), max(xs_all)
    miny, maxy = min(ys_all), max(ys_all)
    w = max(maxx - minx, 1e-9)
    h = max(maxy - miny, 1e-9)
    margin = 0.08
    s = min(2.0 * (1.0 - margin) / w, 2.0 * (1.0 - margin) / h)
    midx = (minx + maxx) / 2.0
    midy = (miny + maxy) / 2.0
    scaled = {v: ((positions[v][0] - midx) * s, (positions[v][1] - midy) * s) for v in positions}
    return scaled
