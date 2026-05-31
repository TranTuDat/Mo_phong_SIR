"""Tính chỉ số trung tâm & chọn nguồn phát thông tin xấu (ban đầu) cho mô phỏng SIR."""
from __future__ import annotations

import random
from typing import Iterable

import networkx as nx

from .deploy_env import betweenness_sample_k

CENTRALITY_STRATEGIES = frozenset({'betweenness', 'degree', 'eigenvector', 'pagerank'})
DYNAMIC_INTERVENTION_STRATEGIES = frozenset({'random', *CENTRALITY_STRATEGIES})
MISINFO_SOURCE_MODES = frozenset({'random', *CENTRALITY_STRATEGIES})

# Với nguồn theo chỉ số: không cố định nút #1 (dễ trùng giữa các mode) — chọn ngẫu nhiên trong top-K.
MISINFO_TOP_POOL_SIZE = 10


def normalize_strategy(strategy: str) -> str:
    s = (strategy or 'betweenness').strip().lower()
    if s not in CENTRALITY_STRATEGIES:
        raise ValueError(
            f'strategy phải là một trong: {", ".join(sorted(CENTRALITY_STRATEGIES))}'
        )
    return s


def normalize_dynamic_strategy(strategy: str) -> str:
    s = (strategy or 'betweenness').strip().lower()
    if s not in DYNAMIC_INTERVENTION_STRATEGIES:
        raise ValueError(
            f'strategy phải là một trong: {", ".join(sorted(DYNAMIC_INTERVENTION_STRATEGIES))}'
        )
    return s


def normalize_misinfo_mode(mode: str) -> str:
    m = (mode or 'random').strip().lower()
    if m not in MISINFO_SOURCE_MODES:
        raise ValueError(
            f'misinfo_source_mode phải là một trong: {", ".join(sorted(MISINFO_SOURCE_MODES))}'
        )
    return m


def compute_centrality_scores(graph: nx.Graph, strategy: str) -> dict[int, float]:
    """Điểm trung tâm theo chiến lược (cao = quan trọng hơn)."""
    strategy = normalize_strategy(strategy)
    n = graph.number_of_nodes()
    if n == 0:
        return {}

    if strategy == 'degree':
        return {int(node): float(deg) for node, deg in graph.degree()}

    if strategy == 'eigenvector':
        try:
            ev = nx.eigenvector_centrality(graph, max_iter=1000)
            return {int(node): float(v) for node, v in ev.items()}
        except Exception:
            return {int(node): float(deg) for node, deg in graph.degree()}

    if strategy == 'pagerank':
        try:
            pr = nx.pagerank(graph, alpha=0.85, max_iter=200, tol=1e-06)
            return {int(node): float(v) for node, v in pr.items()}
        except Exception:
            return {int(node): float(deg) for node, deg in graph.degree()}

    k_bet = betweenness_sample_k(n)
    if k_bet is None:
        bet = nx.betweenness_centrality(graph)
    else:
        bet = nx.betweenness_centrality(graph, k=k_bet)
    return {int(node): float(v) for node, v in bet.items()}


def pick_top_nodes_by_score(
    graph: nx.Graph,
    mode: str,
    count: int,
    *,
    seed: int = 42,
) -> list[int]:
    """Chọn ``count`` nút — random hoặc theo chỉ số cao nhất."""
    count = max(1, int(count))
    nodes = [int(n) for n in graph.nodes()]
    if not nodes:
        return []
    if count >= len(nodes):
        return nodes

    mode = normalize_misinfo_mode(mode)
    rng = random.Random(seed)

    if mode == 'random':
        return [int(x) for x in rng.sample(nodes, count)]

    scores = compute_centrality_scores(graph, mode)
    ranked = sorted(
        ((int(nid), float(scores.get(int(nid), 0))) for nid in nodes),
        key=lambda kv: (kv[1], -kv[0]),
        reverse=True,
    )
    pool_k = min(MISINFO_TOP_POOL_SIZE, len(ranked))
    pool = [nid for nid, _ in ranked[:pool_k]]
    if count <= len(pool):
        return [int(x) for x in rng.sample(pool, count)]
    # count lớn hơn pool: lấy hết pool rồi bổ sung từ phần còn lại của bảng xếp hạng
    chosen = list(rng.sample(pool, len(pool)))
    rest_ids = [nid for nid, _ in ranked[pool_k:] if nid not in chosen]
    need = count - len(chosen)
    if need > 0 and rest_ids:
        take = min(need, len(rest_ids))
        chosen.extend(int(x) for x in rng.sample(rest_ids, take))
    return chosen[:count]


def misinfo_source_labels(
    node_ids: Iterable[int],
    users_df,
    *,
    id_col: str = 'user_id',
    name_col: str = 'name',
) -> list[dict]:
    """{id, name} cho hiển thị API."""
    ids = [int(x) for x in node_ids]
    if users_df is None or users_df.empty:
        return [{'id': nid, 'name': str(nid)} for nid in ids]
    u = users_df.copy()
    if id_col not in u.columns and 'id' in u.columns:
        id_col = 'id'
    if name_col not in u.columns:
        name_col = id_col
    name_map = {
        int(row[id_col]): str(row.get(name_col, row[id_col]))
        for _, row in u.iterrows()
    }
    return [{'id': nid, 'name': name_map.get(nid, str(nid))} for nid in ids]
