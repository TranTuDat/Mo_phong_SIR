"""Cờ môi trường: Render (nhẹ, không PNG) vs local (đầy đủ trực quan)."""
from __future__ import annotations

import math
import os


def on_render_deploy() -> bool:
    return bool(os.getenv('RENDER') or os.getenv('RENDER_SERVICE_ID'))


def skip_heavy_viz() -> bool:
    """True → không matplotlib PNG / ma trận kề nặng (Render hoặc MO_PHONG_SKIP_VIZ=1)."""
    if os.getenv('MO_PHONG_SKIP_VIZ', '').strip().lower() in ('1', 'true', 'yes'):
        return True
    return on_render_deploy()


def max_users_limit() -> int:
    on_render = on_render_deploy()
    default = '5000' if on_render else '10000'
    return int(os.getenv('MO_PHONG_MAX_USERS', default))


def use_fast_graph_algorithms(n_nodes: int) -> bool:
    """Trên server hoặc mạng lớn: centrality xấp xỉ, bỏ phân cụm nặng."""
    if skip_heavy_viz():
        return True
    return n_nodes > 2000


def betweenness_sample_k(n_nodes: int) -> int | None:
    """None = betweenness đầy đủ; int = tham số k của NetworkX (xấp xỉ)."""
    if n_nodes <= 800:
        return None
    return min(500, max(100, int(math.sqrt(n_nodes))))
