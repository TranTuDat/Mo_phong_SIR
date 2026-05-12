from flask import Flask, jsonify, request, send_from_directory, abort
from pathlib import Path
from typing import Optional
import pandas as pd
import networkx as nx
import numpy as np
import os
import datetime
import logging
import tempfile
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


def get_latest_output_dir() -> Optional[Path]:
    env_path = os.getenv('MO_PHONG_OUTPUT_DIR')
    if env_path:
        output_dir = Path(env_path)
        if output_dir.exists() and output_dir.is_dir():
            return output_dir

    output_roots = [BASE_DIR]
    fallback_root = Path(os.getenv('MO_PHONG_OUTPUT_ROOT', tempfile.gettempdir())) / 'mo_phong_outputs'
    if fallback_root.exists():
        output_roots.append(fallback_root)

    candidates = [p for root in output_roots for p in root.glob('output_*') if p.is_dir()]
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
            'color': RISK_COLORS.get(risk, '#9ca3af')
        })
    return payload


def build_graph_payload():
    global _cached_graph, _cached_payload, _cached_output
    try:
        folder, users, relationships, metrics = load_output_data()
    except FileNotFoundError as e:
        logger.error(f'Data not found: {e}')
        raise Exception(f'Không tìm thấy dữ liệu: {str(e)}')
    
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


@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(str(BASE_DIR), path)


@app.route('/api/summary')
def api_summary():
    try:
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
    except Exception as e:
        logger.error(f'Error in api_summary: {e}')
        return jsonify({'error': str(e)}), 500


@app.route('/api/graph')
def api_graph():
    try:
        payload = build_graph_payload()
        return jsonify(payload)
    except Exception as e:
        logger.error(f'Error in api_graph: {e}')
        return jsonify({'error': str(e)}), 500


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

        if model == 'dynamic':
            sim = SIRDynamicImmunization(output_dir=output_dir)
            sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, days=days)
            peak_day, peak_I, final_day = sim.get_statistics()
            return jsonify({
                'model': 'dynamic',
                'output_directory': sim.results_dir,
                'peak_day': peak_day,
                'peak_infected': peak_I,
                'final_day': final_day,
            })

        sim = PureSIRSimulation(output_dir=output_dir)
        sim.simulate(transmission_rate=transmission_rate, recovery_rate=recovery_rate, max_days=days)
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
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port)
