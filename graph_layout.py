"""
Layout an toàn cho NetworkX: spring_layout cần SciPy; nếu lỗi thì dùng circular_layout.
Dùng chung cho app (dashboard) và Tao_nguoi_dung_va_do_thi (xuất PNG).
"""
import logging
from typing import Any, Optional

import networkx as nx

logger = logging.getLogger(__name__)


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
    it = min(iterations, max(10, 8000 // n))
    try:
        kwargs: dict[str, Any] = {'seed': seed, 'iterations': it}
        if k is not None:
            kwargs['k'] = k
        return nx.spring_layout(graph, **kwargs)
    except Exception as exc:
        logger.warning('spring_layout failed (%s); using circular_layout', exc)
        return nx.circular_layout(graph)
