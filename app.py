import os

os.environ.setdefault('MPLBACKEND', 'Agg')

from flask import Flask, jsonify, request, send_from_directory, abort
from pathlib import Path
from typing import Optional
import pandas as pd
import networkx as nx
import numpy as np
import json
import datetime
import logging
import tempfile
import shutil

from Tao_nguoi_dung_va_do_thi import SocialNetworkGenerator
from sir_models import PureSIRSimulation, SIRDynamicImmunization
from sir_sim_paths import (
    find_dynamic_sir_history_csv,
    find_pure_sir_history_csv,
    list_saved_dynamic_sir_runs,
    read_immunized_node_ids,
)
from graph_layout import spring_or_circular

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, static_folder='.', static_url_path='')

RISK_COLORS = {
    'High': '#d63939',
    'Medium': '#f29424',
    'Low': '#0f9d58',
    'Unknown': '#9ca3af'
}
CLUSTER_COLORS = ['#d63939', '#026e9f', '#f29424', '#9ca3af', '#6d28d9']

DYNAMIC_STRATEGIES = ('betweenness', 'degree', 'eigenvector')

_cached_graph = None
_cached_payload = None
_cached_output = None


def get_latest_output_dir() -> Optional[Path]:
    env_path = os.getenv('MO_PHONG_OUTPUT_DIR')
    if env_path:
        output_dir = Path(env_path)
        if output_dir.exists() and output_dir.is_dir():
            return output_dir

    candidates = [p for p in BASE_DIR.glob('output_*') if p.is_dir()]
    candidates += [p for p in BASE_DIR.glob('output_uploaded_*') if p.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_output_data(output_dir: Optional[str] = None):
    if output_dir:
        folder = Path(output_dir)
        if not folder.is_dir():
            folder = BASE_DIR / output_dir
    else:
        folder = get_latest_output_dir()
    if folder is None or not folder.exists():
        raise FileNotFoundError('Không tìm thấy thư mục dữ liệu output')

    users_csv = folder / 'users.csv'
    rels_csv = folder / 'relationships.csv'
    metrics_csv = folder / 'metrics.csv'

    if not users_csv.exists() or not rels_csv.exists() or not metrics_csv.exists():
        raise FileNotFoundError('File dữ liệu cần thiết không tồn tại trong output folder')

    users = pd.read_csv(users_csv)
    relationships = pd.read_csv(rels_csv)
    metrics = pd.read_csv(metrics_csv)

    # Normalize column names for compatibility
    # Handle both generated data (user_id, user1_id, user2_id) and uploaded data (id, source, target)
    if 'user_id' in users.columns:
        # Generated data format
        users = users.rename(columns={'user_id': 'id'})
    if 'user1_id' in relationships.columns and 'user2_id' in relationships.columns:
        # Generated data format
        relationships = relationships.rename(columns={'user1_id': 'source', 'user2_id': 'target'})

    return folder, users, relationships, metrics


def create_graph(users: pd.DataFrame, relationships: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for _, user in users.iterrows():
        graph.add_node(int(user['id']))
    for _, row in relationships.iterrows():
        graph.add_edge(int(row['source']), int(row['target']))
    return graph


def sir_metrics_from_history_df(df: pd.DataFrame, n_nodes: int) -> tuple:
    """(peak_day, peak_infected, final_day) — ưu tiên đỉnh I thấp và kết thúc sớm khi so sánh."""
    peak_idx = df['I'].idxmax()
    peak_day = int(df.loc[peak_idx, 'day'])
    peak_I = int(df['I'].max())
    done = df[df['R'] == n_nodes]
    final_day = int(done['day'].iloc[0]) if len(done) else int(df['day'].iloc[-1])
    return peak_day, peak_I, final_day


def build_intervention_recommendations(folder: Path) -> dict:
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
        pd_day, pd_pi, pd_fd = sir_metrics_from_history_df(pdf, n_nodes)
        pure_metrics = {
            'peak_day': pd_day,
            'peak_infected': pd_pi,
            'final_day': pd_fd,
        }

    rows = []

    for strategy in DYNAMIC_STRATEGIES:
        hist_path = find_dynamic_sir_history_csv(folder, strategy, 1)
        node_ids = read_immunized_node_ids(folder, strategy, 1) if hist_path is not None else []

        if hist_path is None:
            rows.append({
                'strategy': strategy,
                'available': False,
                'peak_day': None,
                'peak_infected': None,
                'final_day': None,
                'node_ids': node_ids,
                'intervened_nodes': [],
            })
            continue

        dfp = pd.read_csv(hist_path)
        peak_day, peak_I, final_day = sir_metrics_from_history_df(dfp, n_nodes)
        detail = [{'id': nid, 'name': id_to_name.get(nid, str(nid))} for nid in node_ids]
        rows.append({
            'strategy': strategy,
            'available': True,
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
            'node_ids': node_ids,
            'intervened_nodes': detail,
        })

    available = [r for r in rows if r['available']]
    rationale_vi = (
        'Xếp hạng theo thứ tự từ điển: (1) đỉnh số ca nhiễm đồng thời (I) càng thấp càng tốt; '
        '(2) nếu bằng nhau thì ngày kết thúc dịch (R = toàn mạng) càng sớm càng tốt.'
    )
    rationale_en = (
        'Lexicographic ranking: (1) lower peak concurrent infected (I) is better; '
        '(2) if tied, earlier full-recovery day (R equals network size) is better.'
    )

    winner = None
    if available:
        available.sort(key=lambda r: (r['peak_infected'], r['final_day']))
        w = available[0]
        winner = {
            'strategy': w['strategy'],
            'peak_day': w['peak_day'],
            'peak_infected': w['peak_infected'],
            'final_day': w['final_day'],
            'node_ids': w['node_ids'],
            'intervened_nodes': w['intervened_nodes'],
        }

    return {
        'output_folder': folder.name,
        'pure_sir': pure_metrics,
        'strategies': rows,
        'winner': winner,
        'rationale_vi': rationale_vi,
        'rationale_en': rationale_en,
    }


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


def build_node_payload(users, metrics, graph, positions):
    payload = []
    
    # Rename metrics columns to standardized names
    metrics = metrics.rename(columns={
        'user_id': 'id',
        'betweenness_centrality': 'betweenness',
        'degree_centrality': 'degree',
        'eigenvector_centrality': 'eigenvector'
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

    for _, row in info.iterrows():
        node_id = int(row['id'])
        pos = positions.get(node_id, (0.0, 0.0))

        # Handle different risk calculation methods
        if 'risk' in row and pd.notna(row['risk']):
            risk = str(row['risk'])
        else:
            # Calculate risk from metrics for generated data
            score = (
                row.get('betweenness', 0) * 1800
                + row.get('degree', 0) * 450
                + row.get('eigenvector', 0) * 900
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
        radius = max(10, min(28, 10 + int(degree_map.get(node_id, 0) * 1.5)))

        payload.append({
            'id': node_id,
            'name': str(row.get('name', f'User {node_id}')),
            'role': 'Nút trung gian' if row.get('betweenness', 0) >= info['betweenness'].quantile(0.75) else 'Nút lan truyền' if row.get('degree', 0) >= info['degree'].quantile(0.7) else 'Quan sát viên',
            'degree': float(row.get('degree', 0)),
            'betweenness': float(row.get('betweenness', 0)),
            'eigenvector': float(row.get('eigenvector', 0)),
            'risk': risk,
            'risk_score': int(100 * min(1.0, row.get('betweenness', 0) * 3 + row.get('degree', 0) * 2 + row.get('eigenvector', 0) * 2)),
            'cluster': None,
            'followers': followers,
            'posts': posts,
            'shares': shares,
            'comments': comments,
            'x': int(80 + 720 * (pos[0] + 1) / 2),
            'y': int(60 + 420 * (pos[1] + 1) / 2),
            'radius': radius,
            'color': '#94a3b8',
        })
    return payload


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
        'clusters': [],
        'hint': 'Bấm «Tạo dữ liệu» trên thanh công cụ để sinh thư mục output_* (users.csv, relationships.csv, metrics.csv).',
    }


def build_graph_payload():
    global _cached_graph, _cached_payload, _cached_output
    try:
        folder, users, relationships, metrics = load_output_data()
    except FileNotFoundError as e:
        logger.warning('Chưa có bộ dữ liệu output: %s', e)
        return empty_graph_payload()
    
    if _cached_output == folder and _cached_payload is not None:
        return _cached_payload

    graph = create_graph(users, relationships)
    _cached_graph = graph
    _cached_output = folder

    positions = spring_or_circular(graph, seed=42, iterations=80)
    node_payload = build_node_payload(users, metrics, graph, positions)

    try:
        communities = list(nx.community.greedy_modularity_communities(graph))
    except Exception as exc:
        logger.warning('greedy_modularity_communities failed (%s); single cluster', exc)
        communities = [set(graph.nodes())] if graph.number_of_nodes() else []
    cluster_map = {}
    cluster_items = []
    for index, community in enumerate(communities[:4]):
        color = CLUSTER_COLORS[index % len(CLUSTER_COLORS)]
        cluster_name = f'Cụm {index + 1}'
        for node in community:
            cluster_map[node] = {'name': cluster_name, 'color': color}
        cluster_items.append({'name': cluster_name, 'color': color, 'count': len(community)})

    for node in node_payload:
        node_cluster = cluster_map.get(node['id'], {'name': 'Chưa xác định', 'color': '#9ca3af'})
        node['cluster'] = node_cluster['name']
        node['cluster_color'] = node_cluster['color']
        node['color'] = node_cluster['color']

    edges_payload = [
        {'source': int(row['source']), 'target': int(row['target'])}
        for _, row in relationships.iterrows()
    ]

    top_nodes = sorted(node_payload, key=lambda item: item['betweenness'], reverse=True)[:10]

    _cached_payload = {
        'ready': True,
        'output_folder': folder.name,
        'nodes': len(users),
        'edges': len(relationships),
        'data_date': str(users['join_date'].max() if 'join_date' in users.columns else datetime.date.today()),
        'status': 'Dữ liệu đã sẵn sàng',
        'version': '1.0.0',
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'nodes_data': node_payload,
        'edges_data': edges_payload,
        'top_nodes': top_nodes,
        'clusters': cluster_items,
    }
    return _cached_payload


@app.route('/')
def index():
    return send_from_directory(str(BASE_DIR), 'index.html')


@app.route('/simulation')
def simulation_page():
    return send_from_directory(str(BASE_DIR), 'simulation.html')


@app.route('/recommendations')
def recommendations_page():
    return send_from_directory(str(BASE_DIR), 'recommendations.html')


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(str(BASE_DIR), path)


@app.route('/api/summary')
def api_summary():
    try:
        payload = build_graph_payload()
    except Exception as e:
        logger.exception('api_summary: build_graph_payload failed')
        payload = empty_graph_payload()
        payload['hint'] = (
            f'Lỗi khi dựng đồ thị: {str(e)}. '
            'Thử bấm «Tạo dữ liệu» lại, giảm số user, hoặc kiểm tra Render đã cài scipy (requirements.txt).'
        )
    return jsonify({
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


@app.route('/api/graph')
def api_graph():
    try:
        payload = build_graph_payload()
        return jsonify(payload)
    except Exception as e:
        logger.exception('api_graph: build_graph_payload failed')
        p = empty_graph_payload()
        p['hint'] = (
            f'Lỗi khi dựng đồ thị: {str(e)}. '
            'Thử «Tạo dữ liệu» lại hoặc giảm số user; trên Render cần có scipy trong requirements.txt.'
        )
        p['error'] = str(e)
        return jsonify(p)


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

        generator = SocialNetworkGenerator(num_users=num_users, seed=seed)
        metrics = generator.run(num_users=num_users, relationship_prob=relationship_prob)

        return jsonify({
            'output_folder': generator.output_dir,
            'nodes': num_users,
            'edges': len(generator.relationships),
            'top_nodes': metrics.head(10).to_dict(orient='records'),
        })
    except Exception as e:
        logger.error(f'Error in api_run_generator: {e}')
        return jsonify({'error': f'Lỗi tạo dữ liệu: {str(e)}'}), 500


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

        if model == 'dynamic':
            top_k = int(payload.get('top_k', 10))
            strategy = (payload.get('strategy') or 'betweenness').strip().lower()
            intervention_day = int(payload.get('intervention_day', 1))
            sim = SIRDynamicImmunization(
                output_dir=output_dir,
                top_k=top_k,
                strategy=strategy,
                intervention_day=intervention_day,
            )
            sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, days=days, seed=seed)
            peak_day, peak_I, final_day = sim.get_statistics()
            return jsonify({
                'model': 'dynamic',
                'strategy': sim.strategy,
                'top_k': sim.top_k,
                'intervention_day': sim.intervention_day,
                'output_directory': sim.results_dir,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
            })

        sim = PureSIRSimulation(output_dir=output_dir)
        sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, max_days=days, seed=seed)
        peak_day, peak_I, final_day = sim.get_statistics()
        sim.save()
        return jsonify({
            'model': 'pure',
            'output_directory': sim.results_dir,
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
        })
    except Exception as e:
        logger.error(f'Error in api_run_simulate: {e}')
        return jsonify({'error': f'Lỗi mô phỏng: {str(e)}'}), 500


@app.route('/api/simulate-sir', methods=['POST'])
def api_simulate_sir():
    try:
        payload = request.get_json() or {}
        model = payload.get('model', 'pure')
        folder, users, relationships, _metrics = load_output_data(payload.get('output_dir'))
        graph = create_graph(users, relationships)
        n_nodes = graph.number_of_nodes()
        transmission_rate = float(payload.get('transmission_rate', 0.3))
        recovery_rate = float(payload.get('recovery_rate', 0.1))
        days = int(payload.get('days', 300))
        seed = int(payload.get('seed', 42))

        if model == 'dynamic':
            top_k = int(payload.get('top_k', 10))
            strategy = (payload.get('strategy') or 'betweenness').strip().lower()
            intervention_day = int(payload.get('intervention_day', 1))
            sim = SIRDynamicImmunization(
                output_dir=str(folder),
                top_k=top_k,
                strategy=strategy,
                intervention_day=intervention_day,
            )
            sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, days=days, seed=seed)
            peak_day, peak_I, final_day = sim.get_statistics()
            hist = sim.history.to_dict(orient='records')
            imm = [int(x) for x in sim.immunized_nodes]
            return jsonify({
                'model': 'dynamic',
                'strategy': sim.strategy,
                'top_k': sim.top_k,
                'intervention_day': sim.intervention_day,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'history': hist,
                'output_directory': sim.results_dir,
                'immunized_node_ids': imm,
            })

        sim = PureSIRSimulation(output_dir=str(folder))
        sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, max_days=days, seed=seed)
        peak_day, peak_I, final_day = sim.get_statistics()
        sim.save()
        hist = sim.history.to_dict(orient='records')
        return jsonify({
            'model': 'pure',
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
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
        folder = Path(output_dir) if output_dir else get_latest_output_dir()
        if output_dir and folder and not folder.is_dir():
            alt = BASE_DIR / output_dir
            if alt.is_dir():
                folder = alt
        if folder is None or not folder.exists():
            return jsonify({'error': 'Không tìm thấy thư mục output'}), 404

        if model == 'dynamic':
            strat_q = (request.args.get('strategy') or 'betweenness').strip().lower()
            if strat_q not in DYNAMIC_STRATEGIES:
                strat_q = 'betweenness'
            intervention_day = int(request.args.get('intervention_day', 1))
            hist_path = find_dynamic_sir_history_csv(folder, strat_q, intervention_day)
        else:
            strat_q = None
            intervention_day = None
            hist_path = find_pure_sir_history_csv(folder)

        if hist_path is None:
            return jsonify({'error': 'Chưa có sir_history.csv'}), 404

        df = pd.read_csv(hist_path)
        users_csv = folder / 'users.csv'
        n_nodes = len(pd.read_csv(users_csv)) if users_csv.exists() else int(df['S'].iloc[0] + df['I'].iloc[0] + df['R'].iloc[0])
        peak_day, peak_I, final_day = sir_metrics_from_history_df(df, n_nodes)

        payload = {
            'history': df.to_dict(orient='records'),
            'statistics': {
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
            },
            'output_directory': str(hist_path.parent.resolve()),
        }
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
                except (OSError, json.JSONDecodeError, TypeError, ValueError):
                    pass

        return jsonify(payload)
    except Exception as e:
        logger.error(f'Error in api_sir_results: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/sir-saved-runs', methods=['GET'])
def api_sir_saved_runs():
    """Liệt kê các mô phỏng SIR đã có file trên đĩa (để khôi phục khi tải lại trang)."""
    try:
        output_dir = request.args.get('output_dir')
        folder = Path(output_dir) if output_dir else get_latest_output_dir()
        if output_dir and folder and not folder.is_dir():
            alt = BASE_DIR / output_dir
            if alt.is_dir():
                folder = alt
        if folder is None or not folder.exists():
            return jsonify({'error': 'Không tìm thấy thư mục output'}), 404

        pure_ok = find_pure_sir_history_csv(folder) is not None
        dynamics = list_saved_dynamic_sir_runs(folder)
        return jsonify({
            'output_folder': folder.name,
            'pure_available': pure_ok,
            'dynamic_runs': dynamics,
        })
    except Exception as e:
        logger.error(f'Error in api_sir_saved_runs: {e}')
        return jsonify({'error': str(e)}), 500


def empty_intervention_recommendations() -> dict:
    """Cùng cấu trúc với build_intervention_recommendations khi chưa có thư mục output."""
    rationale_vi = (
        'Xếp hạng theo thứ tự từ điển: (1) đỉnh số ca nhiễm đồng thời (I) càng thấp càng tốt; '
        '(2) nếu bằng nhau thì ngày kết thúc dịch (R = toàn mạng) càng sớm càng tốt.'
    )
    rationale_en = (
        'Lexicographic ranking: (1) lower peak concurrent infected (I) is better; '
        '(2) if tied, earlier full-recovery day (R equals network size) is better.'
    )
    rows = [
        {
            'strategy': s,
            'available': False,
            'peak_day': None,
            'peak_infected': None,
            'final_day': None,
            'node_ids': [],
            'intervened_nodes': [],
        }
        for s in DYNAMIC_STRATEGIES
    ]
    return {
        'output_folder': None,
        'pure_sir': None,
        'strategies': rows,
        'winner': None,
        'rationale_vi': rationale_vi,
        'rationale_en': rationale_en,
        'hint': 'Chưa có thư mục output. Về tổng quan và bấm «Tạo dữ liệu» trước.',
    }


@app.route('/api/intervention-recommendations', methods=['GET'])
def api_intervention_recommendations():
    try:
        output_dir = request.args.get('output_dir')
        folder = Path(output_dir) if output_dir else get_latest_output_dir()
        if output_dir and folder and not folder.is_dir():
            alt = BASE_DIR / output_dir
            if alt.is_dir():
                folder = alt
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


@app.route('/api/cleanup-outputs', methods=['POST'])
def api_cleanup_outputs():
    try:
        payload = request.get_json() or {}
        keep_latest = int(payload.get('keep_latest', 3))
        include_uploaded = bool(payload.get('include_uploaded', True))

        prefixes = ['output_']
        if include_uploaded:
            prefixes.append('output_uploaded_')

        candidates = []
        for p in BASE_DIR.iterdir():
            if not p.is_dir():
                continue
            if any(p.name.startswith(pref) for pref in prefixes):
                candidates.append(p)

        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        to_remove = candidates[keep_latest:]
        removed = 0
        for p in to_remove:
            shutil.rmtree(p, ignore_errors=True)
            removed += 1

        global _cached_graph, _cached_payload, _cached_output
        _cached_graph = None
        _cached_payload = None
        _cached_output = None

        return jsonify({'removed_count': removed, 'kept': min(len(candidates), keep_latest)})
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


@app.route('/api/upload-data', methods=['POST'])
def api_upload_data():
    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Không có file được chọn'}), 400

    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'Chỉ chấp nhận file CSV'}), 400

    try:
        # Read CSV data
        df = pd.read_csv(file)

        # Validate required columns
        required_cols = ['id', 'name', 'followers', 'posts', 'shares', 'comments', 'risk']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            return jsonify({'error': f'Thiếu các cột bắt buộc: {", ".join(missing_cols)}'}), 400

        # Create temporary directory for processing
        temp_dir = Path(tempfile.mkdtemp(prefix='upload_'))
        output_dir = temp_dir / f"uploaded_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Process the uploaded data
        generator = SocialNetworkGenerator(num_users=len(df), seed=42)
        generator.users = df.to_dict('records')

        # Create relationships based on risk levels (higher risk = more connections)
        relationships = []
        for i, user1 in enumerate(generator.users):
            for j, user2 in enumerate(generator.users):
                if i >= j: continue  # Avoid duplicates and self-connections

                # Higher risk users tend to connect more
                risk_factor = {'High': 0.8, 'Medium': 0.5, 'Low': 0.3, 'Unknown': 0.2}
                prob = risk_factor.get(user1.get('risk', 'Unknown'), 0.2) * risk_factor.get(user2.get('risk', 'Unknown'), 0.2)

                if np.random.random() < prob:
                    relationships.append({
                        'source': user1['id'],
                        'target': user2['id'],
                        'weight': np.random.uniform(0.1, 1.0)
                    })

        generator.relationships = relationships
        generator.output_dir = str(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save processed data
        users_df = pd.DataFrame(generator.users)
        relationships_df = pd.DataFrame(generator.relationships)

        users_df.to_csv(output_dir / 'users.csv', index=False)
        relationships_df.to_csv(output_dir / 'relationships.csv', index=False)

        # Create adjacency matrix
        G = nx.Graph()
        G.add_nodes_from([u['id'] for u in generator.users])
        G.add_edges_from([(r['source'], r['target']) for r in generator.relationships])

        adj_matrix = nx.to_pandas_adjacency(G, dtype=int)
        adj_matrix.to_csv(output_dir / 'adjacency_matrix.csv')

        # Calculate metrics - compute centrality measures once
        degree_map = dict(G.degree())
        betweenness_map = nx.betweenness_centrality(G)
        
        # Handle eigenvector centrality with fallback
        try:
            eigenvector_map = nx.eigenvector_centrality(G, max_iter=1000)
        except Exception as e:
            logger.warning(f'Eigenvector centrality calculation failed: {e}, using fallback')
            eigenvector_map = {node: 0.0 for node in G.nodes()}
        
        metrics_data = []
        for user in generator.users:
            node_id = user['id']
            degree = degree_map.get(node_id, 0)
            betweenness = betweenness_map.get(node_id, 0)
            eigenvector = eigenvector_map.get(node_id, 0)

            metrics_data.append({
                'id': node_id,
                'name': user['name'],
                'degree': degree,
                'betweenness': betweenness,
                'eigenvector': eigenvector,
                'risk_score': {'High': 0.9, 'Medium': 0.6, 'Low': 0.3, 'Unknown': 0.1}.get(user.get('risk', 'Unknown'), 0.1)
            })

        metrics_df = pd.DataFrame(metrics_data)
        metrics_df.to_csv(output_dir / 'metrics.csv', index=False)

        # Copy to main output directory for dashboard
        main_output_dir = BASE_DIR / f"output_uploaded_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copytree(output_dir, main_output_dir)

        return jsonify({
            'output_folder': str(main_output_dir),
            'nodes': len(generator.users),
            'edges': len(generator.relationships),
            'message': f'Upload và xử lý thành công {len(generator.users)} người dùng từ file CSV'
        })

    except pd.errors.ParserError as e:
        logger.error(f'CSV parsing error: {e}')
        return jsonify({'error': f'Lỗi định dạng CSV: {str(e)}'}), 400
    except ValueError as e:
        logger.error(f'Value error processing uploaded file: {e}')
        return jsonify({'error': f'Lỗi dữ liệu không hợp lệ: {str(e)}'}), 400
    except Exception as e:
        logger.error(f'Error processing uploaded file: {e}')
        return jsonify({'error': f'Lỗi xử lý file: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': str(error)}), 404

if __name__ == "__main__":
    # Mặc định chỉ lắng nghe trên máy này (127.0.0.1). Mở LAN: APP_HOST=0.0.0.0
    port = int(os.environ.get("PORT", "5000"))
    host = os.environ.get("APP_HOST", "127.0.0.1")
    logger.info("Chạy cục bộ: http://%s:%s (LAN: đặt biến môi trường APP_HOST=0.0.0.0)", host, port)
    app.run(host=host, port=port, debug=False)
