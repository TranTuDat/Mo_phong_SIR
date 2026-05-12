"""
Module tạo và phân tích mạng xã hội
Chức năng: Tạo mạng xã hội ngẫu nhiên, tính toán chỉ số mạng, trực quan hóa đồ thị
"""

import pandas as pd
import networkx as nx
import matplotlib
matplotlib.use('Agg')  # Use non-GUI backend
import matplotlib.pyplot as plt
import os
import numpy as np
import random
import logging
from datetime import datetime
from pathlib import Path

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
            output_dir = Path(__file__).resolve().parent / f"output_{self.num_users}_users_{timestamp}"
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
    
    def generate_relationships(self, relationship_probability: float = 0.15) -> list:
        """
        Tạo quan hệ giữa người dùng
        
        Args:
            relationship_probability (float): Xác suất tạo quan hệ (0-1)
            
        Returns:
            list: Danh sách quan hệ
            
        Raises:
            ValueError: Nếu xác suất không trong khoảng [0, 1]
        """
        if not (0 <= relationship_probability <= 1):
            raise ValueError("relationship_probability phải trong khoảng [0, 1]")
        
        try:
            logger.info(f"Bắt đầu tạo quan hệ (xác suất: {relationship_probability*100}%)...")
            
            user_ids = [u['user_id'] for u in self.users]
            for i, user1_id in enumerate(user_ids):
                for user2_id in user_ids[i+1:]:
                    if random.random() < relationship_probability:
                        self.relationships.append({'user1_id': user1_id, 'user2_id': user2_id})
            
            logger.info(f"✓ Đã tạo {len(self.relationships)} quan hệ thành công")
            return self.relationships
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
            
            betweenness = nx.betweenness_centrality(self.graph)
            degree = nx.degree_centrality(self.graph)
            
            # Xử lý eigenvector centrality với error handling
            try:
                eigenvector = nx.eigenvector_centrality(self.graph, max_iter=1000)
            except nx.NetworkXError:
                logger.warning("Không thể tính eigenvector centrality, sử dụng giá trị 0")
                eigenvector = {node: 0 for node in self.graph.nodes()}
            
            node_ids = list(self.graph.nodes())
            metrics_df = pd.DataFrame({
                'user_id': node_ids,
                'betweenness_centrality': [betweenness.get(node, 0) for node in node_ids],
                'degree_centrality': [degree.get(node, 0) for node in node_ids],
                'eigenvector_centrality': [eigenvector.get(node, 0) for node in node_ids],
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
            
            adj_matrix = nx.to_pandas_adjacency(self.graph)
            adj_matrix_csv = os.path.join(self.output_dir, 'adjacency_matrix.csv')
            adj_matrix.to_csv(adj_matrix_csv)
            logger.info(f"✓ Lưu ma trận kề: {adj_matrix_csv}")
            
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
            betweenness = dict(zip(metrics['user_id'], metrics['betweenness_centrality']))
            eigenvector = dict(zip(metrics['user_id'], metrics['eigenvector_centrality']))
            
            # Biểu đồ 1: Đồ thị mạng xã hội
            ax1 = axes[0]
            pos = nx.spring_layout(self.graph, k=0.5, iterations=50, seed=42)
            node_sizes = [max(50, degree.get(node, 0.01) * 300) for node in self.graph.nodes()]
            
            nx.draw_networkx_nodes(self.graph, pos, node_size=node_sizes, node_color='lightblue', 
                                  ax=ax1, edgecolors='steelblue', linewidths=0.5)
            nx.draw_networkx_edges(self.graph, pos, edge_color='gray', alpha=0.2, ax=ax1, width=0.5)
            ax1.set_title('Đồ thị mạng xã hội vô hướng\n(Kích thước node = Degree)', fontsize=12, pad=10)
            ax1.axis('off')
            
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
            logger.error(f"Lỗi khi trực quan hóa đồ thị: {e}")
            raise
    
    def print_statistics(self) -> None:
        """In thống kê mạng xã hội"""
        if self.graph is None:
            logger.warning("Chưa có đồ thị để in thống kê")
            return
        
        try:
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
            self.print_statistics()
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
