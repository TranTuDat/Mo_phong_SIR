"""
Module tạo và phân tích mạng xã hội
Chức năng: Tạo mạng xã hội ngẫu nhiên, tính toán chỉ số mạng, trực quan hóa đồ thị
"""

import math
import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import os
import numpy as np
import random
import logging
import tempfile
from datetime import datetime
from pathlib import Path

from .graph_draw import draw_network_test_style
from .deploy_env import betweenness_sample_k, skip_heavy_viz, use_fast_graph_algorithms

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _default_output_root() -> Path:
    """Thư mục ghi dataset — trên Render dùng /tmp (ổ ghi được, tránh read-only)."""
    explicit = os.getenv('MO_PHONG_OUTPUT_ROOT', '').strip()
    if explicit:
        return Path(explicit).resolve() / 'mo_phong_outputs'
    if os.getenv('RENDER') or os.getenv('RENDER_SERVICE_ID'):
        return Path(tempfile.gettempdir()) / 'mo_phong_outputs'
    return _REPO_ROOT.resolve() / 'outputs'


OUTPUT_ROOT = _default_output_root()
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)


# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SocialNetworkGenerator:
    """
    Lớp tạo và phân tích mạng xã hội
    
    Attributes:
        num_users (int): Số lượng người dùng
        seed (int): Seed cho random
        users (list): Danh sách người dùng
        relationships (list): Danh sách quan hệ
        graph (nx.Graph): Đồ thị NetworkX
        output_dir (str): Thư mục output
    """
    
    def __init__(self, num_users: int = 100, seed: int = 42):
        """
        Khởi tạo bộ tạo mạng xã hội
        
        Args:
            num_users (int): Số lượng người dùng (mặc định 100)
            seed (int): Seed cho random (mặc định 42)
            
        Raises:
            ValueError: Nếu num_users <= 0
        """
        if num_users <= 0:
            raise ValueError("num_users phải > 0")
        
        self.num_users = num_users
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
        
        self.users = []
        self.relationships = []
        self.graph = None
        self.output_dir = self._create_output_dir()
        logger.info(f"Khởi tạo SocialNetworkGenerator: {num_users} users, seed={seed}")
    
    def _create_output_dir(self) -> str:
        """
        Tạo thư mục output với timestamp
        
        Returns:
            str: Đường dẫn thư mục output
            
        Raises:
            OSError: Nếu không thể tạo thư mục
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = OUTPUT_ROOT / f"output_{self.num_users}_users_{timestamp}"
            output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Thư mục output được tạo: {output_dir}")
            return str(output_dir)
        except OSError as e:
            logger.error(f"Lỗi tạo thư mục output: {e}")
            raise
    
    def generate_users(self) -> list:
        """
        Tạo danh sách người dùng với thông tin ngẫu nhiên
        
        Returns:
            list: Danh sách người dùng
        """
        try:
            logger.info(f"Bắt đầu tạo {self.num_users} người dùng...")
            
            first_names = ["Lê", "Trần", "Nguyễn", "Phạm", "Hoàng", "Phan", "Tôn", "Võ", "Bùi", "Đặng"]
            last_names = ["An", "Bình", "Công", "Dũng", "Em", "Phú", "Giang", "Hà", "Ích", "Kiên"]
            
            for user_id in range(1, self.num_users + 1):
                user = {
                    'user_id': user_id,
                    'name': f"{random.choice(first_names)} {random.choice(last_names)}",
                    'followers_count': random.randint(0, 1000),
                    'posts_count': random.randint(0, 500),
                    'join_date': f"2020-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                    'verified': random.choice([0, 0, 0, 1])
                }
                self.users.append(user)
            
            logger.info(f"✓ Đã tạo {len(self.users)} người dùng thành công")
            return self.users
        except Exception as e:
            logger.error(f"Lỗi khi tạo người dùng: {e}")
            raise
    
    def generate_uniform_relationships(self, relationship_probability: float = 0.025) -> list:
        """
        Mô hình Erdős–Rényi G(n, p): mọi cặp nút có cùng xác suất tạo cạnh p.
        Cụm cộng đồng được phát hiện sau khi đã có đồ thị (greedy modularity).
        """
        if not (0 <= relationship_probability <= 1):
            raise ValueError("relationship_probability phải trong khoảng [0, 1]")
        if not self.users:
            raise ValueError("Chưa có người dùng")

        p = relationship_probability
        user_ids = [int(u['user_id']) for u in self.users]
        self.relationships = []
        seen: set[tuple[int, int]] = set()

        def add_edge(a: int, b: int) -> None:
            if a == b:
                return
            key = (min(a, b), max(a, b))
            if key in seen:
                return
            seen.add(key)
            self.relationships.append({'user1_id': a, 'user2_id': b})

        for i in range(len(user_ids)):
            for j in range(i + 1, len(user_ids)):
                if random.random() < p:
                    add_edge(user_ids[i], user_ids[j])

        logger.info(
            "✓ Quan hệ đồng nhất G(n,p): p=%.4f, %d nút, %d cạnh",
            p,
            len(user_ids),
            len(self.relationships),
        )
        return self.relationships

    def assign_detected_communities(self) -> None:
        """Gán community_id sau khi có đồ thị — không gán trước khi tạo cạnh."""
        if self.graph is None:
            raise ValueError("Chưa có đồ thị. Gọi create_graph() trước")

        n = self.graph.number_of_nodes()
        if use_fast_graph_algorithms(n):
            logger.info('Phát hiện cụm: một cụm (mạng lớn / server)')
            communities = [set(self.graph.nodes())] if n else []
        else:
            try:
                communities = list(nx.community.greedy_modularity_communities(self.graph))
            except Exception as exc:
                logger.warning('greedy_modularity thất bại (%s); gộp một cụm', exc)
                communities = [set(self.graph.nodes())] if n else []

        communities = sorted(communities, key=lambda c: (-len(c), min(c)))
        node_to_comm: dict[int, int] = {}
        for idx, comm in enumerate(communities):
            for nid in comm:
                node_to_comm[int(nid)] = idx

        for u in self.users:
            uid = int(u['user_id'])
            u['community_id'] = node_to_comm.get(uid, 0)

        logger.info("✓ Phát hiện %d cụm trên đồ thị đã tạo", len(communities))

    def generate_community_relationships(
        self,
        relationship_probability: float = 0.025,
        *,
        num_communities: int | None = None,
    ) -> list:
        """
        (Legacy) Tạo quan hệ theo cấu trúc cộng đồng đặt trước: dày trong cụm, thưa giữa cụm.
        Không dùng mặc định — giữ để tham chiếu / thử nghiệm.
        """
        if not (0 <= relationship_probability <= 1):
            raise ValueError("relationship_probability phải trong khoảng [0, 1]")
        if not self.users:
            raise ValueError("Chưa có người dùng")

        n = self.num_users
        k = num_communities or max(8, min(15, int(round(math.sqrt(n) * 0.55))))
        p_in = min(0.22, max(0.05, relationship_probability * 3.8))
        p_out = min(0.006, max(0.0004, relationship_probability * 0.12))

        user_ids = [u['user_id'] for u in self.users]
        random.shuffle(user_ids)
        communities: list[list[int]] = [[] for _ in range(k)]
        for i, uid in enumerate(user_ids):
            communities[i % k].append(uid)
            for u in self.users:
                if u['user_id'] == uid:
                    u['community_id'] = i % k

        self.relationships = []
        seen: set[tuple[int, int]] = set()

        def add_edge(a: int, b: int) -> None:
            if a == b:
                return
            key = (min(a, b), max(a, b))
            if key in seen:
                return
            seen.add(key)
            self.relationships.append({'user1_id': a, 'user2_id': b})

        for comm in communities:
            for i, u1 in enumerate(comm):
                for u2 in comm[i + 1 :]:
                    if random.random() < p_in:
                        add_edge(u1, u2)

        for i, c1 in enumerate(communities):
            for c2 in communities[i + 1 :]:
                for u1 in c1:
                    for u2 in c2:
                        if random.random() < p_out:
                            add_edge(u1, u2)

        logger.info(
            "✓ Quan hệ theo %d cụm (p_in=%.4f, p_out=%.5f): %d cạnh",
            k,
            p_in,
            p_out,
            len(self.relationships),
        )
        return self.relationships

    def generate_relationships(self, relationship_probability: float = 0.15) -> list:
        """Tạo quan hệ — mọi cặp nút cùng xác suất p (mô hình G(n, p))."""
        try:
            logger.info(
                "Bắt đầu tạo quan hệ đồng nhất G(n,p), p=%s%%...",
                relationship_probability * 100,
            )
            return self.generate_uniform_relationships(relationship_probability)
        except Exception as e:
            logger.error(f"Lỗi khi tạo quan hệ: {e}")
            raise
    
    def create_graph(self) -> nx.Graph:
        """
        Tạo đồ thị NetworkX từ người dùng và quan hệ
        
        Returns:
            nx.Graph: Đồ thị được tạo
            
        Raises:
            ValueError: Nếu chưa tạo người dùng hoặc quan hệ
        """
        if not self.users:
            raise ValueError("Chưa có người dùng. Gọi generate_users() trước")
        
        try:
            logger.info("Bắt đầu tạo đồ thị...")
            
            self.graph = nx.Graph()
            for user in self.users:
                self.graph.add_node(user['user_id'], **user)
            for rel in self.relationships:
                self.graph.add_edge(rel['user1_id'], rel['user2_id'])
            
            logger.info(f"✓ Đồ thị được tạo: {self.graph.number_of_nodes()} node, {self.graph.number_of_edges()} cạnh")
            return self.graph
        except Exception as e:
            logger.error(f"Lỗi khi tạo đồ thị: {e}")
            raise
    
    def calculate_metrics(self) -> pd.DataFrame:
        """
        Tính toán các chỉ số mạng (centrality measures)
        
        Returns:
            pd.DataFrame: DataFrame chứa các chỉ số
            
        Raises:
            ValueError: Nếu chưa tạo đồ thị
        """
        if self.graph is None:
            raise ValueError("Chưa có đồ thị. Gọi create_graph() trước")
        
        try:
            logger.info("Bắt đầu tính toán các chỉ số mạng...")
            
            n = self.graph.number_of_nodes()
            k_bet = betweenness_sample_k(n)
            if k_bet is None:
                betweenness = nx.betweenness_centrality(self.graph)
            else:
                logger.info('Betweenness xấp xỉ (k=%s) cho %s nút', k_bet, n)
                betweenness = nx.betweenness_centrality(self.graph, k=k_bet)
            degree = nx.degree_centrality(self.graph)
            
            # Xử lý eigenvector centrality với error handling
            try:
                eigenvector = nx.eigenvector_centrality(self.graph, max_iter=1000)
            except nx.NetworkXError:
                logger.warning("Không thể tính eigenvector centrality, sử dụng giá trị 0")
                eigenvector = {node: 0 for node in self.graph.nodes()}

            try:
                pagerank = nx.pagerank(self.graph, alpha=0.85, max_iter=200, tol=1e-06)
            except Exception:
                logger.warning("Không thể tính PageRank, sử dụng degree làm proxy")
                pagerank = {node: float(degree.get(node, 0)) for node in self.graph.nodes()}
            
            node_ids = list(self.graph.nodes())
            metrics_df = pd.DataFrame({
                'user_id': node_ids,
                'betweenness_centrality': [betweenness.get(node, 0) for node in node_ids],
                'degree_centrality': [degree.get(node, 0) for node in node_ids],
                'eigenvector_centrality': [eigenvector.get(node, 0) for node in node_ids],
                'pagerank': [pagerank.get(node, 0) for node in node_ids],
            })
            
            metrics_df = metrics_df.sort_values('betweenness_centrality', ascending=False)
            
            logger.info(f"✓ Đã tính toán chỉ số cho {len(metrics_df)} người dùng")
            return metrics_df
        except Exception as e:
            logger.error(f"Lỗi khi tính toán chỉ số: {e}")
            raise
    
    def save_data(self) -> pd.DataFrame:
        """
        Lưu dữ liệu vào các file CSV
        
        Returns:
            pd.DataFrame: DataFrame chỉ số mạng
            
        Raises:
            OSError: Nếu lỗi ghi file
        """
        try:
            logger.info("Bắt đầu lưu dữ liệu...")
            
            users_df = pd.DataFrame(self.users)
            users_csv = os.path.join(self.output_dir, 'users.csv')
            users_df.to_csv(users_csv, index=False)
            logger.info(f"✓ Lưu danh sách người dùng: {users_csv}")
            
            relationships_df = pd.DataFrame(self.relationships)
            relationships_csv = os.path.join(self.output_dir, 'relationships.csv')
            relationships_df.to_csv(relationships_csv, index=False)
            logger.info(f"✓ Lưu quan hệ: {relationships_csv}")
            
            if not skip_heavy_viz() and self.num_users <= 800:
                adj_matrix = nx.to_pandas_adjacency(self.graph)
                adj_matrix_csv = os.path.join(self.output_dir, 'adjacency_matrix.csv')
                adj_matrix.to_csv(adj_matrix_csv)
                logger.info(f"✓ Lưu ma trận kề: {adj_matrix_csv}")
            else:
                logger.info('Bỏ qua ma trận kề (tiết kiệm RAM trên server)')
            
            metrics_df = self.calculate_metrics()
            metrics_csv = os.path.join(self.output_dir, 'metrics.csv')
            metrics_df.to_csv(metrics_csv, index=False)
            logger.info(f"✓ Lưu chỉ số mạng: {metrics_csv}")
            
            return metrics_df
        except OSError as e:
            logger.error(f"Lỗi khi lưu dữ liệu: {e}")
            raise
    
    def visualize_graph(self, figsize: tuple = (18, 6)) -> None:
        """
        Trực quan hóa đồ thị mạng xã hội
        
        Args:
            figsize (tuple): Kích thước hình (mặc định (18, 6))
            
        Raises:
            ValueError: Nếu chưa tạo đồ thị
        """
        if self.graph is None:
            raise ValueError("Chưa có đồ thị. Gọi create_graph() trước")
        
        try:
            logger.info("Bắt đầu trực quan hóa đồ thị...")
            
            fig, axes = plt.subplots(1, 3, figsize=figsize)
            fig.suptitle(f'Mạng Xã Hội ({self.num_users} người dùng)', fontsize=18, fontweight='bold', y=1.02)
            
            metrics = self.calculate_metrics()
            degree = dict(zip(metrics['user_id'], metrics['degree_centrality']))
            n_nodes = self.graph.number_of_nodes()
            use_degree_sizes = n_nodes <= 300

            # Biểu đồ 1: kiểu Test.py (node nhỏ, cạnh mảnh — ổn với mạng lớn)
            ax1 = axes[0]
            draw_network_test_style(
                self.graph,
                ax1,
                seed=self.seed,
                use_degree_sizes=use_degree_sizes,
                metrics_degree=degree,
            )
            if use_degree_sizes:
                ax1.set_title(
                    'Đồ thị mạng xã hội\n(kích thước nút ∝ Degree)',
                    fontsize=12,
                    pad=10,
                )
            else:
                ax1.set_title(
                    f'Đồ thị mạng xã hội ({n_nodes} nút)\n'
                    f'kiểu Test.py — node nhỏ, cạnh mảnh',
                    fontsize=12,
                    pad=10,
                )
            
            # Biểu đồ 2: Top 10 theo Degree Centrality
            ax2 = axes[1]
            top_10 = metrics.nlargest(10, 'degree_centrality')[['user_id', 'degree_centrality']]
            ax2.barh(range(len(top_10)), top_10['degree_centrality'].values, color='lightgreen', 
                    edgecolor='darkgreen', linewidth=1)
            ax2.set_yticks(range(len(top_10)))
            ax2.set_yticklabels(top_10['user_id'].values, fontsize=10)
            ax2.set_xlabel('Degree Centrality', fontsize=11, fontweight='bold')
            ax2.set_title('Top 10 theo Degree Centrality', fontsize=12, pad=10)
            ax2.invert_yaxis()
            ax2.grid(axis='x', alpha=0.3, linestyle='--')
            
            # Biểu đồ 3: Top 10 theo Betweenness Centrality
            ax3 = axes[2]
            top_10_betweenness = metrics.nlargest(10, 'betweenness_centrality')[['user_id', 'betweenness_centrality']]
            ax3.barh(range(len(top_10_betweenness)), top_10_betweenness['betweenness_centrality'].values, 
                    color='lightcoral', edgecolor='darkred', linewidth=1)
            ax3.set_yticks(range(len(top_10_betweenness)))
            ax3.set_yticklabels(top_10_betweenness['user_id'].values, fontsize=10)
            ax3.set_xlabel('Betweenness Centrality', fontsize=11, fontweight='bold')
            ax3.set_title('Top 10 theo Betweenness', fontsize=12, pad=10)
            ax3.invert_yaxis()
            ax3.grid(axis='x', alpha=0.3, linestyle='--')
            
            plt.tight_layout()
            graph_png = os.path.join(self.output_dir, 'graph_visualization.png')
            plt.savefig(graph_png, dpi=150, bbox_inches='tight', facecolor='white')
            logger.info(f"✓ Lưu hình trực quan: {graph_png}")
            
            plt.close()
        except Exception as e:
            logger.warning('Bỏ qua lưu PNG (matplotlib không bắt buộc trên server): %s', e)
    
    def print_statistics(self) -> None:
        """In thống kê mạng xã hội"""
        if self.graph is None:
            logger.warning("Chưa có đồ thị để in thống kê")
            return
        
        try:
            if use_fast_graph_algorithms(self.graph.number_of_nodes()):
                diameter = 'N/A (mạng lớn / server)'
            else:
                diameter = nx.diameter(self.graph) if nx.is_connected(self.graph) else "N/A"
            
            logger.info("="*60)
            logger.info("THỐNG KÊ MẠNG XÃ HỘI")
            logger.info("="*60)
            logger.info(f"Số người dùng: {self.graph.number_of_nodes()}")
            logger.info(f"Số quan hệ: {self.graph.number_of_edges()}")
            logger.info(f"Mật độ mạng: {nx.density(self.graph):.4f}")
            logger.info(f"Đường kính: {diameter}")
            logger.info("="*60)
        except Exception as e:
            logger.error(f"Lỗi khi in thống kê: {e}")
    
    def run(self, num_users: int = None, relationship_prob: float = 0.15) -> pd.DataFrame:
        """
        Chạy toàn bộ quá trình tạo và phân tích mạng
        
        Args:
            num_users (int): Số người dùng (nếu khác với khởi tạo)
            relationship_prob (float): Xác suất tạo quan hệ
            
        Returns:
            pd.DataFrame: DataFrame chỉ số mạng
        """
        try:
            if num_users:
                if num_users <= 0:
                    raise ValueError("num_users phải > 0")
                self.num_users = num_users
            
            if not (0 <= relationship_prob <= 1):
                raise ValueError("relationship_prob phải trong khoảng [0, 1]")
            
            logger.info("#"*60)
            logger.info("# Tạo MẠNG XÃ HỘI và PHÂN TÍCH ĐỒ THỊ")
            logger.info(f"# Số người dùng: {self.num_users}")
            logger.info(f"# Output: {self.output_dir}")
            logger.info("#"*60)
            
            self.generate_users()
            self.generate_relationships(relationship_prob)
            self.create_graph()
            self.assign_detected_communities()
            self.print_statistics()
            if skip_heavy_viz():
                logger.info('Bỏ qua visualize_graph (MO_PHONG_SKIP_VIZ / Render)')
            else:
                self.visualize_graph()
            metrics_df = self.save_data()
            
            logger.info("="*60)
            logger.info("✓ HOÀN THÀNH!")
            logger.info("="*60)
            logger.info(f"Output được lưu tại: {self.output_dir}")
            
            return metrics_df
        except Exception as e:
            logger.error(f"Lỗi trong quá trình chạy: {e}")
            raise


def main():
    """Hàm chính"""
    try:
        NUM_USERS = 500
        RELATIONSHIP_PROB = 0.025
        
        generator = SocialNetworkGenerator(num_users=NUM_USERS, seed=42)
        metrics = generator.run(relationship_prob=RELATIONSHIP_PROB)
        
        logger.info("\nTop 10 Người dùng có ảnh hưởng nhất:")
        top_10_str = metrics[['user_id', 'betweenness_centrality', 'degree_centrality', 'eigenvector_centrality']].head(10).to_string(index=False)
        logger.info("\n" + top_10_str)
    except Exception as e:
        logger.error(f"Lỗi trong hàm main: {e}")
        raise


if __name__ == "__main__":
    main()
