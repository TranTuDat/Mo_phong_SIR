import os

os.environ.setdefault('MPLBACKEND', 'Agg')

from flask import Flask, jsonify, request, send_from_directory, send_file, abort
from io import BytesIO
from pathlib import Path
from typing import Optional, Set, Tuple
import pandas as pd
import networkx as nx
import numpy as np
import json
import datetime
import logging
import tempfile
import shutil
import heapq
import math
import random
import re

from .deploy_env import max_users_limit, on_render_deploy, skip_heavy_viz, use_fast_graph_algorithms
from .Tao_nguoi_dung_va_do_thi import SocialNetworkGenerator, OUTPUT_ROOT
from .sir_models import PureSIRSimulation, SIRDynamicImmunization, epidemic_final_day_from_history
from .centrality_scores import (
    DYNAMIC_INTERVENTION_STRATEGIES,
    misinfo_source_labels,
    normalize_misinfo_mode,
)
from .sir_pdf_report import build_sir_comparison_pdf_bytes
from .sir_sim_paths import (
    clear_dataset_sir_results,
    clear_orphan_legacy_sir_dirs,
    find_dynamic_sir_history_csv,
    find_pure_sir_history_csv,
    list_saved_dynamic_sir_runs,
    list_saved_pure_sir_runs,
    read_immunized_node_ids,
)
from .graph_draw import layout_for_network_draw, normalize_positions_to_unit, test_style_canvas_radius
from .graph_layout import (
    _repel_overlaps,
    cluster_focus_layout,
    dashboard_spring_layout,
    polish_representative_layout,
    spring_or_circular,
)
from .upload_data import (
    allowed_upload_filename,
    detect_upload_kind,
    prepare_edges_upload,
    read_upload_table,
)

_DATASET_DIR_TS_RE = re.compile(r'_(\d{8})_(\d{6})$')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _json_safe(value):
    """Chuyển numpy/pandas sang kiểu JSON thuần (tránh 500 khi jsonify trên Render)."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime.datetime, datetime.date)):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    return value


def json_safe_response(data, status=200):
    return jsonify(_json_safe(data)), status


BASE_DIR = Path(__file__).resolve().parent.parent
HTML_DIR = BASE_DIR / 'html'
OUTPUTS_DIR = BASE_DIR / 'outputs'
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path='')

RISK_COLORS = {
    'High': '#d94a4a',
    'Medium': '#e8924a',
    'Low': '#4b80c9',
    'Unknown': '#c8cdd6',
}
# Màu cụm — bảng tương phản cao, dễ phân biệt trên nền sáng/tối
CLUSTER_COLORS = [
    '#4f46e5',
    '#0d9488',
    '#db2777',
    '#d97706',
    '#7c3aed',
    '#0891b2',
    '#be123c',
    '#65a30d',
]

DYNAMIC_STRATEGIES = tuple(sorted(DYNAMIC_INTERVENTION_STRATEGIES))
GALAXY_MAX_NODES = 2000
GALAXY_MAX_EDGES = 28000
TEST_STYLE_MIN_NODES = 300
TEST_STYLE_NODE_COLOR = '#60a5fa'
TEST_STYLE_EDGE_COLOR = '#94a3b8'

# Trọng số mặc định cho điểm nguy cơ (mỗi trọng số ∈ (0, 1); metrics đã là centrality 0–1).
DEFAULT_RISK_WEIGHTS = {
    'betweenness': 0.3,
    'degree': 0.25,
    'eigenvector': 0.25,
    'pagerank': 0.2,
}


def raw_risk_score(
    betweenness: float,
    degree_centrality: float,
    eigenvector: float,
    pagerank: float = 0.0,
    weights: Optional[dict] = None,
) -> float:
    """Tổng có trọng số trên chỉ số trung tâm [0, 1] (chưa scale theo mạng)."""
    w = weights or DEFAULT_RISK_WEIGHTS
    return (
        float(betweenness or 0) * float(w.get('betweenness', 0.3))
        + float(degree_centrality or 0) * float(w.get('degree', 0.25))
        + float(eigenvector or 0) * float(w.get('eigenvector', 0.25))
        + float(pagerank or 0) * float(w.get('pagerank', 0.2))
    )


def risk_label_from_score(score: int) -> str:
    """Nhãn nguy cơ từ điểm đã chuẩn hóa 0–100 trong phạm vi mạng hiện tại."""
    s = int(score)
    if s >= 85:
        return 'High'
    if s >= 65:
        return 'Medium'
    if s >= 40:
        return 'Low'
    return 'Unknown'


def apply_normalized_risk_scores(rows: list, weights: Optional[dict] = None) -> None:
    """Gán risk_score 0–100 (min–max trong tập rows) và risk tương ứng."""
    if not rows:
        return
    raws = [
        raw_risk_score(
            r.get('betweenness', 0),
            r.get('degree_metric', r.get('degree', 0)),
            r.get('eigenvector', 0),
            r.get('pagerank', 0),
            weights,
        )
        for r in rows
    ]
    lo, hi = min(raws), max(raws)
    span = hi - lo
    for row, raw in zip(rows, raws):
        if span <= 1e-12:
            score = 50 if raw > 0 else 0
        else:
            score = int(round(100 * (raw - lo) / span))
        row['risk_score'] = score
        row['risk'] = risk_label_from_score(score)


def compute_risk_score(
    betweenness: float,
    degree_centrality: float,
    eigenvector: float,
    pagerank: float = 0.0,
    weights: Optional[dict] = None,
) -> int:
    """Điểm thô ×100 (giữ tương thích); dashboard dùng apply_normalized_risk_scores."""
    return int(
        round(
            100
            * min(
                1.0,
                raw_risk_score(
                    betweenness, degree_centrality, eigenvector, pagerank, weights
                ),
            )
        )
    )

_cached_graph = None
_cached_payload_by_viz: dict[str, dict] = {}
_cached_output = None
_csv_data_cache: dict[str, tuple] = {}
_recommendations_cache: dict[str, dict] = {}


def _invalidate_graph_cache() -> None:
    global _cached_graph, _cached_payload_by_viz, _cached_output
    _cached_graph = None
    _cached_payload_by_viz = {}
    _cached_output = None
    _csv_data_cache.clear()
    _recommendations_cache.clear()


def _dataset_csv_mtimes(folder: Path) -> tuple[float, float, float]:
    users_csv = folder / 'users.csv'
    rels_csv = folder / 'relationships.csv'
    metrics_csv = folder / 'metrics.csv'
    return (
        users_csv.stat().st_mtime,
        rels_csv.stat().st_mtime,
        metrics_csv.stat().st_mtime,
    )


def _csv_row_count(path: Path) -> int:
    with path.open('r', encoding='utf-8', errors='replace') as fh:
        return max(0, sum(1 for _ in fh) - 1)


def get_latest_output_dir() -> Optional[Path]:
    env_path = os.getenv('MO_PHONG_OUTPUT_DIR')
    if env_path:
        output_dir = Path(env_path)
        if output_dir.exists() and output_dir.is_dir():
            return output_dir

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []
    candidates += [p for p in OUTPUTS_DIR.glob('output_*') if p.is_dir()]
    candidates += [p for p in OUTPUTS_DIR.glob('output_uploaded_*') if p.is_dir()]
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        candidates += [p for p in OUTPUT_ROOT.glob('output_*') if p.is_dir()]
        candidates += [p for p in OUTPUT_ROOT.glob('output_uploaded_*') if p.is_dir()]
    except OSError:
        pass
    # Tương thích bộ cũ nằm trực tiếp dưới root repo
    candidates += [p for p in BASE_DIR.glob('output_*') if p.is_dir()]
    candidates += [p for p in BASE_DIR.glob('output_uploaded_*') if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_output_folder(output_dir: Optional[str]) -> Optional[Path]:
    """Giải đường dẫn dataset từ tham số API hoặc chỉ tên thư mục."""
    if not output_dir:
        return get_latest_output_dir()
    p = Path(output_dir)
    if p.is_dir():
        return p
    name = p.name
    for root in (OUTPUTS_DIR, BASE_DIR, OUTPUT_ROOT):
        cand = root / name
        if cand.is_dir():
            return cand
    for root in (OUTPUTS_DIR, BASE_DIR, OUTPUT_ROOT):
        cand = root / output_dir
        if cand.is_dir():
            return cand
    return None


def dataset_data_date(folder: Path) -> str:
    """Ngày tạo bộ dữ liệu (YYYY-MM-DD) — từ tên thư mục output_*_YYYYMMDD_HHMMSS hoặc mtime."""
    m = _DATASET_DIR_TS_RE.search(folder.name)
    if m:
        ymd = m.group(1)
        return f'{ymd[0:4]}-{ymd[4:6]}-{ymd[6:8]}'
    try:
        return datetime.datetime.fromtimestamp(folder.stat().st_mtime).strftime('%Y-%m-%d')
    except OSError:
        return datetime.date.today().isoformat()


def _strip_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lstrip('\ufeff') for c in out.columns]
    return out


def _resolve_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    cols = set(df.columns)
    lower = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name in cols:
            return name
        hit = lower.get(name.lower())
        if hit:
            return hit
    return None


def normalize_users_df(users: pd.DataFrame) -> pd.DataFrame:
    users = _strip_dataframe_columns(users)
    id_col = _resolve_column(users, 'id', 'user_id', 'node_id')
    if id_col is None:
        raise ValueError(
            f'users.csv thiếu cột id (hoặc user_id). Có: {", ".join(map(str, users.columns))}'
        )
    if id_col != 'id':
        users = users.rename(columns={id_col: 'id'})
    return users


def normalize_relationships_df(relationships: pd.DataFrame) -> pd.DataFrame:
    relationships = _strip_dataframe_columns(relationships)
    source_col = _resolve_column(
        relationships, 'source', 'user1_id', 'from', 'src', 'node1', 'u'
    )
    target_col = _resolve_column(
        relationships, 'target', 'user2_id', 'to', 'dst', 'node2', 'v'
    )
    if source_col is None or target_col is None:
        raise ValueError(
            'relationships.csv thiếu cột nguồn/đích (source/target hoặc user1_id/user2_id). '
            f'Có: {", ".join(map(str, relationships.columns))}'
        )
    rename = {}
    if source_col != 'source':
        rename[source_col] = 'source'
    if target_col != 'target':
        rename[target_col] = 'target'
    if rename:
        relationships = relationships.rename(columns=rename)

    relationships['source'] = pd.to_numeric(relationships['source'], errors='coerce')
    relationships['target'] = pd.to_numeric(relationships['target'], errors='coerce')
    before = len(relationships)
    relationships = relationships.dropna(subset=['source', 'target'], how='any')
    dropped = before - len(relationships)
    if dropped:
        logger.warning(
            'relationships.csv: bỏ %s dòng không hợp lệ (thiếu source/target hoặc rỗng)',
            dropped,
        )
    if relationships.empty:
        raise ValueError('relationships.csv không còn cạnh hợp lệ sau khi lọc')
    relationships['source'] = relationships['source'].astype(np.int64)
    relationships['target'] = relationships['target'].astype(np.int64)
    return relationships


def load_output_data(output_dir: Optional[str] = None):
    if output_dir:
        folder = resolve_output_folder(output_dir)
    else:
        folder = get_latest_output_dir()
    if folder is None or not folder.exists():
        raise FileNotFoundError('Không tìm thấy thư mục dữ liệu output')

    users_csv = folder / 'users.csv'
    rels_csv = folder / 'relationships.csv'
    metrics_csv = folder / 'metrics.csv'

    if not users_csv.exists() or not rels_csv.exists() or not metrics_csv.exists():
        raise FileNotFoundError('File dữ liệu cần thiết không tồn tại trong output folder')

    cache_key = str(folder.resolve())
    mtimes = _dataset_csv_mtimes(folder)
    cached = _csv_data_cache.get(cache_key)
    if cached is not None and cached[0] == mtimes:
        return folder, cached[1], cached[2], cached[3]

    users = normalize_users_df(pd.read_csv(users_csv))
    relationships = normalize_relationships_df(pd.read_csv(rels_csv))
    metrics = _strip_dataframe_columns(pd.read_csv(metrics_csv))
    _csv_data_cache[cache_key] = (mtimes, users, relationships, metrics)

    return folder, users, relationships, metrics


def create_graph(users: pd.DataFrame, relationships: pd.DataFrame) -> nx.Graph:
    users = normalize_users_df(users)
    relationships = normalize_relationships_df(relationships)
    graph = nx.Graph()
    graph.add_nodes_from(users['id'].astype(np.int64, copy=False))
    graph.add_edges_from(
        zip(relationships['source'].to_numpy(), relationships['target'].to_numpy())
    )
    return graph


def build_dataset_summary(output_dir: Optional[str] = None) -> dict:
    """Metadata dataset — không dựng layout / đồ thị (dùng cho /api/summary)."""
    try:
        folder, users, relationships, _metrics = load_output_data(output_dir)
    except FileNotFoundError as e:
        logger.warning('build_dataset_summary: %s', e)
        p = empty_graph_payload()
        return {
            'ready': False,
            'nodes': p['nodes'],
            'edges': p['edges'],
            'data_date': p['data_date'],
            'status': p['status'],
            'version': p['version'],
            'timestamp': p['timestamp'],
            'output_folder': None,
            'hint': p['hint'],
        }
    return {
        'ready': True,
        'nodes': len(users),
        'edges': len(relationships),
        'data_date': dataset_data_date(folder),
        'status': 'Dữ liệu đã sẵn sàng',
        'version': '1.0.0',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'output_folder': folder.name,
        'hint': None,
    }


def _intervention_rank_key(run: dict) -> tuple:
    """
    Thứ tự ưu tiên (nhỏ hơn = tốt hơn):
    1) Tổng nút từng nhiễm thấp (total_infected)
    2) Đỉnh đồng thời nhiễm thấp (peak_infected)
    3) Kết thúc dịch sớm (final_day)
    """
    big = 10**9
    return (
        int(run['total_infected']) if run.get('total_infected') is not None else big,
        int(run['peak_infected']) if run.get('peak_infected') is not None else big,
        int(run['final_day']) if run.get('final_day') is not None else big,
    )


def sir_metrics_from_history_df(df: pd.DataFrame, n_nodes: int) -> tuple:
    """(peak_day, peak_infected, final_day, total_infected, never_infected)."""
    from .sir_models import sir_epidemic_totals_from_history

    peak_idx = df['I'].idxmax()
    peak_day = int(df.loc[peak_idx, 'day'])
    peak_I = int(df['I'].max())
    final_day = epidemic_final_day_from_history(df)
    total_inf, never_inf = sir_epidemic_totals_from_history(df, n_nodes)
    return peak_day, peak_I, final_day, total_inf, never_inf


def _intervention_run_row(
    folder: Path,
    id_to_name: dict,
    n_nodes: int,
    strategy: str,
    intervention_day: int,
    top_k: int,
    misinfo_source_mode: str = 'random',
) -> dict:
    """Một kịch bản can thiệp (nguồn xấu + strategy + ngày + top_k)."""
    misinfo = normalize_misinfo_mode(misinfo_source_mode)
    hist_path = find_dynamic_sir_history_csv(
        folder, strategy, intervention_day, top_k, misinfo
    )
    node_ids = (
        read_immunized_node_ids(
            folder, strategy, intervention_day, top_k, misinfo
        )
        if hist_path is not None
        else []
    )
    if hist_path is None:
        return {
            'misinfo_source_mode': misinfo,
            'strategy': strategy,
            'intervention_day': intervention_day,
            'top_k': top_k,
            'available': False,
            'peak_day': None,
            'peak_infected': None,
            'final_day': None,
            'total_infected': None,
            'never_infected': None,
            'node_ids': node_ids,
            'intervened_nodes': [],
        }
    dfp = pd.read_csv(hist_path)
    peak_day, peak_I, final_day, total_inf, never_inf = sir_metrics_from_history_df(dfp, n_nodes)
    detail = [{'id': nid, 'name': id_to_name.get(nid, str(nid))} for nid in node_ids]
    out_day = int(intervention_day)
    out_k = int(top_k)
    out_misinfo = misinfo
    mj_path = hist_path.parent / 'immunized_nodes.json'
    if mj_path.is_file():
        try:
            with open(mj_path, encoding='utf-8') as f:
                mj = json.load(f)
            if mj.get('intervention_day') is not None:
                out_day = int(mj['intervention_day'])
            if mj.get('top_k') is not None:
                out_k = int(mj['top_k'])
            if mj.get('misinfo_source_mode'):
                out_misinfo = normalize_misinfo_mode(str(mj['misinfo_source_mode']))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return {
        'misinfo_source_mode': out_misinfo,
        'strategy': strategy,
        'intervention_day': out_day,
        'top_k': out_k,
        'available': True,
        'peak_day': int(peak_day),
        'peak_infected': int(peak_I),
        'final_day': int(final_day),
        'total_infected': int(total_inf),
        'never_infected': int(never_inf),
        'node_ids': node_ids,
        'intervened_nodes': detail,
    }


def _load_sir_export_payload_from_folder(folder: Path) -> tuple[Optional[dict], list[dict]]:
    """Đọc SIR thuần + các lần can thiệp đã lưu trên đĩa (cho xuất PDF)."""
    users_csv = folder / 'users.csv'
    if not users_csv.exists():
        raise FileNotFoundError('Thiếu users.csv trong output')

    users = pd.read_csv(users_csv)
    id_col = 'user_id' if 'user_id' in users.columns else 'id'
    name_col = 'name' if 'name' in users.columns else id_col
    id_to_name = {int(r[id_col]): str(r.get(name_col, r[id_col])) for _, r in users.iterrows()}
    n_nodes = len(users)

    pure = None
    pure_hist_path = find_pure_sir_history_csv(folder)
    if pure_hist_path is not None:
        pdf = pd.read_csv(pure_hist_path)
        pd_day, pd_pi, pd_fd, pd_ti, pd_ni = sir_metrics_from_history_df(pdf, n_nodes)
        pure = {
            'model': 'pure',
            'peak_day': pd_day,
            'peak_infected': pd_pi,
            'final_day': pd_fd,
            'total_infected': pd_ti,
            'never_infected': pd_ni,
            'history': pdf.to_dict(orient='records'),
        }

    dynamic_runs: list[dict] = []
    for item in list_saved_dynamic_sir_runs(folder):
        row = _intervention_run_row(
            folder,
            id_to_name,
            n_nodes,
            item['strategy'],
            int(item['intervention_day']),
            int(item['top_k']),
            item.get('misinfo_source_mode', 'random'),
        )
        if not row.get('available'):
            continue
        hist_path = find_dynamic_sir_history_csv(
            folder,
            row['strategy'],
            row['intervention_day'],
            row['top_k'],
            row.get('misinfo_source_mode'),
        )
        if hist_path is None:
            continue
        dfp = pd.read_csv(hist_path)
        row['history'] = dfp.to_dict(orient='records')
        dynamic_runs.append(row)

    return pure, dynamic_runs


def _run_export_key(run: dict) -> tuple:
    if run.get('model') == 'pure' or run.get('is_pure'):
        return ('pure', '', 0, 0)
    return (
        'dynamic',
        str(run.get('strategy') or 'betweenness'),
        int(run.get('intervention_day') or 0),
        int(run.get('top_k') or 0),
    )


def _merge_export_runs(
    pure_session: Optional[dict],
    dynamic_session: Optional[list],
    disk_pure: Optional[dict],
    disk_runs: list[dict],
) -> tuple[Optional[dict], list[dict]]:
    """Gộp phiên hiện tại + mọi lần chạy đã lưu trên đĩa."""
    pure = disk_pure
    if pure_session:
        if not pure or (pure_session.get('history') and len(pure_session.get('history') or []) >= len(pure.get('history') or [])):
            pure = pure_session

    merged: dict[tuple, dict] = {}
    for r in disk_runs or []:
        merged[_run_export_key(r)] = r
    for r in dynamic_session or []:
        if not r:
            continue
        k = _run_export_key(r)
        prev = merged.get(k)
        if prev is None or (
            r.get('history')
            and len(r.get('history') or []) >= len(prev.get('history') or [])
        ):
            merged[k] = r

    dynamic_list = [merged[k] for k in sorted(merged.keys()) if k[0] == 'dynamic']
    return pure, dynamic_list


def _folder_analysis_token(folder: Path) -> tuple:
    """Token thay đổi khi CSV gốc hoặc kết quả SIR trên đĩa đổi."""
    parts: list = []
    for name in ('users.csv', 'relationships.csv', 'metrics.csv'):
        p = folder / name
        parts.append(p.stat().st_mtime if p.is_file() else 0.0)
    parts.append(len(list_saved_dynamic_sir_runs(folder)))
    pure_hist = find_pure_sir_history_csv(folder)
    parts.append(pure_hist.stat().st_mtime if pure_hist is not None else 0.0)
    return tuple(parts)


def build_intervention_recommendations(folder: Path) -> dict:
    cache_key = str(folder.resolve())
    token = _folder_analysis_token(folder)
    hit = _recommendations_cache.get(cache_key)
    if hit is not None and hit[0] == token:
        return hit[1]

    users_csv = folder / 'users.csv'
    if not users_csv.exists():
        raise FileNotFoundError('Thiếu users.csv trong output')

    users = pd.read_csv(users_csv)
    id_col = 'user_id' if 'user_id' in users.columns else 'id'
    name_col = 'name' if 'name' in users.columns else id_col
    id_to_name = {int(r[id_col]): str(r.get(name_col, r[id_col])) for _, r in users.iterrows()}
    n_nodes = len(users)

    pure_hist_path = find_pure_sir_history_csv(folder)
    pure_metrics = None
    if pure_hist_path is not None:
        pdf = pd.read_csv(pure_hist_path)
        pd_day, pd_pi, pd_fd, pd_ti, pd_ni = sir_metrics_from_history_df(pdf, n_nodes)
        pure_metrics = {
            'peak_day': pd_day,
            'peak_infected': pd_pi,
            'final_day': pd_fd,
            'total_infected': pd_ti,
            'never_infected': pd_ni,
        }

    saved = list_saved_dynamic_sir_runs(folder)
    runs: list[dict] = []
    for item in saved:
        runs.append(
            _intervention_run_row(
                folder,
                id_to_name,
                n_nodes,
                item['strategy'],
                int(item['intervention_day']),
                int(item['top_k']),
                item.get('misinfo_source_mode', 'random'),
            )
        )

    seen_strategies = {r['strategy'] for r in runs if r['available']}
    for strategy in DYNAMIC_STRATEGIES:
        if strategy not in seen_strategies:
            runs.append(
                {
                    'strategy': strategy,
                    'intervention_day': None,
                    'top_k': None,
                    'available': False,
                    'peak_day': None,
                    'peak_infected': None,
                    'final_day': None,
                    'total_infected': None,
                    'never_infected': None,
                    'node_ids': [],
                    'intervened_nodes': [],
                }
            )

    available_runs = [r for r in runs if r['available']]
    available_runs.sort(key=_intervention_rank_key)
    runs.sort(
        key=lambda r: (
            not r['available'],
            _intervention_rank_key(r) if r['available'] else (10**9, 10**9, 10**9),
            r.get('strategy') or '',
        )
    )

    strategy_summary: list[dict] = []
    for strategy in DYNAMIC_STRATEGIES:
        pool = [r for r in runs if r['strategy'] == strategy and r['available']]
        if pool:
            best = min(pool, key=_intervention_rank_key)
            strategy_summary.append({**best, 'is_best_for_strategy': True})
        else:
            strategy_summary.append(
                {
                    'strategy': strategy,
                    'intervention_day': None,
                    'top_k': None,
                    'available': False,
                    'peak_day': None,
                    'peak_infected': None,
                    'final_day': None,
                    'total_infected': None,
                    'never_infected': None,
                    'node_ids': [],
                    'intervened_nodes': [],
                    'is_best_for_strategy': False,
                }
            )

    winner = None
    if available_runs:
        w = available_runs[0]
        winner = dict(w)

    result = {
        'output_folder': folder.name,
        'pure_sir': pure_metrics,
        'runs': runs,
        'strategies': strategy_summary,
        'winner': winner,
    }
    _recommendations_cache[cache_key] = (token, result)
    return result


def _metrics_layout_frame(metrics: pd.DataFrame) -> pd.DataFrame:
    """Chuẩn hóa cột id / betweenness để chọn hub cụm (khớp CSV sinh & upload)."""
    m = metrics.copy()
    if 'user_id' in m.columns:
        m = m.rename(columns={'user_id': 'id'})
    for old, new in (
        ('betweenness_centrality', 'betweenness'),
        ('degree_centrality', 'degree'),
        ('eigenvector_centrality', 'eigenvector'),
        ('pagerank_centrality', 'pagerank'),
        ('pagerank', 'pagerank'),
    ):
        if old in m.columns and new not in m.columns:
            m = m.rename(columns={old: new})
    return m


def _layout_priority_nodes(metrics_norm: pd.DataFrame, k: int = 6) -> set[int]:
    """Top nút theo betweenness + degree + eigenvector — dùng kéo về trung tâm khi spring layout."""
    if metrics_norm is None or len(metrics_norm) == 0 or 'id' not in metrics_norm.columns:
        return set()
    m = metrics_norm.copy()
    for c in ('betweenness', 'degree', 'eigenvector', 'pagerank'):
        if c not in m.columns:
            m[c] = 0.0
    m['_lw'] = (
        m['betweenness'].fillna(0) * 3.5
        + m['degree'].fillna(0) * 1.15
        + m['eigenvector'].fillna(0) * 1.35
        + m['pagerank'].fillna(0) * 1.25
    )
    try:
        top = m.nlargest(min(k, len(m)), '_lw')
        return {int(x) for x in top['id']}
    except (TypeError, ValueError):
        return set()


def _select_cluster_hubs(graph: nx.Graph, communities: list, metrics_norm: pd.DataFrame) -> set:
    bet: dict = {}
    if metrics_norm is not None and len(metrics_norm) and 'id' in metrics_norm.columns:
        col = 'betweenness' if 'betweenness' in metrics_norm.columns else None
        if col:
            for _, row in metrics_norm.iterrows():
                try:
                    bet[int(row['id'])] = float(row[col] or 0)
                except (TypeError, ValueError):
                    continue
    hub_nodes: set = set()
    for comm in communities:
        nodes = [n for n in comm if n in graph]
        if not nodes:
            continue
        scored = sorted(
            nodes,
            key=lambda n: (bet.get(n, 0.0), graph.degree(n) if n in graph else 0),
            reverse=True,
        )
        nh = max(1, min(2, 1 + len(nodes) // 22))
        hub_nodes.update(scored[:nh])
    return hub_nodes


def _centrality_maps(
    metrics_norm: Optional[pd.DataFrame], graph: nx.Graph
) -> Tuple[dict[int, float], dict[int, float], dict[int, float], dict[int, float]]:
    """Betweenness / eigenvector / pagerank từ metrics; degree từ đồ thị."""
    bet: dict[int, float] = {}
    eig: dict[int, float] = {}
    pr: dict[int, float] = {}
    if metrics_norm is not None and len(metrics_norm) and 'id' in metrics_norm.columns:
        for _, row in metrics_norm.iterrows():
            try:
                nid = int(row['id'])
            except (TypeError, ValueError):
                continue
            if 'betweenness' in metrics_norm.columns:
                bet[nid] = float(row.get('betweenness') or 0)
            if 'eigenvector' in metrics_norm.columns:
                eig[nid] = float(row.get('eigenvector') or 0)
            if 'pagerank' in metrics_norm.columns:
                pr[nid] = float(row.get('pagerank') or 0)
    deg = {int(n): float(graph.degree(n)) for n in graph.nodes()}
    return bet, eig, deg, pr


def _parse_hex_color(hex_color: str) -> tuple[int, int, int]:
    h = str(hex_color).strip().lstrip('#')
    if len(h) != 6:
        return (148, 163, 184)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb_hex(r: int, g: int, b: int) -> str:
    return f'#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}'


def cluster_node_fill(
    cluster_hex: str,
    risk: str,
    *,
    is_hub: bool = False,
    is_context: bool = False,
) -> str:
    """
    Màu nút = tông cụm (community) + độ đậm theo nguy cơ.
    Hub đậm hơn; node phụ / nền nhạt hơn trong cùng cụm.
    """
    r, g, b = _parse_hex_color(cluster_hex)
    rk = str(risk or 'Unknown')
    lighten = {'High': 0.08, 'Medium': 0.18, 'Low': 0.3, 'Unknown': 0.38}.get(rk, 0.32)
    darken = {'High': 0.78, 'Medium': 0.86, 'Low': 0.94, 'Unknown': 0.9}.get(rk, 0.9)

    if is_context:
        lighten = max(lighten, 0.55)
        darken *= 0.96

    if is_hub:
        rr = max(0, min(255, int(r * darken)))
        gg = max(0, min(255, int(g * darken)))
        bb = max(0, min(255, int(b * darken)))
    else:
        rr = int(r + (255 - r) * lighten)
        gg = int(g + (255 - g) * lighten)
        bb = int(b + (255 - b) * lighten)
        rr, gg, bb = int(rr * darken), int(gg * darken), int(bb * darken)

    return _rgb_hex(rr, gg, bb)


def _communities_for_nodes(communities: list, node_ids: Set[int]) -> list:
    out = []
    for comm in communities:
        sub = {int(x) for x in comm if int(x) in node_ids}
        if sub:
            out.append(sub)
    return out


def _has_cross_cluster_neighbors(
    graph: nx.Graph, nid: int, node_to_cluster: dict[int, str]
) -> bool:
    com = node_to_cluster.get(nid)
    if com is None:
        return False
    for nb in graph.neighbors(nid):
        c2 = node_to_cluster.get(int(nb))
        if c2 is not None and c2 != com:
            return True
    return False


def _select_bridge_nodes(
    graph: nx.Graph,
    visible: Set[int],
    node_to_cluster: dict[int, str],
    bet: dict[int, float],
    *,
    limit: int = 14,
) -> Set[int]:
    """Nút cầu nối giữa các community (có láng giềng thuộc cụm khác)."""
    scored: list = []
    for nid in visible:
        com = node_to_cluster.get(nid)
        if com is None:
            continue
        other = set()
        for nb in graph.neighbors(nid):
            c2 = node_to_cluster.get(int(nb))
            if c2 is not None and c2 != com:
                other.add(c2)
        if other:
            scored.append((bet.get(nid, 0.0), len(other), graph.degree(nid), nid))
    scored.sort(reverse=True)
    return {int(nid) for _, _, _, nid in scored[:limit]}


def _viz_score(
    nid: int,
    bet: dict,
    eig: dict,
    deg: dict,
    pr: Optional[dict] = None,
) -> float:
    pr = pr or {}
    return (
        bet.get(nid, 0.0) * 4.0
        + deg.get(nid, 0.0) * 1.15
        + eig.get(nid, 0.0) * 1.5
        + pr.get(nid, 0.0) * 1.2
    )


def _community_center_nodes(
    graph: nx.Graph, communities: list, bet: dict[int, float]
) -> Set[int]:
    """Một nút đại diện mỗi cụm (betweenness, rồi degree)."""
    centers: Set[int] = set()
    for comm in communities:
        nodes = [x for x in comm if x in graph]
        if not nodes:
            continue
        best = max(nodes, key=lambda n: (bet.get(n, 0.0), graph.degree(n)))
        centers.add(int(best))
    return centers


def _reps_per_cluster(cluster_size: int) -> int:
    """Số nút đại diện mỗi cụm — cụm lớn hơn thì nhiều nút hơn."""
    if cluster_size <= 1:
        return 1
    if cluster_size <= 5:
        return 2
    if cluster_size <= 15:
        return max(2, 1 + cluster_size // 6)
    if cluster_size <= 45:
        return max(3, int(math.sqrt(cluster_size)))
    return max(4, min(10, int(math.sqrt(cluster_size) * 1.1)))


def _expand_visible_for_local_neighbors(
    graph: nx.Graph,
    visible: Set[int],
    bet: dict[int, float],
    *,
    max_expansions: int = 28,
) -> Set[int]:
    """Bổ sung láng giềng mạnh nếu nút visible không còn cạnh nào trong tập hiển thị."""
    added: Set[int] = set()
    for nid in visible:
        if len(added) >= max_expansions:
            break
        has_vis_nb = any(int(nb) in visible or int(nb) in added for nb in graph.neighbors(nid))
        if has_vis_nb:
            continue
        extras = sorted(
            (
                (_edge_viz_weight(graph, int(nid), int(nb)), bet.get(int(nb), 0.0), int(nb))
                for nb in graph.neighbors(nid)
            ),
            reverse=True,
        )
        for _, _, nb in extras[:2]:
            if nb not in visible and nb not in added:
                added.add(nb)
                break
    return added


def _select_global_connectors(
    graph: nx.Graph,
    bet: dict[int, float],
    node_to_cluster: dict[int, str],
    *,
    limit: int = 10,
    exclude: Optional[Set[int]] = None,
) -> Set[int]:
    """Top betweenness có cạnh liên cụm — bổ sung sau chọn theo cụm."""
    exclude = exclude or set()
    ranked = sorted(
        (
            int(n)
            for n in graph.nodes()
            if int(n) not in exclude
            and _has_cross_cluster_neighbors(graph, int(n), node_to_cluster)
        ),
        key=lambda nid: (bet.get(nid, 0.0), graph.degree(nid)),
        reverse=True,
    )
    return set(ranked[:limit])


def _select_viz_node_sets(
    graph: nx.Graph,
    communities: list,
    metrics_norm: Optional[pd.DataFrame],
    hub_nodes: Set[int],
    cluster_name_by_id: Optional[dict[int, str]] = None,
) -> Tuple[Set[int], Set[int], Set[int]]:
    """
  Tập nút đại diện: mỗi cụm góp số nút theo quy mô cụm (betweenness/degree).
  Luôn giữ hub cụm, nút cầu liên cụm và connector toàn cục.
  Mạng nhỏ (≤20): hiển thị toàn bộ.
    """
    n = graph.number_of_nodes()
    if n == 0:
        return set(), set(), set()
    bet, eig, deg, pr = _centrality_maps(metrics_norm, graph)
    node_to_comm: dict[int, int] = {}
    for ci, comm in enumerate(communities):
        for x in comm:
            if x in graph:
                node_to_comm[int(x)] = ci

    if cluster_name_by_id is None:
        cluster_name_by_id = {
            int(x): f'C{node_to_comm.get(int(x), -1)}' for x in graph.nodes()
        }

    if n <= 20:
        all_ids = {int(v) for v in graph.nodes()}
        bridges_small = _select_bridge_nodes(
            graph, all_ids, cluster_name_by_id, bet, limit=10
        )
        return all_ids, set(), bridges_small

    primary: Set[int] = set()
    per_cluster_best: Set[int] = set()
    cross_cluster_important: Set[int] = set()

    for comm in communities:
        nodes = [int(x) for x in comm if x in graph]
        if not nodes:
            continue
        ranked = sorted(nodes, key=lambda nid: _viz_score(nid, bet, eig, deg, pr), reverse=True)
        k = _reps_per_cluster(len(nodes))
        pick = ranked[:k]
        primary.update(pick)
        per_cluster_best.add(ranked[0])
        quota_ids = set(pick)
        for nid in ranked[k:]:
            if nid in quota_ids:
                continue
            if _has_cross_cluster_neighbors(graph, nid, cluster_name_by_id):
                if bet.get(nid, 0.0) > 0 or graph.degree(nid) >= 3:
                    cross_cluster_important.add(nid)
                    if len(cross_cluster_important) >= len(communities) + 4:
                        break

    primary.update(cross_cluster_important)
    primary.update(int(h) for h in hub_nodes if h in graph)

    all_node_ids = {int(v) for v in graph.nodes()}
    bridge_limit = min(16, max(12, len(communities) + 4))
    bridge_ids = _select_bridge_nodes(
        graph, all_node_ids, cluster_name_by_id, bet, limit=bridge_limit
    )
    primary.update(bridge_ids)

    global_budget = min(10, max(6, len(communities) + 2))
    global_ids = _select_global_connectors(
        graph, bet, cluster_name_by_id, limit=global_budget, exclude=set()
    )
    primary.update(global_ids)

    max_total = min(62, max(14, int(math.sqrt(n) * 2.2) + len(communities) * 2))
    preserved = (
        per_cluster_best
        | bridge_ids
        | global_ids
        | cross_cluster_important
        | {int(h) for h in hub_nodes if h in graph}
    )
    if len(primary) > max_total:
        scored = sorted(primary, key=lambda nid: _viz_score(nid, bet, eig, deg, pr), reverse=True)
        trimmed: Set[int] = set(scored[:max_total]) | preserved
        while len(trimmed) > max_total:
            pool = sorted(
                (x for x in trimmed if x not in preserved),
                key=lambda nid: _viz_score(nid, bet, eig, deg, pr),
            )
            if not pool:
                break
            trimmed.discard(pool[-1])
        primary = trimmed
        bridge_ids = bridge_ids & primary
        global_ids = global_ids & primary

    expansion = _expand_visible_for_local_neighbors(
        graph, primary, bet, max_expansions=8
    )
    primary.update(expansion)
    preserved |= expansion

    bridge_ids = _select_bridge_nodes(
        graph, primary, cluster_name_by_id, bet, limit=bridge_limit
    )
    primary.update(bridge_ids)

    return primary, set(), bridge_ids


def _viz_edges_payload(
    graph: nx.Graph,
    visible: Set[int],
    hub_nodes: Set[int],
    centers: Set[int],
    cluster_name: dict[int, str],
    *,
    bridge_nodes: Optional[Set[int]] = None,
    max_edges: int = 200,
) -> list:
    """Cạnh nội cụm (ưu tiên hub); liên cụm chỉ qua bridge — tránh mạng nhện."""
    bridge_nodes = bridge_nodes or set()
    intra_ranked: list = []
    inter_ranked: list = []
    for u, v in graph.edges():
        u, v = int(u), int(v)
        if u not in visible or v not in visible:
            continue
        cu = cluster_name.get(u)
        cv = cluster_name.get(v)
        inter = cu is not None and cv is not None and cu != cv
        touch_h = u in hub_nodes or v in hub_nodes
        touch_c = u in centers or v in centers
        touch_b = u in bridge_nodes or v in bridge_nodes
        w = graph.degree(u) * graph.degree(v) + graph.degree(u) + graph.degree(v)
        if inter:
            if not touch_b:
                continue
            inter_ranked.append((touch_h, touch_b, w, u, v))
        else:
            intra_ranked.append((touch_h, touch_c, w, u, v))
    intra_ranked.sort(key=lambda row: row[:3], reverse=True)
    inter_ranked.sort(key=lambda row: row[:3], reverse=True)
    max_inter = min(max(4, max_edges // 10), len(inter_ranked))
    take_intra = max(0, max_edges - max_inter)
    edges_data = []
    for *_, u, v in intra_ranked[:take_intra]:
        edges_data.append({'source': u, 'target': v, 'inter_cluster': False})
    for *_, u, v in inter_ranked[:max_inter]:
        edges_data.append({'source': u, 'target': v, 'inter_cluster': True})
    return edges_data


def _viz_edges_galaxy(
    graph: nx.Graph,
    visible: Set[int],
    hub_nodes: Set[int],
    centers: Set[int],
    cluster_name: dict[int, str],
    bridge_nodes: Set[int],
    *,
    max_edges: int = GALAXY_MAX_EDGES,
) -> list:
    """Lấy mẫu cạnh thông minh cho đồ thị lớn (500–2000 node): ưu tiên hub, cầu, cạnh nặng."""
    ranked: list = []
    for u, v in graph.edges():
        u, v = int(u), int(v)
        if u not in visible or v not in visible:
            continue
        cu = cluster_name.get(u)
        cv = cluster_name.get(v)
        inter = cu is not None and cv is not None and cu != cv
        touch_h = u in hub_nodes or v in hub_nodes
        touch_c = u in centers or v in centers
        touch_b = u in bridge_nodes or v in bridge_nodes
        w = graph.degree(u) * graph.degree(v) + graph.degree(u) + graph.degree(v)
        if inter and not touch_b:
            w *= 0.35
        score = w + (5000 if touch_h else 0) + (2500 if touch_b else 0) + (800 if touch_c else 0)
        ranked.append((score, u, v, inter))
    ranked.sort(key=lambda row: row[0], reverse=True)
    if len(ranked) > max_edges:
        ranked = ranked[:max_edges]
    return [{'source': u, 'target': v, 'inter_cluster': bool(inter)} for _, u, v, inter in ranked]


def _edge_viz_weight(graph: nx.Graph, u: int, v: int) -> float:
    return float(graph.degree(u) * graph.degree(v) + graph.degree(u) + graph.degree(v))


def _viz_edge_key(u: int, v: int) -> tuple[int, int]:
    u, v = int(u), int(v)
    return (u, v) if u < v else (v, u)


def _viz_degree_in_chosen(chosen: set[tuple[int, int]]) -> dict[int, int]:
    deg: dict[int, int] = {}
    for u, v in chosen:
        deg[u] = deg.get(u, 0) + 1
        deg[v] = deg.get(v, 0) + 1
    return deg


def _viz_ensure_connected_components(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    chosen: set[tuple[int, int]],
    add,
    *,
    max_bridges: int = 24,
) -> None:
    """Nối các thành phần liên thông trong tập cạnh viz bằng cạnh nặng nhất trên đồ thị gốc."""
    if len(visible) < 2:
        return

    def n_components() -> int:
        g = nx.Graph()
        for u, v in chosen:
            g.add_edge(u, v)
        for nid in visible:
            g.add_node(nid)
        return len(list(nx.connected_components(g)))

    if n_components() <= 1:
        return

    ranked: list = []
    for u, v in graph.edges():
        u, v = int(u), int(v)
        if u not in visible or v not in visible:
            continue
        ranked.append((_edge_viz_weight(graph, u, v), u, v))
    ranked.sort(key=lambda row: row[0], reverse=True)

    added = 0
    while n_components() > 1 and added < max_bridges:
        progress = False
        comp_map: dict[int, int] = {}
        g = nx.Graph()
        for u, v in chosen:
            g.add_edge(u, v)
        for nid in visible:
            g.add_node(nid)
        for ci, comp in enumerate(nx.connected_components(g)):
            for nid in comp:
                comp_map[int(nid)] = ci

        for _, u, v in ranked:
            if comp_map.get(u) == comp_map.get(v):
                continue
            inter = cluster_name.get(u) != cluster_name.get(v)
            add(u, v, bool(inter))
            added += 1
            progress = True
            if n_components() <= 1:
                break
        if not progress:
            break


def _viz_ensure_incident_for_nodes(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    chosen: set[tuple[int, int]],
    add,
    node_ids: Set[int],
    *,
    max_per_node: int = 2,
) -> None:
    """Hub/cầu bậc 0 trong payload — thêm 1–2 cạnh mạnh nhất tới láng giềng visible."""
    deg = _viz_degree_in_chosen(chosen)
    for nid in node_ids:
        if nid not in visible:
            continue
        if deg.get(nid, 0) > 0:
            continue
        extras: list = []
        for nb in graph.neighbors(nid):
            nb = int(nb)
            if nb not in visible:
                continue
            extras.append((_edge_viz_weight(graph, nid, nb), nb))
        extras.sort(key=lambda row: row[0], reverse=True)
        for _, nb in extras[:max_per_node]:
            inter = cluster_name.get(nid) != cluster_name.get(nb)
            add(nid, nb, inter)
            deg[nid] = deg.get(nid, 0) + 1
            deg[nb] = deg.get(nb, 0) + 1


def _viz_extra_intra_for_isolates(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    chosen: set[tuple[int, int]],
    add,
    *,
    per_node: int = 2,
) -> None:
    """Bổ sung cạnh nội cụm cho nút vẫn bậc 0 sau MST."""
    by_cluster: dict[str, list[int]] = {}
    for nid in visible:
        cn = str(cluster_name.get(nid) or '_')
        by_cluster.setdefault(cn, []).append(int(nid))
    deg = _viz_degree_in_chosen(chosen)
    for nodes in by_cluster.values():
        for nid in nodes:
            if deg.get(nid, 0) > 0:
                continue
            extras: list = []
            for nb in graph.neighbors(nid):
                nb = int(nb)
                if nb not in visible or cluster_name.get(nb) != cluster_name.get(nid):
                    continue
                key = _viz_edge_key(nid, nb)
                if key in chosen:
                    continue
                extras.append((_edge_viz_weight(graph, nid, nb), nb))
            extras.sort(key=lambda row: row[0], reverse=True)
            for _, nb in extras[:per_node]:
                add(nid, nb, False)


def _viz_add_bridge_inter_cluster_edges(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    chosen: set[tuple[int, int]],
    add,
    bridge_nodes: Set[int],
    *,
    max_per_bridge: int = 3,
) -> None:
    """Mọi cầu visible — tối đa N cạnh liên cụm mạnh nhất mỗi cầu."""
    for b in bridge_nodes:
        if b not in visible:
            continue
        extras: list = []
        for nb in graph.neighbors(b):
            nb = int(nb)
            if nb not in visible or cluster_name.get(nb) == cluster_name.get(b):
                continue
            key = _viz_edge_key(b, nb)
            if key in chosen:
                continue
            extras.append((_edge_viz_weight(graph, b, nb), nb))
        extras.sort(key=lambda row: row[0], reverse=True)
        for _, nb in extras[:max_per_bridge]:
            add(b, nb, True)


def _viz_fix_boundary_leaf_connectors(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    chosen: set[tuple[int, int]],
    add,
    bridge_nodes: Set[int],
) -> None:
    """Nút bậc 1 ở biên cụm (cầu/hub) — thêm một cạnh nội cụm dự phòng."""
    deg = _viz_degree_in_chosen(chosen)
    for nid in visible:
        if deg.get(nid, 0) != 1:
            continue
        if nid not in bridge_nodes:
            continue
        extras: list = []
        for nb in graph.neighbors(nid):
            nb = int(nb)
            if nb not in visible or cluster_name.get(nb) != cluster_name.get(nid):
                continue
            key = _viz_edge_key(nid, nb)
            if key in chosen:
                continue
            extras.append((_edge_viz_weight(graph, nid, nb), nb))
        extras.sort(key=lambda row: row[0], reverse=True)
        for _, nb in extras[:1]:
            add(nid, nb, False)


def _cluster_rep_node(
    graph: nx.Graph,
    nodes: Set[int],
    visible: Set[int],
    hub_nodes: Set[int],
    bet: dict[int, float],
) -> Optional[int]:
    """Một nút đại diện mỗi cụm trong tập visible (ưu tiên hub)."""
    candidates = [int(n) for n in nodes if int(n) in visible]
    if not candidates:
        return None
    hubs = [n for n in candidates if n in hub_nodes]
    pool = hubs if hubs else candidates
    return max(pool, key=lambda nid: (bet.get(nid, 0.0), graph.degree(nid)))


def _adjacent_grid_cluster_indices(idx: int, k: int, cols: int) -> list[int]:
    row, col = divmod(idx, cols)
    rows = int(math.ceil(k / cols))
    out: list[int] = []
    if row > 0:
        out.append(idx - cols)
    if row < rows - 1:
        out.append(idx + cols)
    if col > 0:
        out.append(idx - 1)
    if col < cols - 1:
        out.append(idx + 1)
    return [j for j in out if 0 <= j < k]


def _viz_add_grid_backbone_edges(
    graph: nx.Graph,
    visible: Set[int],
    communities: list,
    cluster_name: dict[int, str],
    hub_nodes: Set[int],
    bet: dict[int, float],
    chosen: set[tuple[int, int]],
    add,
) -> None:
    """Nối hub cụm với hub cụm ở ô lưới kề (cluster_focus) + 1 cạnh liên cụm mạnh/cụm."""
    comms = sorted(
        [{int(x) for x in c if int(x) in visible} for c in communities],
        key=lambda s: (-len(s), min(s) if s else 0),
    )
    comms = [c for c in comms if c]
    k = len(comms)
    if k < 2:
        return
    cols = int(math.ceil(math.sqrt(k)))
    reps: list[Optional[int]] = [
        _cluster_rep_node(graph, comm, visible, hub_nodes, bet) for comm in comms
    ]
    seen_pairs: set[tuple[int, int]] = set()
    for idx in range(k):
        rep_a = reps[idx]
        if rep_a is None:
            continue
        for j in _adjacent_grid_cluster_indices(idx, k, cols):
            if j <= idx:
                continue
            rep_b = reps[j]
            if rep_b is None:
                continue
            pair = (idx, j)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            best: list = []
            for u in comms[idx]:
                for v in comms[j]:
                    if graph.has_edge(u, v):
                        best.append((_edge_viz_weight(graph, u, v), u, v))
            if not best:
                continue
            best.sort(key=lambda row: row[0], reverse=True)
            _, u, v = best[0]
            add(u, v, True)
            if rep_a != u and rep_b != v:
                if graph.has_edge(rep_a, rep_b):
                    add(rep_a, rep_b, True)

    for idx, comm in enumerate(comms):
        rep = reps[idx]
        if rep is None:
            continue
        best_out: list = []
        for u in comm:
            for nb in graph.neighbors(u):
                nb = int(nb)
                if nb not in visible or cluster_name.get(nb) == cluster_name.get(u):
                    continue
                key = _viz_edge_key(u, nb)
                if key in chosen:
                    continue
                best_out.append((_edge_viz_weight(graph, u, nb), u, nb))
        if best_out:
            best_out.sort(key=lambda row: row[0], reverse=True)
            _, u, v = best_out[0]
            add(u, v, True)


def _ensure_viz_payload_connected(
    graph: nx.Graph,
    visible: Set[int],
    edges_data: list,
    cluster_name: dict[int, str],
    *,
    max_repairs: int = 32,
) -> list:
    """Đảm bảo payload cạnh tạo đúng 1 thành phần liên thông; sửa nút bậc 0."""
    if not visible:
        return edges_data

    chosen: set[tuple[int, int]] = set()
    out: list = []
    seen: set[tuple[int, int]] = set()

    def ingest(item: dict) -> None:
        u, v = int(item['source']), int(item['target'])
        key = _viz_edge_key(u, v)
        if key in seen:
            return
        seen.add(key)
        chosen.add(key)
        out.append(item)

    for item in edges_data:
        ingest(item)

    def add_edge(u: int, v: int, inter: bool) -> None:
        u, v = int(u), int(v)
        key = _viz_edge_key(u, v)
        if key in seen:
            return
        seen.add(key)
        chosen.add(key)
        out.append({'source': u, 'target': v, 'inter_cluster': bool(inter)})

    def n_components() -> int:
        g = nx.Graph()
        for u, v in chosen:
            g.add_edge(u, v)
        for nid in visible:
            g.add_node(nid)
        return len(list(nx.connected_components(g)))

    ranked: list = []
    for u, v in graph.edges():
        u, v = int(u), int(v)
        if u not in visible or v not in visible:
            continue
        ranked.append((_edge_viz_weight(graph, u, v), u, v))
    ranked.sort(key=lambda row: row[0], reverse=True)

    repairs = 0
    while n_components() > 1 and repairs < max_repairs:
        comp_map: dict[int, int] = {}
        g = nx.Graph()
        for u, v in chosen:
            g.add_edge(u, v)
        for nid in visible:
            g.add_node(nid)
        for ci, comp in enumerate(nx.connected_components(g)):
            for nid in comp:
                comp_map[int(nid)] = ci
        progress = False
        for _, u, v in ranked:
            if comp_map.get(u) == comp_map.get(v):
                continue
            inter = cluster_name.get(u) != cluster_name.get(v)
            add_edge(u, v, bool(inter))
            repairs += 1
            progress = True
            if n_components() <= 1:
                break
        if not progress:
            break

    deg = _viz_degree_in_chosen(chosen)
    for nid in visible:
        if deg.get(nid, 0) > 0:
            continue
        extras: list = []
        for nb in graph.neighbors(nid):
            nb = int(nb)
            if nb not in visible:
                continue
            extras.append((_edge_viz_weight(graph, nid, nb), nb))
        extras.sort(key=lambda row: row[0], reverse=True)
        for _, nb in extras[:2]:
            inter = cluster_name.get(nid) != cluster_name.get(nb)
            add_edge(nid, nb, bool(inter))
            deg[nid] = deg.get(nid, 0) + 1

    return out


def _viz_edges_clean_representative(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name: dict[int, str],
    cluster_color_by_id: Optional[dict[int, str]] = None,
    hub_nodes: Optional[Set[int]] = None,
    bridge_nodes: Optional[Set[int]] = None,
    *,
    communities: Optional[list] = None,
    bet: Optional[dict[int, float]] = None,
    max_inter: int = 10,
    extra_intra_per_hub: int = 1,
    extra_intra_per_cluster: int = 1,
) -> list:
    """
    Cạnh gọn cho đồ thị đại diện: MST trong mỗi cụm (+ vài cạnh hub),
    liên cụm thưa — tránh mạng nhện induced đầy đủ.
    """
    hub_nodes = hub_nodes or set()
    bridge_nodes = bridge_nodes or set()
    bet = bet or {}
    chosen: set[tuple[int, int]] = set()
    edges_data: list = []

    def add(u: int, v: int, inter: bool) -> None:
        u, v = int(u), int(v)
        if u == v:
            return
        key = _viz_edge_key(u, v)
        if key in chosen:
            return
        chosen.add(key)
        w = _edge_viz_weight(graph, u, v)
        item: dict = {
            'source': u,
            'target': v,
            'inter_cluster': bool(inter),
            'weight': round(w, 2),
        }
        if cluster_color_by_id:
            item['color'] = (
                cluster_color_by_id.get(u) or cluster_color_by_id.get(v) or '#94a3b8'
            )
        edges_data.append(item)

    by_cluster: dict[str, list[int]] = {}
    for nid in visible:
        cn = cluster_name.get(nid) or '_'
        by_cluster.setdefault(str(cn), []).append(int(nid))

    for nodes in by_cluster.values():
        if len(nodes) < 2:
            continue
        sub = graph.subgraph(nodes)
        try:
            mst = nx.minimum_spanning_tree(sub)
            for u, v in mst.edges():
                add(int(u), int(v), False)
        except Exception as exc:
            logger.debug('MST intra-cluster failed: %s', exc)

        for h in nodes:
            if h not in hub_nodes and len(nodes) > 8:
                continue
            extras: list = []
            for nb in graph.neighbors(h):
                nb = int(nb)
                if nb not in visible or cluster_name.get(nb) != cluster_name.get(h):
                    continue
                key = (h, nb) if h < nb else (nb, h)
                if key in chosen:
                    continue
                extras.append((_edge_viz_weight(graph, h, nb), nb))
            extras.sort(key=lambda row: row[0], reverse=True)
            for _, nb in extras[:extra_intra_per_hub]:
                add(h, nb, False)

        if extra_intra_per_cluster > 0 and len(nodes) > 2:
            ranked_intra: list = []
            for u, v in graph.edges():
                u, v = int(u), int(v)
                if u not in nodes or v not in nodes:
                    continue
                if cluster_name.get(u) != cluster_name.get(v):
                    continue
                key = _viz_edge_key(u, v)
                if key in chosen:
                    continue
                ranked_intra.append((_edge_viz_weight(graph, u, v), u, v))
            ranked_intra.sort(key=lambda row: row[0], reverse=True)
            added_extra = 0
            cap = extra_intra_per_cluster * max(1, len(nodes) // 6)
            for _, u, v in ranked_intra:
                if added_extra >= cap:
                    break
                add(u, v, False)
                added_extra += 1

    inter_ranked: list = []
    for u, v in graph.edges():
        u, v = int(u), int(v)
        if u not in visible or v not in visible:
            continue
        cu, cv = cluster_name.get(u), cluster_name.get(v)
        if cu is None or cv is None or cu == cv:
            continue
        inter_ranked.append((_edge_viz_weight(graph, u, v), u, v, cu, cv))
    inter_ranked.sort(key=lambda row: row[0], reverse=True)

    _viz_add_bridge_inter_cluster_edges(
        graph,
        visible,
        cluster_name,
        chosen,
        add,
        bridge_nodes,
        max_per_bridge=3,
    )

    if communities:
        _viz_add_grid_backbone_edges(
            graph,
            visible,
            communities,
            cluster_name,
            hub_nodes,
            bet,
            chosen,
            add,
        )

    pair_count: dict[tuple, int] = {}
    inter_added = 0
    max_per_pair = 3
    for _, u, v, cu, cv in inter_ranked:
        if inter_added >= max_inter:
            break
        pair = (cu, cv) if str(cu) <= str(cv) else (cv, cu)
        if pair_count.get(pair, 0) >= max_per_pair:
            continue
        add(u, v, True)
        pair_count[pair] = pair_count.get(pair, 0) + 1
        inter_added += 1

    priority_nodes = (hub_nodes | bridge_nodes) & visible
    _viz_ensure_incident_for_nodes(
        graph, visible, cluster_name, chosen, add, priority_nodes, max_per_node=2
    )
    _viz_extra_intra_for_isolates(
        graph, visible, cluster_name, chosen, add, per_node=2
    )
    _viz_ensure_connected_components(
        graph,
        visible,
        cluster_name,
        chosen,
        add,
        max_bridges=24,
    )
    _viz_fix_boundary_leaf_connectors(
        graph, visible, cluster_name, chosen, add, bridge_nodes
    )
    _viz_ensure_incident_for_nodes(
        graph, visible, cluster_name, chosen, add, visible, max_per_node=2
    )
    _viz_ensure_connected_components(
        graph,
        visible,
        cluster_name,
        chosen,
        add,
        max_bridges=24,
    )

    return edges_data


def _sna_scale(n_total: int) -> float:
    if n_total >= 1500:
        return 0.72
    if n_total >= 800:
        return 0.84
    if n_total >= 400:
        return 0.92
    return 1.0


def _sna_node_radius(tier: str, w_norm: float, n_total: int) -> float:
    """Hub ~10–14px, trung bình ~5–8px — dễ nhìn trên đồ thị đại diện."""
    scale = min(_sna_scale(n_total), 0.92)
    if tier == 'hub':
        return max(10.0, min(14.0, (10.0 + w_norm * 4.0) * scale))
    if tier == 'medium':
        return max(5.0, min(8.0, (5.0 + w_norm * 2.5) * scale))
    return max(3.5, min(5.5, (3.5 + w_norm * 1.8) * scale))


def _spread_representative_positions(
    positions: dict[int, tuple[float, float]],
    *,
    seed: int = 42,
) -> dict[int, tuple[float, float]]:
    """Bố trí nút đại diện trên vòng tròn + đẩy chồng — tọa độ chuẩn [-1,1]²."""
    keys = sorted(positions.keys())
    n = len(keys)
    if n <= 1:
        return positions
    rng = random.Random(seed)
    golden = 2.399963229728653
    out: dict[int, tuple[float, float]] = {}
    base_r = 0.72 + 0.08 * math.sqrt(n)
    for i, nid in enumerate(keys):
        ang = (2.0 * math.pi * i) / n - math.pi / 2 + rng.uniform(-0.06, 0.06)
        r = base_r * (0.92 + 0.08 * (i % 3))
        out[int(nid)] = (r * math.cos(ang), r * math.sin(ang))
    return _repel_overlaps(out, passes=40, min_dist_factor=3.6)


def _sna_node_opacity(tier: str, w_norm: float) -> float:
    if tier == 'hub':
        return 1.0
    if tier == 'medium':
        return 0.82
    return min(0.8, max(0.5, 0.52 + w_norm * 0.26))


def compute_risk(row):
    score = (
        row['betweenness_centrality'] * 1800
        + row['degree_centrality'] * 450
        + row['eigenvector_centrality'] * 900
    )
    if score >= 180:
        return 'High'
    if score >= 95:
        return 'Medium'
    if score >= 40:
        return 'Low'
    return 'Unknown'


def build_node_payload(
    users,
    metrics,
    graph,
    positions,
    hub_nodes=None,
    *,
    included_ids: Optional[Set[int]] = None,
    context_nodes: Optional[Set[int]] = None,
    bridge_nodes: Optional[Set[int]] = None,
    galaxy_mode: bool = False,
    graph_node_count: int = 0,
    test_style: bool = False,
):
    hub_nodes = hub_nodes or set()
    context_nodes = context_nodes or set()
    bridge_nodes = bridge_nodes or set()
    n_total = graph_node_count or (graph.number_of_nodes() if graph is not None else 0)
    payload = []
    
    # Rename metrics columns to standardized names
    metrics = metrics.rename(columns={
        'user_id': 'id',
        'betweenness_centrality': 'betweenness',
        'degree_centrality': 'degree',
        'eigenvector_centrality': 'eigenvector',
        'pagerank_centrality': 'pagerank',
        'pagerank': 'pagerank',
    })
    
    # Rename users columns if needed
    if 'user_id' in users.columns:
        users = users.rename(columns={'user_id': 'id'})
    
    # Standardize column names
    if 'followers_count' in users.columns:
        users = users.rename(columns={'followers_count': 'followers'})
    if 'posts_count' in users.columns:
        users = users.rename(columns={'posts_count': 'posts'})
    if 'shares_count' in users.columns:
        users = users.rename(columns={'shares_count': 'shares'})
    if 'comments_count' in users.columns:
        users = users.rename(columns={'comments_count': 'comments'})
    
    # Merge users and metrics
    info = users.merge(metrics, on='id', how='left')
    info = info.sort_values('betweenness', ascending=False)
    degree_map = dict(graph.degree())

    if 'pagerank' not in info.columns:
        info['pagerank'] = 0.0
    info['_viz_w'] = (
        info['betweenness'].fillna(0) * 4.0
        + info['degree'].fillna(0) * 1.25
        + info['eigenvector'].fillna(0) * 1.5
        + info['pagerank'].fillna(0) * 1.2
    )
    if included_ids is not None:
        info = info[info['id'].isin(included_ids)]
    if info.empty:
        return []
    w_series = info['_viz_w'].fillna(0)
    n_info = len(info)
    prominent_n = max(1, int(n_info * 0.08))
    medium_n = max(0, int(n_info * 0.12))
    ranked_df = info.sort_values('_viz_w', ascending=False)
    prominent_ids = {int(x) for x in ranked_df.head(prominent_n)['id']}
    medium_ids = {
        int(x) for x in ranked_df.iloc[prominent_n : prominent_n + medium_n]['id']
    }
    bt_q75 = float(info['betweenness'].fillna(0).quantile(0.75))
    deg_q70 = float(info['degree'].fillna(0).quantile(0.7))
    spotlight_take = max(5, min(8, len(info)))
    spotlight_ids = prominent_ids
    w_min = float(w_series.min()) if len(w_series) else 0.0
    w_max = float(w_series.max()) if len(w_series) else 1.0

    for _, row in info.iterrows():
        node_id = int(row['id'])
        if included_ids is not None and node_id not in included_ids:
            continue
        pos = positions.get(node_id, (0.0, 0.0))
        is_context = node_id in context_nodes

        # Handle different risk calculation methods
        if 'risk' in row and pd.notna(row['risk']):
            risk = str(row['risk'])
        else:
            # Calculate risk from metrics for generated data
            score = (
                row.get('betweenness', 0) * 1800
                + row.get('degree', 0) * 450
                + row.get('eigenvector', 0) * 900
                + row.get('pagerank', 0) * 800
            )
            if score >= 180:
                risk = 'High'
            elif score >= 95:
                risk = 'Medium'
            elif score >= 40:
                risk = 'Low'
            else:
                risk = 'Unknown'

        followers = int(row.get('followers', 0))
        posts = int(row.get('posts', 0))
        shares = int(row.get('shares', max(0, min(9999, followers * 0.15 + posts * 2))))
        comments = int(row.get('comments', max(0, min(9999, followers * 0.08 + posts * 1.1))))
        deg = float(degree_map.get(node_id, 0))
        w_norm = (float(row.get('_viz_w', 0) or 0) - w_min) / max(w_max - w_min, 1e-9)
        is_hub = node_id in hub_nodes
        is_bridge = node_id in bridge_nodes
        viz_tier = 'background'
        node_opacity = 0.65
        if test_style:
            viz_tier = 'background'
            radius = test_style_canvas_radius(n_total)
            node_opacity = 0.5 if n_total >= 2000 else 0.62
            show_label = False
            is_hub = False
            is_bridge = False
            is_context = False
        elif galaxy_mode:
            if is_hub or node_id in prominent_ids:
                viz_tier = 'hub'
                is_hub = True
                radius = _sna_node_radius('hub', w_norm, min(n_total, 200))
                node_opacity = 1.0
            else:
                viz_tier = 'medium'
                radius = _sna_node_radius('medium', w_norm, min(n_total, 200))
                node_opacity = _sna_node_opacity('medium', w_norm)
        elif is_context:
            radius = max(2.6, min(4.0, 2.8 + math.sqrt(max(0.0, deg)) * 0.14))
            is_hub = False
        elif is_hub:
            radius = min(22.0, 14.0 + math.sqrt(max(0.0, deg)) * 0.95)
        elif is_bridge:
            radius = min(15.0, 9.0 + math.sqrt(max(0.0, deg)) * 0.65)
        elif node_id in spotlight_ids:
            radius = min(12.0, 7.0 + math.sqrt(max(0.0, deg)) * 0.55)
        else:
            radius = max(4.0, min(9.0, 4.2 + w_norm * 4.5 + math.sqrt(max(0.0, deg)) * 0.22))
        is_spotlight = (not is_context) and (node_id in spotlight_ids)

        if not test_style:
            show_label = bool(
                not is_context
                and (
                    (galaxy_mode and viz_tier == 'hub')
                    or (galaxy_mode and risk == 'High' and viz_tier != 'background')
                    or is_bridge
                    or (not galaxy_mode and (is_hub or is_bridge))
                )
            )
        x_norm = float((pos[0] + 1) / 2)
        y_norm = float((pos[1] + 1) / 2)

        role_key = node_role_key(
            float(row.get('betweenness', 0) or 0),
            float(row.get('degree', 0) or 0),
            bt_q75=bt_q75,
            deg_q70=deg_q70,
        )
        payload.append({
            'id': node_id,
            'name': str(row.get('name', f'User {node_id}')),
            'role_key': role_key,
            'degree': deg,
            'degree_metric': float(row.get('degree', 0) or 0),
            'betweenness': float(row.get('betweenness', 0)),
            'eigenvector': float(row.get('eigenvector', 0)),
            'risk': risk,
            'risk_score': compute_risk_score(
                row.get('betweenness', 0),
                row.get('degree', 0),
                row.get('eigenvector', 0),
            ),
            'cluster': None,
            'cluster_hub': bool(is_hub),
            'viz_spotlight': bool(is_spotlight),
            'viz_context': bool(is_context),
            'viz_bridge': bool(is_bridge),
            'show_label': show_label,
            'followers': followers,
            'posts': posts,
            'shares': shares,
            'comments': comments,
            'x': int(100 + 700 * x_norm),
            'y': int(80 + 380 * y_norm),
            'x_norm': round(x_norm, 5),
            'y_norm': round(y_norm, 5),
            'radius': radius,
            'influence': round(float(w_norm), 4),
            'viz_tier': viz_tier,
            'opacity': round(float(node_opacity), 3),
            'color': TEST_STYLE_NODE_COLOR if test_style else '#94a3b8',
        })
    return payload


def _nodes_metrics_rows(users: pd.DataFrame, metrics: pd.DataFrame, graph: nx.Graph) -> list:
    """Mọi nút kèm chỉ số trung tâm — dùng xếp hạng Top-k và chỉnh trọng số phía client."""
    m = metrics.rename(
        columns={
            'user_id': 'id',
            'betweenness_centrality': 'betweenness',
            'degree_centrality': 'degree',
            'eigenvector_centrality': 'eigenvector',
        }
    )
    u = users.copy()
    if 'user_id' in u.columns:
        u = u.rename(columns={'user_id': 'id'})
    info = u.merge(m, on='id', how='left')
    for c in ('betweenness', 'degree', 'eigenvector', 'pagerank'):
        if c not in info.columns:
            info[c] = 0.0
        info[c] = pd.to_numeric(info[c], errors='coerce').fillna(0.0)

    info['id'] = info['id'].astype(np.int64)
    degree_map = dict(graph.degree())
    info['degree_graph'] = info['id'].map(degree_map).fillna(info['degree']).astype(float)

    bt = info['betweenness'].astype(float)
    deg_c = info['degree'].astype(float)
    ev = info['eigenvector'].astype(float)
    pr = info['pagerank'].astype(float)
    bt_q75 = float(bt.quantile(0.75))
    deg_q70 = float(deg_c.quantile(0.7))

    legacy_score = bt * 1800 + deg_c * 450 + ev * 900
    computed_risk = np.where(
        legacy_score >= 180,
        'High',
        np.where(legacy_score >= 95, 'Medium', np.where(legacy_score >= 40, 'Low', 'Unknown')),
    )
    if 'risk' in info.columns:
        has_risk = info['risk'].notna()
        risk_arr = np.where(has_risk, info['risk'].astype(str).to_numpy(), computed_risk)
    else:
        risk_arr = computed_risk

    role_arr = np.where(
        bt >= bt_q75,
        'bridge',
        np.where(deg_c >= deg_q70, 'spreader', 'observer'),
    )
    if 'name' in info.columns:
        names = info['name'].fillna('').astype(str)
        names = np.where(names != '', names, 'User ' + info['id'].astype(str))
    else:
        names = 'User ' + info['id'].astype(str)

    out = [
        {
            'id': int(nid),
            'name': str(nm),
            'role_key': str(role),
            'degree': float(deg_g),
            'degree_metric': float(deg_m),
            'betweenness': float(b),
            'eigenvector': float(e),
            'pagerank': float(p),
            'risk': str(rk),
            'risk_score': 0,
        }
        for nid, nm, role, deg_g, deg_m, b, e, p, rk in zip(
            info['id'].to_numpy(),
            names,
            role_arr,
            info['degree_graph'].to_numpy(),
            deg_c.to_numpy(),
            bt.to_numpy(),
            ev.to_numpy(),
            pr.to_numpy(),
            risk_arr,
        )
    ]
    apply_normalized_risk_scores(out)
    return out


def _top_nodes_payload(users: pd.DataFrame, metrics: pd.DataFrame, graph: nx.Graph, limit: int = 10) -> list:
    """Top nút theo điểm nguy cơ (mặc định trọng số betweenness/degree/eigenvector)."""
    rows = _nodes_metrics_rows(users, metrics, graph)
    rows.sort(key=lambda x: x['risk_score'], reverse=True)
    return rows[:limit]


def node_role_key(
    betweenness: float,
    degree: float,
    *,
    bt_q75: float,
    deg_q70: float,
) -> str:
    """Mã vai trò nút (dịch phía client qua i18n roles.*)."""
    if betweenness >= bt_q75:
        return 'bridge'
    if degree >= deg_q70:
        return 'spreader'
    return 'observer'


def classify_risk_from_metrics(bt: float, dg: float, ev: float) -> str:
    score = bt * 1800 + dg * 450 + ev * 900
    if score >= 180:
        return 'High'
    if score >= 95:
        return 'Medium'
    if score >= 40:
        return 'Low'
    return 'Unknown'


def empty_graph_payload() -> dict:
    """Khi chưa có thư mục output_* — tránh 500 cho dashboard."""
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        'ready': False,
        'output_folder': None,
        'nodes': 0,
        'edges': 0,
        'data_date': str(datetime.date.today()),
        'status': 'Chưa có dữ liệu mạng',
        'version': '1.0.0',
        'timestamp': ts,
        'nodes_data': [],
        'edges_data': [],
        'top_nodes': [],
        'ranking_nodes': [],
        'clusters': [],
        'hint': 'Bấm «Tạo dữ liệu» để sinh thư mục trong outputs/ (users.csv, relationships.csv, metrics.csv).',
    }


def _normalize_viz_mode(viz: Optional[str]) -> str:
    key = (viz or 'summary').strip().lower()
    if key in ('dense', 'test', 'testpy'):
        return 'dense'
    if key in ('full', 'all', 'entire', 'complete', 'galaxy'):
        return 'full'
    return 'summary'


def _viz_all_edges_payload(
    graph: nx.Graph,
    visible: Set[int],
    cluster_name_by_id: dict[int, str],
    cluster_color_by_id: dict[int, str],
    *,
    max_edges: int = GALAXY_MAX_EDGES,
) -> list:
    """Toàn bộ cạnh trong tập nút hiển thị (hoặc lấy mẫu nếu vượt ngưỡng)."""
    sub = graph.subgraph(visible)
    n_e = sub.number_of_edges()
    if n_e <= max_edges:
        out: list = []
        for u, v in sub.edges():
            u, v = int(u), int(v)
            cu, cv = cluster_name_by_id.get(u), cluster_name_by_id.get(v)
            inter = cu is not None and cv is not None and cu != cv
            col = cluster_color_by_id.get(u) or cluster_color_by_id.get(v) or '#94a3b8'
            out.append(
                {
                    'source': u,
                    'target': v,
                    'inter_cluster': bool(inter),
                    'color': col,
                }
            )
        return out
    ranked: list = []
    for u, v in sub.edges():
        u, v = int(u), int(v)
        w = _edge_viz_weight(graph, u, v)
        ranked.append((w, u, v))
    ranked = heapq.nlargest(
        max_edges,
        ranked,
        key=lambda row: row[0],
    )
    out = []
    for _, u, v in ranked:
        cu, cv = cluster_name_by_id.get(u), cluster_name_by_id.get(v)
        inter = cu is not None and cv is not None and cu != cv
        col = cluster_color_by_id.get(u) or cluster_color_by_id.get(v) or '#94a3b8'
        out.append(
            {
                'source': u,
                'target': v,
                'inter_cluster': bool(inter),
                'color': col,
            }
        )
    return out


def build_graph_payload(*, viz: str = 'summary', output_dir: Optional[str] = None):
    global _cached_graph, _cached_payload_by_viz, _cached_output
    viz_key = _normalize_viz_mode(viz)
    folder = resolve_output_folder(output_dir)
    if folder is None or not folder.exists():
        logger.warning('Chưa có bộ dữ liệu output')
        return empty_graph_payload()

    if _cached_output == folder and viz_key in _cached_payload_by_viz:
        return _cached_payload_by_viz[viz_key]

    try:
        folder, users, relationships, metrics = load_output_data(output_dir)
    except FileNotFoundError as e:
        logger.warning('Chưa có bộ dữ liệu output: %s', e)
        return empty_graph_payload()

    if _cached_output == folder and _cached_graph is not None:
        graph = _cached_graph
    else:
        graph = create_graph(users, relationships)
        _cached_graph = graph
        _cached_output = folder

    n_total_early = graph.number_of_nodes()
    if use_fast_graph_algorithms(n_total_early):
        logger.info('Phân cụm nhanh (một cụm) cho mạng %s nút trên server / mạng lớn', n_total_early)
        communities = [set(graph.nodes())] if n_total_early else []
    else:
        try:
            communities = list(nx.community.greedy_modularity_communities(graph))
        except Exception as exc:
            logger.warning('greedy_modularity_communities failed (%s); single cluster', exc)
            communities = [set(graph.nodes())] if n_total_early else []

    communities = sorted(communities, key=lambda c: (-len(c), min(c)))

    metrics_norm = _metrics_layout_frame(metrics)
    hub_nodes = _select_cluster_hubs(graph, communities, metrics_norm)
    bet, _, _, pr = _centrality_maps(metrics_norm, graph)
    centers = _community_center_nodes(graph, communities, bet)
    n_total = graph.number_of_nodes()

    cluster_map: dict[int, dict] = {}
    cluster_items = []
    for index, community in enumerate(communities):
        color = CLUSTER_COLORS[index % len(CLUSTER_COLORS)]
        cluster_name = f'Cụm {index + 1}'
        for node in community:
            cluster_map[node] = {'name': cluster_name, 'color': color}
        if index < 8:
            cluster_items.append({'name': cluster_name, 'color': color, 'count': len(community)})

    cluster_name_by_id = {nid: cluster_map[nid]['name'] for nid in cluster_map}

    force_full = viz_key == 'full'
    force_dense = viz_key == 'dense'
    use_test_viz = force_dense or (viz_key == 'summary' and n_total >= TEST_STYLE_MIN_NODES)

    if force_full or use_test_viz:
        all_ids = {int(v) for v in graph.nodes()}
        if len(all_ids) > GALAXY_MAX_NODES:
            _, eig, deg, pr = _centrality_maps(metrics_norm, graph)
            ranked = sorted(
                all_ids,
                key=lambda nid: _viz_score(nid, bet, eig, deg, pr),
                reverse=True,
            )
            visible_ids = set(ranked[:GALAXY_MAX_NODES])
        else:
            visible_ids = all_ids
        representative_mode = False
        context_ids: Set[int] = set()
        bridge_ids = (
            set()
            if use_test_viz
            else _select_bridge_nodes(
                graph, visible_ids, cluster_name_by_id, bet, limit=24
            )
        )
        primary_ids = visible_ids
    else:
        primary_ids, context_ids, bridge_ids = _select_viz_node_sets(
            graph, communities, metrics_norm, hub_nodes, cluster_name_by_id
        )
        visible_ids = primary_ids | (hub_nodes & set(graph.nodes()))
        visible_ids |= _expand_visible_for_local_neighbors(
            graph, visible_ids, bet, max_expansions=8
        )
        representative_mode = n_total > len(visible_ids)

    layout_node_set = visible_ids if visible_ids else {int(v) for v in graph.nodes()}
    layout_graph = (
        graph.subgraph(layout_node_set).copy()
        if len(layout_node_set) < n_total
        else graph
    )
    layout_comms = _communities_for_nodes(communities, set(layout_graph.nodes()))
    hubs_vis = hub_nodes & set(layout_graph.nodes())
    used_cluster_grid = len(layout_comms) >= 2 and not force_full and not use_test_viz

    if use_test_viz:
        positions = layout_for_network_draw(layout_graph, seed=42)
        positions = normalize_positions_to_unit(positions)
        positions = _repel_overlaps(positions, passes=14, min_dist_factor=1.15)
    elif used_cluster_grid:
        positions = cluster_focus_layout(
            layout_graph, layout_comms, hubs_vis, seed=42
        )
    else:
        layout_pull = _layout_priority_nodes(metrics_norm, k=8 if force_full else 6)
        positions = dashboard_spring_layout(
            layout_graph, center_nodes=layout_pull, seed=42
        )

    n_vis = len(layout_node_set)
    if representative_mode:
        if used_cluster_grid:
            # Giữ lưới cụm — chỉ xử lý chồng nhẹ, không dàn đều toàn mạng
            positions = _repel_overlaps(
                positions, passes=22, min_dist_factor=2.6
            )
        else:
            positions = polish_representative_layout(
                layout_graph,
                positions,
                iterations=58,
                edge_ideal_frac=0.072,
                min_sep_factor=7.8,
            )
            positions = _repel_overlaps(
                positions, passes=64, min_dist_factor=5.5
            )
    else:
        if force_full and n_vis > 200:
            repel_passes, repel_factor = 28, 2.4
        else:
            repel_passes = 72 if n_vis <= 40 else 56
            repel_factor = 4.8 if n_vis <= 40 else 3.2
        positions = _repel_overlaps(
            positions, passes=repel_passes, min_dist_factor=repel_factor
        )
    node_payload = build_node_payload(
        users,
        metrics,
        graph,
        positions,
        hub_nodes=hub_nodes,
        included_ids=visible_ids if visible_ids else None,
        context_nodes=context_ids,
        bridge_nodes=bridge_ids,
        galaxy_mode=force_full or representative_mode or n_total <= GALAXY_MAX_NODES,
        graph_node_count=n_total,
        test_style=use_test_viz,
    )

    for node in node_payload:
        node_cluster = cluster_map.get(node['id'], {'name': 'Chưa xác định', 'color': '#8b95a8'})
        node['cluster'] = node_cluster['name']
        node['cluster_color'] = node_cluster['color']
        node['color'] = node_cluster['color']
        rk = str(node.get('risk', 'Unknown'))
        if use_test_viz:
            fill = TEST_STYLE_NODE_COLOR
            node['node_fill'] = fill
            node['risk_fill'] = fill
            node['color'] = fill
            node['opacity'] = round(
                float(node.get('opacity') or (0.5 if n_total >= 2000 else 0.62)), 3
            )
        elif representative_mode:
            fill = cluster_node_fill(
                node_cluster['color'],
                rk,
                is_hub=bool(node.get('cluster_hub')),
                is_context=False,
            )
        elif force_full or n_total <= GALAXY_MAX_NODES:
            fill = RISK_COLORS.get(rk, RISK_COLORS['Unknown'])
        else:
            fill = cluster_node_fill(
                node_cluster['color'],
                rk,
                is_hub=bool(node.get('cluster_hub')),
                is_context=bool(node.get('viz_context')),
            )
        node['node_fill'] = fill
        node['risk_fill'] = fill
        node['color'] = fill

    edge_visible = visible_ids if visible_ids else set(graph.nodes())
    cluster_color_by_id = {
        int(nid): cluster_map[nid]['color'] for nid in cluster_map if nid in edge_visible
    }
    if force_full or use_test_viz:
        edges_payload = _viz_all_edges_payload(
            graph,
            edge_visible,
            cluster_name_by_id,
            {nid: TEST_STYLE_EDGE_COLOR for nid in edge_visible},
            max_edges=GALAXY_MAX_EDGES,
        )
    elif representative_mode:
        n_clusters = max(1, len(cluster_items))
        max_inter = min(18, 6 + n_clusters * 2)
        edges_payload = _viz_edges_clean_representative(
            graph,
            edge_visible,
            cluster_name_by_id,
            cluster_color_by_id,
            hub_nodes,
            bridge_nodes=bridge_ids,
            communities=communities,
            bet=bet,
            max_inter=max_inter,
            extra_intra_per_hub=1,
            extra_intra_per_cluster=1,
        )
        edges_payload = _ensure_viz_payload_connected(
            graph,
            edge_visible,
            edges_payload,
            cluster_name_by_id,
        )
        if edges_payload:
            g_check = nx.Graph()
            for e in edges_payload:
                g_check.add_edge(int(e['source']), int(e['target']))
            for nid in edge_visible:
                g_check.add_node(nid)
            n_comps = len(list(nx.connected_components(g_check)))
            if n_comps != 1:
                logger.warning(
                    'Representative viz still has %d components after repair; forcing bridges',
                    n_comps,
                )
                edges_payload = _ensure_viz_payload_connected(
                    graph,
                    edge_visible,
                    edges_payload,
                    cluster_name_by_id,
                    max_repairs=64,
                )
        if edges_payload:
            backbone = nx.Graph()
            inter_edge_keys: set[tuple[int, int]] = set()
            for e in edges_payload:
                u, v = int(e['source']), int(e['target'])
                backbone.add_edge(u, v)
                if e.get('inter_cluster'):
                    inter_edge_keys.add((u, v))
                    inter_edge_keys.add((v, u))
            positions = polish_representative_layout(
                backbone,
                positions,
                iterations=24,
                edge_ideal_frac=0.085,
                min_sep_factor=7.8,
                inter_edge_keys=inter_edge_keys,
            )
            positions = _repel_overlaps(
                positions, passes=32, min_dist_factor=5.5
            )
            for node in node_payload:
                nid = node['id']
                if nid in positions:
                    px, py = positions[nid]
                    node['x_norm'] = round(float((px + 1) / 2), 5)
                    node['y_norm'] = round(float((py + 1) / 2), 5)
                    node['x'] = int(100 + 700 * node['x_norm'])
                    node['y'] = int(80 + 380 * node['y_norm'])
    elif n_total > 20 or graph.number_of_edges() > 80:
        max_e = min(140, max(24, int(len(edge_visible) * 2.2)))
        edges_payload = _viz_edges_payload(
            graph,
            edge_visible,
            hub_nodes,
            centers,
            cluster_name_by_id,
            bridge_nodes=bridge_ids,
            max_edges=max_e,
        )
    else:
        edges_payload = []
        for _, row in relationships.iterrows():
            u, v = int(row['source']), int(row['target'])
            if u not in edge_visible or v not in edge_visible:
                continue
            cu, cv = cluster_name_by_id.get(u), cluster_name_by_id.get(v)
            inter = cu is not None and cv is not None and cu != cv
            if inter and u not in bridge_ids and v not in bridge_ids:
                continue
            col = cluster_color_by_id.get(u) or cluster_color_by_id.get(v) or '#94a3b8'
            edges_payload.append(
                {
                    'source': u,
                    'target': v,
                    'inter_cluster': bool(inter),
                    'color': col,
                }
            )

    ranking_nodes = _nodes_metrics_rows(users, metrics, graph)
    risk_by_id = {int(r['id']): r for r in ranking_nodes}
    for node in node_payload:
        rid = int(node['id'])
        if rid in risk_by_id:
            node['risk_score'] = risk_by_id[rid]['risk_score']
            node['risk'] = risk_by_id[rid]['risk']
    top_nodes = sorted(ranking_nodes, key=lambda x: x['risk_score'], reverse=True)[:10]
    n_viz = len(node_payload)
    if use_test_viz:
        viz_mode = 'dense' if n_viz >= n_total else 'dense_capped'
    elif force_full:
        viz_mode = 'full' if n_viz >= n_total else 'full_capped'
    else:
        viz_mode = 'summary' if representative_mode else ('full' if n_viz >= n_total else 'summary')

    payload = {
        'ready': True,
        'output_folder': folder.name,
        'nodes': len(users),
        'edges': len(relationships),
        'data_date': dataset_data_date(folder),
        'status': 'Dữ liệu đã sẵn sàng',
        'version': '1.0.0',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'nodes_data': node_payload,
        'edges_data': edges_payload,
        'top_nodes': top_nodes,
        'ranking_nodes': ranking_nodes,
        'clusters': cluster_items,
        'viz_mode': viz_mode,
        'viz_engine': 'force-sna',
        'viz_representative': representative_mode,
        'viz_test_style': use_test_viz,
        'viz_cluster_layout': used_cluster_grid,
        'viz_nodes_shown': n_viz,
        'viz_nodes_total': n_total,
        'viz_edges_shown': len(edges_payload),
        'viz_edges_total': int(graph.subgraph(edge_visible).number_of_edges()) if edge_visible else 0,
    }
    _cached_payload_by_viz[viz_key] = payload
    return payload


@app.route('/')
def index():
    return send_from_directory(str(HTML_DIR), 'index.html')


@app.route('/graph')
def graph_page():
    return send_from_directory(str(HTML_DIR), 'graph.html')


@app.route('/simulation')
def simulation_page():
    return send_from_directory(str(HTML_DIR), 'simulation.html')


@app.route('/recommendations')
def recommendations_page():
    return send_from_directory(str(HTML_DIR), 'recommendations.html')


@app.route('/api/config')
def api_config():
    """Cấu hình UI: giới hạn user, có vẽ PNG matplotlib hay không."""
    on_render = on_render_deploy()
    skip_viz = skip_heavy_viz()
    max_u = max_users_limit()
    return jsonify({
        'on_render': on_render,
        'skip_graph_viz': skip_viz,
        'viz_png_enabled': not skip_viz,
        'max_users': max_u,
        'hint_generate': (
            f'Tối đa {max_u} user. Server không lưu PNG matplotlib; biểu đồ web vẫn dùng dữ liệu CSV.'
            if skip_viz
            else f'Tối đa {max_u} user. Máy local: lưu thêm graph_visualization.png.'
        ),
    })


@app.route('/api/summary')
def api_summary():
    try:
        output_dir = request.args.get('output_dir')
        payload = build_dataset_summary(output_dir=output_dir)
    except Exception as e:
        logger.exception('api_summary: build_dataset_summary failed')
        payload = empty_graph_payload()
        payload['hint'] = (
            f'Lỗi khi đọc dữ liệu: {str(e)}. '
            'Thử bấm «Tạo dữ liệu» lại hoặc chọn lại bộ output.'
        )
    return json_safe_response({
        'ready': payload.get('ready', True),
        'nodes': payload['nodes'],
        'edges': payload['edges'],
        'interaction_type': 'Share/Comment',
        'data_date': payload['data_date'],
        'status': payload['status'],
        'version': payload['version'],
        'timestamp': payload['timestamp'],
        'output_folder': payload.get('output_folder'),
        'hint': payload.get('hint'),
    })


@app.route('/api/graph-png')
def api_graph_png():
    """Ảnh matplotlib đã lưu (graph_visualization.png) — cùng kiểu Test.py."""
    try:
        output_dir = request.args.get('output_dir')
        folder = resolve_output_folder(output_dir) if output_dir else get_latest_output_dir()
        if folder is None:
            return jsonify({'error': 'Không tìm thấy thư mục output'}), 404
        png_path = folder / 'graph_visualization.png'
        if not png_path.is_file():
            return jsonify({'error': 'Chưa có graph_visualization.png — tạo mạng trên máy local.'}), 404
        return send_file(png_path, mimetype='image/png', max_age=0)
    except Exception as e:
        logger.exception('api_graph_png failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/graph')
def api_graph():
    if request.args.get('refresh'):
        global _cached_payload_by_viz, _cached_graph
        _cached_payload_by_viz = {}
        _cached_graph = None
    viz = request.args.get('viz', 'summary')
    try:
        output_dir = request.args.get('output_dir')
        payload = build_graph_payload(viz=viz, output_dir=output_dir)
        return json_safe_response(payload)
    except Exception as e:
        logger.exception('api_graph: build_graph_payload failed')
        p = empty_graph_payload()
        p['hint'] = (
            f'Lỗi khi dựng đồ thị: {str(e)}. '
            'Thử «Tạo dữ liệu» lại hoặc giảm số user; trên Render cần có scipy trong requirements.txt.'
        )
        p['error'] = str(e)
        return json_safe_response(p)


@app.route('/api/top-nodes')
def api_top_nodes():
    try:
        payload = build_graph_payload()
        return jsonify({'top_nodes': payload['top_nodes']})
    except Exception as e:
        logger.error(f'Error in api_top_nodes: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/node/<int:node_id>')
def api_node(node_id):
    try:
        payload = build_graph_payload()
        node = next((item for item in payload['nodes_data'] if item['id'] == node_id), None)
        if node is None:
            abort(404, description='Node không tồn tại')
        return jsonify(node)
    except Exception as e:
        logger.error(f'Error in api_node: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/clusters')
def api_clusters():
    try:
        payload = build_graph_payload()
        return jsonify({'clusters': payload['clusters']})
    except Exception as e:
        logger.error(f'Error in api_clusters: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/run-generator', methods=['POST'])
def api_run_generator():
    try:
        payload = request.get_json() or {}
        num_users = int(payload.get('num_users', 500))
        relationship_prob = float(payload.get('relationship_prob', 0.025))
        seed = int(payload.get('seed', 42))

        max_users = max_users_limit()
        if num_users < 10 or num_users > max_users:
            hint = (
                f'Tối đa {max_users} user trên server (không vẽ PNG, dùng betweenness xấp xỉ).'
                if skip_heavy_viz()
                else f'Tối đa {max_users} user.'
            )
            return json_safe_response(
                {
                    'error': f'Số người dùng phải từ 10 đến {max_users}.',
                    'hint': hint,
                },
                400,
            )

        generator = SocialNetworkGenerator(num_users=num_users, seed=seed)
        generator.run(num_users=num_users, relationship_prob=relationship_prob)

        _invalidate_graph_cache()

        folder = Path(generator.output_dir)
        _, users, relationships, metrics = load_output_data(str(folder))
        graph = create_graph(users, relationships)
        top_nodes = _top_nodes_payload(users, metrics, graph, 10)

        return json_safe_response({
            'output_folder': str(folder.resolve()),
            'nodes': int(graph.number_of_nodes()),
            'edges': int(graph.number_of_edges()),
            'top_nodes': top_nodes,
        })
    except MemoryError:
        logger.exception('api_run_generator OOM')
        return json_safe_response(
            {
                'error': 'Hết bộ nhớ khi tạo dữ liệu.',
                'hint': f'Giảm số user (ví dụ ≤ {max(500, max_users_limit() // 2)}) rồi thử lại.',
            },
            500,
        )
    except Exception as e:
        logger.exception('api_run_generator failed')
        hint = (
            f'Giảm số user hoặc tăng timeout Render. Giới hạn hiện tại: {max_users_limit()}.'
            if on_render_deploy()
            else None
        )
        body = {'error': f'Lỗi tạo dữ liệu: {str(e)}'}
        if hint:
            body['hint'] = hint
        return json_safe_response(body, 500)


@app.route('/api/run-simulate', methods=['POST'])
def api_run_simulate():
    try:
        payload = request.get_json() or {}
        model = payload.get('model', 'pure')
        output_dir = payload.get('output_dir')
        transmission_rate = float(payload.get('transmission_rate', 0.3))
        recovery_rate = float(payload.get('recovery_rate', 0.02))
        days = int(payload.get('days', 300))
        seed = int(payload.get('seed', 42))
        misinfo_source_mode = normalize_misinfo_mode(payload.get('misinfo_source_mode', 'random'))
        num_initial_sources = max(1, int(payload.get('num_initial_sources', 1)))

        if model == 'dynamic':
            top_k = int(payload.get('top_k', 10))
            strategy = (payload.get('strategy') or 'betweenness').strip().lower()
            intervention_day = int(payload.get('intervention_day', 1))
            sim = SIRDynamicImmunization(
                output_dir=output_dir,
                top_k=top_k,
                strategy=strategy,
                intervention_day=intervention_day,
                misinfo_source_mode=misinfo_source_mode,
            )
            sim.simulate(
                transmission_rate=transmission_rate,
                recovery_rate=recovery_rate,
                days=days,
                seed=seed,
                misinfo_source_mode=misinfo_source_mode,
                num_initial_sources=num_initial_sources,
            )
            peak_day, peak_I, final_day, total_inf, never_inf = sim.get_statistics()
            return jsonify({
                'model': 'dynamic',
                'strategy': sim.strategy,
                'top_k': sim.top_k,
                'intervention_day': sim.intervention_day,
                'misinfo_source_mode': getattr(sim, 'misinfo_source_mode', misinfo_source_mode),
                'misinfo_source_node_ids': [
                    int(x) for x in getattr(sim, 'initial_infected_nodes', [])
                ],
                'output_directory': sim.results_dir,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'total_infected': total_inf,
                'never_infected': never_inf,
            })

        sim = PureSIRSimulation(output_dir=output_dir)
        sim.simulate(
            transmission_rate=transmission_rate,
            recovery_rate=recovery_rate,
            max_days=days,
            seed=seed,
            misinfo_source_mode=misinfo_source_mode,
            num_initial_sources=num_initial_sources,
        )
        peak_day, peak_I, final_day, total_inf, never_inf = sim.get_statistics()
        sim.save()
        return jsonify({
            'model': 'pure',
            'misinfo_source_mode': getattr(sim, 'misinfo_source_mode', misinfo_source_mode),
            'misinfo_source_node_ids': [
                int(x) for x in getattr(sim, 'initial_infected_nodes', [])
            ],
            'output_directory': sim.results_dir,
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
            'total_infected': total_inf,
            'never_infected': never_inf,
        })
    except Exception as e:
        logger.error(f'Error in api_run_simulate: {e}')
        return jsonify({'error': f'Lỗi mô phỏng: {str(e)}'}), 500


@app.route('/api/simulate-sir', methods=['POST'])
def api_simulate_sir():
    try:
        payload = request.get_json(silent=True) or {}
        if payload.get('action') == 'export_pdf':
            return _handle_sir_export_pdf(payload)
        model = payload.get('model', 'pure')
        folder, users, relationships, _metrics = load_output_data(payload.get('output_dir'))
        global _cached_graph, _cached_output
        if _cached_output == folder and _cached_graph is not None:
            graph = _cached_graph
        else:
            graph = create_graph(users, relationships)
            _cached_graph = graph
            _cached_output = folder
        n_nodes = int(graph.number_of_nodes())
        n_edges = int(graph.number_of_edges())
        logger.info(
            'simulate-sir: dataset=%s nodes=%s edges=%s model=%s requested=%s',
            folder.name,
            n_nodes,
            n_edges,
            model,
            payload.get('output_dir') or '(latest)',
        )
        transmission_rate = float(payload.get('transmission_rate', 0.3))
        recovery_rate = float(payload.get('recovery_rate', 0.1))
        days = int(payload.get('days', 300))
        seed = int(payload.get('seed', 42))
        misinfo_source_mode = normalize_misinfo_mode(payload.get('misinfo_source_mode', 'random'))
        num_initial_sources = max(1, int(payload.get('num_initial_sources', 1)))

        if model == 'dynamic':
            top_k = int(payload.get('top_k', 10))
            strategy = (payload.get('strategy') or 'betweenness').strip().lower()
            intervention_day = int(payload.get('intervention_day', 1))
            sim = SIRDynamicImmunization(
                output_dir=str(folder),
                top_k=top_k,
                strategy=strategy,
                intervention_day=intervention_day,
                misinfo_source_mode=misinfo_source_mode,
                graph=graph,
                users=users,
                relationships=relationships,
            )
            sim.simulate(
                transmission_rate=transmission_rate,
                recovery_rate=recovery_rate,
                days=days,
                seed=seed,
                misinfo_source_mode=misinfo_source_mode,
                num_initial_sources=num_initial_sources,
            )
            peak_day, peak_I, final_day, total_inf, never_inf = sim.get_statistics()
            hist = sim.history.to_dict(orient='records')
            imm = [int(x) for x in sim.immunized_nodes]
            init_ids = [int(x) for x in getattr(sim, 'initial_infected_nodes', [])]
            init_detail = misinfo_source_labels(init_ids, users)
            _recommendations_cache.pop(str(folder.resolve()), None)
            return jsonify({
                'model': 'dynamic',
                'output_folder': folder.name,
                'nodes': n_nodes,
                'edges': n_edges,
                'strategy': sim.strategy,
                'top_k': sim.top_k,
                'intervention_day': sim.intervention_day,
                'misinfo_source_mode': getattr(sim, 'misinfo_source_mode', misinfo_source_mode),
                'misinfo_source_node_ids': init_ids,
                'misinfo_source_nodes': init_detail,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'total_infected': total_inf,
                'never_infected': never_inf,
                'history': hist,
                'output_directory': sim.results_dir,
                'immunized_node_ids': imm,
            })

        sim = PureSIRSimulation(
            output_dir=str(folder),
            graph=graph,
            users=users,
            relationships=relationships,
        )
        sim.simulate(
            transmission_rate=transmission_rate,
            recovery_rate=recovery_rate,
            max_days=days,
            seed=seed,
            misinfo_source_mode=misinfo_source_mode,
            num_initial_sources=num_initial_sources,
        )
        peak_day, peak_I, final_day, total_inf, never_inf = sim.get_statistics()
        sim.save()
        hist = sim.history.to_dict(orient='records')
        init_ids = [int(x) for x in getattr(sim, 'initial_infected_nodes', [])]
        init_detail = misinfo_source_labels(init_ids, users)
        _recommendations_cache.pop(str(folder.resolve()), None)
        return jsonify({
            'model': 'pure',
            'output_folder': folder.name,
            'nodes': n_nodes,
            'edges': n_edges,
            'misinfo_source_mode': getattr(sim, 'misinfo_source_mode', misinfo_source_mode),
            'misinfo_source_node_ids': init_ids,
            'misinfo_source_nodes': init_detail,
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
            'total_infected': total_inf,
            'never_infected': never_inf,
            'history': hist,
            'output_directory': sim.results_dir,
        })
    except Exception as e:
        logger.error(f'Error in api_simulate_sir: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/sir-results', methods=['GET'])
def api_sir_results():
    try:
        output_dir = request.args.get('output_dir')
        model = request.args.get('model', 'pure')
        folder = resolve_output_folder(output_dir) if output_dir else get_latest_output_dir()
        if folder is None or not folder.exists():
            return jsonify({'error': 'Không tìm thấy thư mục output'}), 404

        misinfo_q = normalize_misinfo_mode(request.args.get('misinfo_source_mode', 'random'))

        if model == 'dynamic':
            strat_q = (request.args.get('strategy') or 'betweenness').strip().lower()
            if strat_q not in DYNAMIC_STRATEGIES:
                strat_q = 'betweenness'
            intervention_day = int(request.args.get('intervention_day', 1))
            top_k_arg = request.args.get('top_k')
            top_k = int(top_k_arg) if top_k_arg not in (None, '') else None
            hist_path = find_dynamic_sir_history_csv(
                folder, strat_q, intervention_day, top_k, misinfo_q
            )
        else:
            strat_q = None
            intervention_day = None
            hist_path = find_pure_sir_history_csv(folder, misinfo_q)

        if hist_path is None:
            return jsonify({'error': 'Chưa có sir_history.csv'}), 404

        df = pd.read_csv(hist_path)
        users_csv = folder / 'users.csv'
        users_df = pd.read_csv(users_csv) if users_csv.exists() else None
        n_nodes = (
            len(users_df)
            if users_df is not None
            else int(df['S'].iloc[0] + df['I'].iloc[0] + df['R'].iloc[0])
        )
        peak_day, peak_I, final_day, total_inf, never_inf = sir_metrics_from_history_df(df, n_nodes)

        payload = {
            'history': df.to_dict(orient='records'),
            'statistics': {
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'total_infected': total_inf,
                'never_infected': never_inf,
            },
            'output_directory': str(hist_path.parent.resolve()),
            'misinfo_source_mode': misinfo_q,
        }
        mis_path = hist_path.parent / 'misinfo_source.json'
        if mis_path.is_file():
            try:
                with open(mis_path, encoding='utf-8') as f:
                    mj = json.load(f)
                if mj.get('misinfo_source_mode'):
                    payload['misinfo_source_mode'] = normalize_misinfo_mode(
                        str(mj['misinfo_source_mode'])
                    )
                init_ids = [int(x) for x in mj.get('node_ids', [])]
                if users_df is not None and init_ids:
                    payload['misinfo_source_node_ids'] = init_ids
                    payload['misinfo_source_nodes'] = misinfo_source_labels(init_ids, users_df)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                pass
        if model == 'dynamic':
            payload['strategy'] = strat_q
            payload['intervention_day'] = intervention_day
            mj_path = hist_path.parent / 'immunized_nodes.json'
            if mj_path.exists():
                try:
                    with open(mj_path, encoding='utf-8') as f:
                        mj = json.load(f)
                    if mj.get('top_k') is not None:
                        payload['top_k'] = mj.get('top_k')
                    if mj.get('strategy'):
                        payload['strategy'] = str(mj.get('strategy')).strip().lower()
                    if mj.get('intervention_day') is not None:
                        payload['intervention_day'] = int(mj.get('intervention_day'))
                    if mj.get('misinfo_source_mode'):
                        payload['misinfo_source_mode'] = normalize_misinfo_mode(
                            str(mj['misinfo_source_mode'])
                        )
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass

        return jsonify(payload)
    except Exception as e:
        logger.error(f'Error in api_sir_results: {e}')
        return jsonify({'error': str(e)}), 500


def _sir_export_pdf_response(
    folder_label: str,
    pure: Optional[dict],
    dynamic_runs: list,
    lang: str,
    recommendations: Optional[dict] = None,
):
    if not pure and not dynamic_runs:
        err = 'No simulation results to export.' if lang == 'en' else 'Chưa có kết quả mô phỏng để xuất.'
        return jsonify({'error': err}), 400
    pdf_bytes = build_sir_comparison_pdf_bytes(
        output_folder=folder_label,
        pure=pure,
        dynamic_runs=dynamic_runs,
        lang=lang,
        recommendations=recommendations,
    )
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in folder_label)[:80]
    prefix = 'sir_report' if lang == 'en' else 'sir_bao_cao'
    filename = f'{prefix}_{safe_name}_{stamp}.pdf'
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


def _handle_sir_export_pdf(payload: Optional[dict] = None, *, query_output_dir: str = '', query_lang: str = '') -> object:
    """Tạo PDF từ payload JSON (phiên làm việc) và/hoặc file trên đĩa."""
    data = payload if payload is not None else {}
    lang = (query_lang or data.get('lang') or 'vi').strip().lower()
    if lang not in ('vi', 'en'):
        lang = 'vi'

    output_dir = (query_output_dir or data.get('output_folder') or data.get('output_dir') or '').strip()
    folder_path = resolve_output_folder(output_dir) if output_dir else get_latest_output_dir()
    if folder_path is None or not folder_path.exists():
        return jsonify({'error': 'Không tìm thấy thư mục output'}), 404

    disk_pure, disk_runs = _load_sir_export_payload_from_folder(folder_path)
    pure, dynamic_runs = _merge_export_runs(
        data.get('pure'),
        data.get('dynamic_runs'),
        disk_pure,
        disk_runs,
    )

    recommendations = None
    try:
        recommendations = build_intervention_recommendations(folder_path)
    except Exception as e:
        logger.warning('PDF: không tải được đề xuất can thiệp: %s', e)

    return _sir_export_pdf_response(
        folder_path.name, pure, dynamic_runs, lang, recommendations=recommendations,
    )


@app.route('/api/sir-export-pdf', methods=['GET', 'POST'])
@app.route('/api/sir_export_pdf', methods=['GET', 'POST'])
def api_sir_export_pdf():
    """Xuất PDF: đồ thị so sánh I(t) + bảng chỉ số."""
    try:
        payload = request.get_json(silent=True) if request.method == 'POST' else {}
        if payload is None:
            payload = {}
        return _handle_sir_export_pdf(
            payload,
            query_output_dir=(request.args.get('output_dir') or '').strip(),
            query_lang=(request.args.get('lang') or '').strip(),
        )
    except Exception as e:
        logger.exception('api_sir_export_pdf failed')
        return jsonify({'error': f'Không tạo được PDF: {str(e)}'}), 500


@app.route('/api/sir-saved-runs', methods=['GET'])
def api_sir_saved_runs():
    """Liệt kê các mô phỏng SIR đã có file trên đĩa (để khôi phục khi tải lại trang)."""
    try:
        output_dir = request.args.get('output_dir')
        folder = resolve_output_folder(output_dir) if output_dir else get_latest_output_dir()
        if folder is None or not folder.exists():
            return jsonify({'error': 'Không tìm thấy thư mục output'}), 404

        pure_runs = list_saved_pure_sir_runs(folder)
        pure_ok = len(pure_runs) > 0 or find_pure_sir_history_csv(folder) is not None
        if pure_ok and not pure_runs:
            pure_runs = [{'misinfo_source_mode': 'random'}]
        dynamics = list_saved_dynamic_sir_runs(folder)
        return jsonify({
            'output_folder': folder.name,
            'pure_available': pure_ok,
            'pure_runs': pure_runs,
            'dynamic_runs': dynamics,
        })
    except Exception as e:
        logger.error(f'Error in api_sir_saved_runs: {e}')
        return jsonify({'error': str(e)}), 500


def empty_intervention_recommendations() -> dict:
    """Cùng cấu trúc với build_intervention_recommendations khi chưa có thư mục output."""
    rows = [
        {
            'strategy': s,
            'intervention_day': None,
            'top_k': None,
            'available': False,
            'peak_day': None,
            'peak_infected': None,
            'final_day': None,
            'total_infected': None,
            'never_infected': None,
            'node_ids': [],
            'intervened_nodes': [],
        }
        for s in DYNAMIC_STRATEGIES
    ]
    return {
        'output_folder': None,
        'pure_sir': None,
        'runs': [],
        'strategies': rows,
        'winner': None,
        'hint': 'Chưa có thư mục output. Về tổng quan và bấm «Tạo dữ liệu» trước.',
    }


@app.route('/api/intervention-recommendations', methods=['GET'])
def api_intervention_recommendations():
    try:
        output_dir = request.args.get('output_dir')
        folder = resolve_output_folder(output_dir) if output_dir else get_latest_output_dir()
        if folder is None or not folder.exists():
            return jsonify(empty_intervention_recommendations())
        data = build_intervention_recommendations(folder)
        return jsonify(data)
    except FileNotFoundError as e:
        logger.warning('intervention-recommendations: %s', e)
        payload = empty_intervention_recommendations()
        payload['warning'] = str(e)
        return jsonify(payload)
    except Exception as e:
        logger.error(f'Error in api_intervention_recommendations: {e}')
        return jsonify({'error': str(e)}), 500


def _list_output_dataset_dirs(include_uploaded: bool = True) -> list[Path]:
    """Liệt kê thư mục output_* / output_uploaded_* (mới nhất trước), không trùng đường dẫn."""
    prefixes = ['output_']
    if include_uploaded:
        prefixes.append('output_uploaded_')
    seen: set[str] = set()
    candidates: list[Path] = []
    for base in (OUTPUTS_DIR, OUTPUT_ROOT, BASE_DIR):
        try:
            base.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        if not base.is_dir():
            continue
        for p in base.iterdir():
            if not p.is_dir():
                continue
            if not any(p.name.startswith(pref) for pref in prefixes):
                continue
            key = str(p.resolve())
            if key in seen:
                continue
            seen.add(key)
            candidates.append(p)
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates


@app.route('/api/output-datasets', methods=['GET'])
def api_output_datasets():
    """Liệt kê các dataset output_* để chọn lại mà không cần tạo mới."""
    try:
        include_uploaded = (request.args.get('include_uploaded', '1') or '1').strip() not in (
            '0',
            'false',
            'False',
        )
        dirs = _list_output_dataset_dirs(include_uploaded=include_uploaded)
        rows: list[dict] = []
        for folder in dirs[:80]:
            nodes = None
            edges = None
            try:
                users_csv = folder / 'users.csv'
                rels_csv = folder / 'relationships.csv'
                if users_csv.is_file() and rels_csv.is_file():
                    nodes = _csv_row_count(users_csv)
                    edges = _csv_row_count(rels_csv)
            except Exception:
                nodes = None
                edges = None
            try:
                updated_at = int(folder.stat().st_mtime)
            except OSError:
                updated_at = None
            rows.append(
                {
                    'name': folder.name,
                    'updated_at': updated_at,
                    'nodes': nodes,
                    'edges': edges,
                }
            )
        return jsonify({'datasets': rows})
    except Exception as e:
        logger.exception('api_output_datasets failed')
        return jsonify({'error': str(e)}), 500


@app.route('/api/cleanup-outputs', methods=['POST'])
def api_cleanup_outputs():
    try:
        payload = request.get_json() or {}
        delete_all = bool(payload.get('delete_all', False))
        keep_latest = 0 if delete_all else int(payload.get('keep_latest', 1))
        if keep_latest < 0:
            keep_latest = 0
        include_uploaded = bool(payload.get('include_uploaded', True))

        clear_simulations = bool(payload.get('clear_simulations', True))

        candidates = _list_output_dataset_dirs(include_uploaded=include_uploaded)
        to_remove = candidates[keep_latest:]
        kept = candidates[:keep_latest]
        removed_names: list[str] = []
        for p in to_remove:
            shutil.rmtree(p, ignore_errors=True)
            removed_names.append(p.name)

        cleared_sim_roots = 0
        if clear_simulations:
            for p in kept:
                cleared_sim_roots += clear_dataset_sir_results(p)
            for base in (OUTPUTS_DIR, OUTPUT_ROOT, BASE_DIR):
                cleared_sim_roots += clear_orphan_legacy_sir_dirs(base)

        _invalidate_graph_cache()

        return jsonify({
            'removed_count': len(removed_names),
            'kept': min(len(candidates), keep_latest),
            'removed_dirs': removed_names,
            'cleared_simulation_roots': cleared_sim_roots,
            'delete_all': delete_all or keep_latest == 0,
        })
    except Exception as e:
        logger.error(f'Error in api_cleanup_outputs: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    latest = get_latest_output_dir()
    return jsonify({
        'ok': True,
        'latest_output': latest.name if latest else None,
    })


def _save_uploaded_dataset(
    users_df: pd.DataFrame,
    relationships_df: pd.DataFrame,
    *,
    seed: int = 42,
) -> Path:
    """Lưu users/relationships/metrics vào outputs/output_uploaded_*."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    main_output_dir = OUTPUTS_DIR / f'output_uploaded_{stamp}'
    main_output_dir.mkdir(parents=True, exist_ok=True)

    users_df.to_csv(main_output_dir / 'users.csv', index=False)
    relationships_df.to_csv(main_output_dir / 'relationships.csv', index=False)

    generator = SocialNetworkGenerator(num_users=len(users_df), seed=seed)
    generator.output_dir = str(main_output_dir)
    generator.users = users_df.to_dict('records')
    generator.relationships = relationships_df.to_dict('records')
    generator.create_graph()
    generator.calculate_metrics().to_csv(main_output_dir / 'metrics.csv', index=False)

    _invalidate_graph_cache()
    return main_output_dir


@app.route('/api/upload-data', methods=['POST'])
def api_upload_data():
    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Không có file được chọn'}), 400

    if not allowed_upload_filename(file.filename):
        return jsonify({'error': 'Chỉ chấp nhận file .csv, .xlsx hoặc .xls'}), 400

    try:
        df = read_upload_table(file)
        if df is None or df.empty:
            return jsonify({'error': 'File rỗng hoặc không đọc được'}), 400

        kind = detect_upload_kind(df)

        if kind == 'edges':
            users_df, relationships_df = prepare_edges_upload(df)
            main_output_dir = _save_uploaded_dataset(users_df, relationships_df)
            n_nodes = len(users_df)
            n_edges = len(relationships_df)
            msg = (
                f'Đã nhập {n_edges:,} quan hệ kết bạn, '
                f'{n_nodes:,} người dùng (suy ra từ danh sách cạnh).'
            )
        else:
            required_cols = ['id', 'name', 'followers', 'posts', 'shares', 'comments', 'risk']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                return jsonify(
                    {'error': f'Thiếu các cột bắt buộc: {", ".join(missing_cols)}'}
                ), 400

            relationships = []
            for i, user1 in enumerate(df.to_dict('records')):
                for j, user2 in enumerate(df.to_dict('records')):
                    if i >= j:
                        continue
                    risk_factor = {'High': 0.8, 'Medium': 0.5, 'Low': 0.3, 'Unknown': 0.2}
                    prob = risk_factor.get(user1.get('risk', 'Unknown'), 0.2) * risk_factor.get(
                        user2.get('risk', 'Unknown'), 0.2
                    )
                    if np.random.random() < prob:
                        relationships.append(
                            {'user1_id': int(user1['id']), 'user2_id': int(user2['id'])}
                        )

            users_df = df.rename(columns={'id': 'user_id'}) if 'id' in df.columns else df
            relationships_df = pd.DataFrame(relationships)
            main_output_dir = _save_uploaded_dataset(users_df, relationships_df)
            n_nodes = len(users_df)
            n_edges = len(relationships_df)
            msg = f'Upload bảng người dùng: {n_nodes:,} nút, {n_edges:,} cạnh (sinh theo risk).'

        return jsonify({
            'output_folder': main_output_dir.name,
            'nodes': n_nodes,
            'edges': n_edges,
            'upload_kind': kind,
            'message': msg,
        })

    except ImportError as e:
        logger.error('Upload dependency missing: %s', e)
        return jsonify(
            {'error': 'Thiếu thư viện đọc Excel. Chạy: pip install openpyxl'}
        ), 500
    except pd.errors.ParserError as e:
        logger.error(f'CSV parsing error: {e}')
        return jsonify({'error': f'Lỗi định dạng file: {str(e)}'}), 400
    except ValueError as e:
        logger.error(f'Value error processing uploaded file: {e}')
        return jsonify({'error': f'Lỗi dữ liệu không hợp lệ: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'Error processing uploaded file: {e}')
        return jsonify({'error': f'Lỗi xử lý file: {str(e)}'}), 500


@app.route('/<path:path>', methods=['GET', 'HEAD'])
def static_files(path):
    if path.startswith('api/'):
        return jsonify({'error': 'API không hỗ trợ phương thức này hoặc cần khởi động lại server.'}), 404
    return send_from_directory(str(BASE_DIR), path)


@app.errorhandler(404)
def not_found(error):
    return json_safe_response({'error': str(error)}, 404)


@app.errorhandler(500)
def internal_error(error):
    logger.exception('Unhandled 500: %s', error)
    return json_safe_response(
        {
            'error': 'Lỗi máy chủ nội bộ',
            'detail': str(error) if error else None,
        },
        500,
    )

