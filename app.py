from flask import Flask, jsonify, request, send_from_directory, abort, redirect
from pathlib import Path
from typing import Optional
from urllib.parse import quote
import pandas as pd
import networkx as nx
import numpy as np
import os
import datetime
import logging
import shutil

from Tao_nguoi_dung_va_do_thi import SocialNetworkGenerator
from sir_models import PureSIRSimulation, SIRDynamicImmunization

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

_cached_graph = None
_cached_payload = None
_cached_output = None


def sir_view_url(model: str, results_dir: str) -> str:
    """URL trang mô phỏng SIR (đường dẫn POSIX, đã encode)."""
    path = quote(str(Path(results_dir).as_posix()), safe='')
    return f'/simulation?model={model}&output_dir={path}'


def get_latest_output_dir() -> Optional[Path]:
    env_path = os.getenv('MO_PHONG_OUTPUT_DIR')
    if env_path:
        output_dir = Path(env_path)
        # Create folder if configured (Render filesystem might be ephemeral)
        output_dir.mkdir(parents=True, exist_ok=True)
        if output_dir.exists() and output_dir.is_dir():
            # Look for output_* subfolders inside it
            candidates = [p for p in output_dir.glob('output_*') if p.is_dir()]
            if candidates:
                return max(candidates, key=lambda p: p.stat().st_mtime)
    

    candidates = [p for p in BASE_DIR.glob('output_*') if p.is_dir() and p.name != 'output_archive']
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_output_data(output_dir: Optional[str] = None):
    folder = Path(output_dir) if output_dir else get_latest_output_dir()
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
    
    # Normalize metrics columns
    if 'user_id' in metrics.columns:
        metrics = metrics.rename(columns={'user_id': 'id'})

    return folder, users, relationships, metrics


def create_graph(users: pd.DataFrame, relationships: pd.DataFrame) -> nx.Graph:
    graph = nx.Graph()
    for _, user in users.iterrows():
        graph.add_node(int(user['id']))
    for _, row in relationships.iterrows():
        graph.add_edge(int(row['source']), int(row['target']))
    return graph


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
    # Ensure both dataframes have 'id' column for merging
    merge_key = 'id'
    
    # Check if merge key exists in both dataframes
    if merge_key not in users.columns:
        logger.warning(f'Missing {merge_key} in users dataframe. Columns: {list(users.columns)}')
        return payload
    
    if merge_key not in metrics.columns:
        logger.warning(f'Missing {merge_key} in metrics dataframe. Columns: {list(metrics.columns)}')
        # If metrics doesn't have id, try to match by index or create it
        if len(metrics) == len(users):
            metrics = metrics.copy()
            metrics['id'] = users['id'].values
        else:
            return payload
    
    info = users.merge(metrics, on=merge_key, how='left')
    if 'betweenness' in info.columns:
        info = info.sort_values('betweenness', ascending=False)
    elif 'betweenness_centrality' in info.columns:
        info = info.sort_values('betweenness_centrality', ascending=False)
    degree_map = dict(graph.degree())


    for _, row in info.iterrows():
        node_id = int(row[merge_key])
        pos = positions.get(node_id, (0.0, 0.0))

        # Handle different risk calculation methods
        if 'risk' in row and pd.notna(row['risk']):
            risk = str(row['risk'])
        else:
            # Calculate risk from metrics for generated data
            # Handle both centrality metrics (e.g., betweenness_centrality) and simple metrics (e.g., betweenness)
            betweenness = row.get('betweenness_centrality', row.get('betweenness', 0))
            degree = row.get('degree_centrality', row.get('degree', 0))
            eigenvector = row.get('eigenvector_centrality', row.get('eigenvector', 0))
            
            score = (
                betweenness * 1800
                + degree * 450
                + eigenvector * 900
            )
            if score >= 180:
                risk = 'High'
            elif score >= 95:
                risk = 'Medium'
            elif score >= 40:
                risk = 'Low'
            else:
                risk = 'Unknown'

        # Get the metric column names (may be centrality or simple names)
        bet_col = 'betweenness_centrality' if 'betweenness_centrality' in info.columns else 'betweenness'
        deg_col = 'degree_centrality' if 'degree_centrality' in info.columns else 'degree'
        eig_col = 'eigenvector_centrality' if 'eigenvector_centrality' in info.columns else 'eigenvector'
        
        betweenness_val = float(row.get(bet_col, row.get('betweenness', 0)))
        degree_val = float(row.get(deg_col, row.get('degree', 0)))
        eigenvector_val = float(row.get(eig_col, row.get('eigenvector', 0)))

        followers = int(row.get('followers', 0))
        posts = int(row.get('posts', 0))
        shares = int(row.get('shares', max(0, min(9999, followers * 0.15 + posts * 2))))
        comments = int(row.get('comments', max(0, min(9999, followers * 0.08 + posts * 1.1))))
        radius = max(10, min(28, 10 + int(degree_map.get(node_id, 0) * 1.5)))

        # Calculate role based on metrics
        bet_quantile = info[bet_col].quantile(0.75) if bet_col in info.columns else 0
        deg_quantile = info[deg_col].quantile(0.7) if deg_col in info.columns else 0
        
        if betweenness_val >= bet_quantile:
            role = 'Nút trung gian'
        elif degree_val >= deg_quantile:
            role = 'Nút lan truyền'
        else:
            role = 'Quan sát viên'

        payload.append({
            'id': node_id,
            'name': str(row.get('name', f'User {node_id}')),
            'role': role,
            'degree': degree_val,
            'betweenness': betweenness_val,
            'eigenvector': eigenvector_val,
            'risk': risk,
            'risk_score': int(100 * min(1.0, betweenness_val * 3 + degree_val * 2 + eigenvector_val * 2)),
            'cluster': None,
            'followers': followers,
            'posts': posts,
            'shares': shares,
            'comments': comments,
            'x': int(80 + 720 * (pos[0] + 1) / 2),
            'y': int(60 + 420 * (pos[1] + 1) / 2),
            'radius': radius,
            'color': RISK_COLORS.get(risk, '#9ca3af')
        })
    return payload


def build_graph_payload():
    global _cached_graph, _cached_payload, _cached_output
    folder, users, relationships, metrics = load_output_data()
    if _cached_output == folder and _cached_payload is not None:
        return _cached_payload

    graph = create_graph(users, relationships)
    _cached_graph = graph
    _cached_output = folder

    positions = nx.spring_layout(graph, seed=42, iterations=80)
    node_payload = build_node_payload(users, metrics, graph, positions)

    communities = list(nx.community.greedy_modularity_communities(graph))
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

    edges_payload = [
        {'source': int(row['source']), 'target': int(row['target'])}
        for _, row in relationships.iterrows()
    ]

    top_nodes = sorted(node_payload, key=lambda item: item['betweenness'], reverse=True)[:10]

    _cached_payload = {
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


@app.route('/results')
def results():
    return redirect('/simulation', code=302)


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(str(BASE_DIR), path)


@app.route('/api/summary')
def api_summary():
    payload = build_graph_payload()
    return jsonify({
        'nodes': payload['nodes'],
        'edges': payload['edges'],
        'interaction_type': 'Share/Comment',
        'data_date': payload['data_date'],
        'status': payload['status'],
        'version': payload['version'],
        'timestamp': payload['timestamp'],
        'output_folder': payload['output_folder'],
    })


@app.route('/api/graph')
def api_graph():
    payload = build_graph_payload()
    return jsonify(payload)


@app.route('/api/top-nodes')
def api_top_nodes():
    payload = build_graph_payload()
    return jsonify({'top_nodes': payload['top_nodes']})


@app.route('/api/node/<int:node_id>')
def api_node(node_id):
    payload = build_graph_payload()
    node = next((item for item in payload['nodes_data'] if item['id'] == node_id), None)
    if node is None:
        abort(404, description='Node không tồn tại')
    return jsonify(node)


@app.route('/api/clusters')
def api_clusters():
    payload = build_graph_payload()
    return jsonify({'clusters': payload['clusters']})


@app.route('/api/sir-results')
def api_sir_results():
    """Fetch SIR simulation results"""
    output_dir = request.args.get('output_dir')
    model = request.args.get('model', 'pure')

    if not output_dir or not Path(output_dir).exists():
        return jsonify({'error': 'Thư mục output không tồn tại'}), 400

    try:
        output_path = Path(output_dir)
        
        # Determine which folder contains the results
        sir_subfolder = output_path / ('Pure_SIR' if model == 'pure' else 'SIR_dynamic_immunization')
        
        if not sir_subfolder.exists():
            sir_subfolder = output_path
        
        history_file = sir_subfolder / 'sir_history.csv'
        
        if not history_file.exists():
            return jsonify({'error': f'File kết quả không tìm thấy: {history_file}'}), 404

        # Load history data
        history_df = pd.read_csv(history_file)
        history = history_df.to_dict(orient='records')

        # Calculate statistics
        peak_day = int(history_df['I'].idxmax())
        peak_infected = int(history_df['I'].max())
        final_day = len(history) - 1

        return jsonify({
            'model': model,
            'output_dir': output_dir,
            'history': history,
            'statistics': {
                'peak_day': peak_day,
                'peak_infected': peak_infected,
                'final_day': final_day,
            }
        })

    except Exception as e:
        logger.error(f'Error loading SIR results: {e}')
        return jsonify({'error': f'Lỗi tải dữ liệu: {str(e)}'}), 500


@app.route('/api/simulate-sir', methods=['POST'])
def api_simulate_sir():
    """Alias for /api/run-simulate for backward compatibility"""
    payload = request.get_json() or {}
    model = payload.get('model', 'pure')
    transmission_rate = float(payload.get('transmission_rate', 0.3))
    recovery_rate = float(payload.get('recovery_rate', 0.02))
    days = int(payload.get('days', 300))
    seed = int(payload.get('seed', 42))
    top_k = int(payload.get('top_k', 10))
    strategy = str(payload.get('strategy', 'betweenness'))
    
    # Get the latest output directory if not specified
    output_dir = payload.get('output_dir')
    if not output_dir:
        output_dir = get_latest_output_dir()
    
    try:
        if model == 'dynamic':
            sim = SIRDynamicImmunization(output_dir=output_dir, top_k=top_k, strategy=strategy)
            sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, days=days, seed=seed)
            peak_day, peak_I, final_day = sim.get_statistics()
            
            # Load history
            history_file = Path(sim.results_dir) / 'sir_history.csv'
            history_df = pd.read_csv(history_file)
            history = history_df.to_dict(orient='records')
            
            return jsonify({
                'model': 'dynamic',
                'output_directory': sim.results_dir,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'top_k': top_k,
                'strategy': strategy,
                'history': history,
                'redirect_url': sir_view_url('dynamic', sim.results_dir),
            })
        else:
            sim = PureSIRSimulation(output_dir=output_dir)
            sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, max_days=days, seed=seed)
            peak_day, peak_I, final_day = sim.get_statistics()
            sim.save()
            
            # Load history
            history_file = Path(sim.results_dir) / 'sir_history.csv'
            history_df = pd.read_csv(history_file)
            history = history_df.to_dict(orient='records')
            
            return jsonify({
                'model': 'pure',
                'output_directory': sim.results_dir,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
                'seed': seed,
                'history': history,
                'redirect_url': sir_view_url('pure', sim.results_dir),
            })
    except Exception as e:
        logger.error(f'Error in simulation: {e}')
        return jsonify({'error': f'Lỗi mô phỏng: {str(e)}'}), 500


@app.route('/api/run-generator', methods=['POST'])
def api_run_generator():
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


@app.route('/api/run-simulate', methods=['POST'])
def api_run_simulate():
    payload = request.get_json() or {}
    model = payload.get('model', 'pure')
    output_dir = payload.get('output_dir')
    transmission_rate = float(payload.get('transmission_rate', 0.3))
    recovery_rate = float(payload.get('recovery_rate', 0.02))
    days = int(payload.get('days', 300))
    seed = int(payload.get('seed', 42))
    top_k = int(payload.get('top_k', 10))
    strategy = str(payload.get('strategy', 'betweenness'))

    if model == 'dynamic':
        sim = SIRDynamicImmunization(output_dir=output_dir, top_k=top_k, strategy=strategy)
        sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, days=days, seed=seed)
        peak_day, peak_I, final_day = sim.get_statistics()
        return jsonify({
            'model': 'dynamic',
            'output_directory': sim.results_dir,
            'peak_day': peak_day,
            'peak_infected': peak_I,
            'final_day': final_day,
            'top_k': top_k,
            'strategy': strategy,
            'redirect_url': sir_view_url('dynamic', sim.results_dir),
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
        'seed': seed,
        'redirect_url': sir_view_url('pure', sim.results_dir),
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

        # On Render, filesystem may be ephemeral: write uploaded outputs to configured dir (if any)
        output_root_env = os.getenv('MO_PHONG_OUTPUT_DIR')
        output_root = Path(output_root_env) if output_root_env else BASE_DIR
        output_dir = output_root / f"output_uploaded_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_dir.mkdir(parents=True, exist_ok=True)


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

        # Calculate metrics
        metrics_data = []
        for user in generator.users:
            node_id = user['id']
            degree = G.degree[node_id] if node_id in G else 0
            betweenness = nx.betweenness_centrality(G).get(node_id, 0)
            eigenvector = nx.eigenvector_centrality(G, max_iter=1000).get(node_id, 0)

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

        return jsonify({
            'output_folder': str(output_dir),
            'nodes': len(generator.users),
            'edges': len(generator.relationships),
            'message': f'Upload và xử lý thành công {len(generator.users)} người dùng từ file CSV'
        })

    except Exception as e:
        logger.error(f'Error processing uploaded file: {e}')
        return jsonify({'error': f'Lỗi xử lý file: {str(e)}'}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': str(error)}), 404


@app.route('/api/health')
def api_health():
    latest = get_latest_output_dir()
    return jsonify({
        'status': 'ok',
        'latest_output': str(latest) if latest else None,
        'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    })


@app.route('/api/cleanup-outputs', methods=['POST'])
def api_cleanup_outputs():
    payload = request.get_json() or {}
    keep_latest = max(1, int(payload.get('keep_latest', 3)))
    include_uploaded = bool(payload.get('include_uploaded', True))

    output_dirs = [p for p in BASE_DIR.glob('output_*') if p.is_dir() and p.name != 'output_archive']
    if not include_uploaded:
        output_dirs = [p for p in output_dirs if not p.name.startswith('output_uploaded_')]

    output_dirs = sorted(output_dirs, key=lambda p: p.stat().st_mtime, reverse=True)
    removable = output_dirs[keep_latest:]

    removed = []
    for folder in removable:
        try:
            shutil.rmtree(folder)
            removed.append(folder.name)
        except Exception as exc:
            logger.warning('Không thể xóa %s: %s', folder, exc)

    return jsonify({
        'removed_count': len(removed),
        'removed': removed,
        'kept': [p.name for p in output_dirs[:keep_latest]],
    })


if __name__ == '__main__':
    # Local dev only. On Render we use gunicorn + $PORT.
    app.run(debug=True, port=8000)

