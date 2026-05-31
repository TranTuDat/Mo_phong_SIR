
import os
import json
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import random
import logging
from pathlib import Path

from .centrality_scores import (
    CENTRALITY_STRATEGIES,
    compute_centrality_scores,
    misinfo_source_labels,
    normalize_dynamic_strategy,
    normalize_misinfo_mode,
    pick_top_nodes_by_score,
)
from .deploy_env import betweenness_sample_k
from .sir_sim_paths import (
    dynamic_dataset_subdir_fs,
    pure_dataset_subdir_fs,
)

# Cấu hình logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def epidemic_final_day_from_history(history: pd.DataFrame) -> int:
    """
    Ngày kết thúc dịch: ngày đầu tiên sau ngày 0 mà không còn nút I (hết nguồn lây).
    Nếu đến hết chuỗi vẫn còn I, lấy ngày cuối đã ghi.
    """
    ended = history[(history['I'] == 0) & (history['day'] > 0)]
    if not ended.empty:
        return int(ended['day'].iloc[0])
    return int(history['day'].iloc[-1])


def sir_epidemic_totals_from_history(
    history: pd.DataFrame,
    n_nodes: int | None = None,
) -> tuple[int, int]:
    """
    (total_ever_infected, never_infected) tại ngày kết thúc dịch (I=0).

    - total_ever_infected: số nút từng ở trạng thái I (bệnh), không tính miễn nhiễm từ S.
    - never_infected: nút còn S — không từng nhiễm (cô lập hoặc không tiếp xúc dịch).
    """
    final_day = epidemic_final_day_from_history(history)
    sub = history[history['day'] <= final_day]
    if sub.empty:
        sub = history
    row = sub[sub['day'] == final_day]
    if row.empty:
        row = sub.iloc[-1:]
    s_end = int(row['S'].iloc[0])
    if 'cum_infected' in history.columns:
        total = int(sub['cum_infected'].max())
    else:
        total = int(row['R'].iloc[0])
    never = s_end
    if n_nodes is not None and n_nodes > 0 and 'cum_infected' not in history.columns:
        never = max(0, min(s_end, n_nodes - total))
    return total, never


def _drop_invalid_relationship_rows(
    relationships: pd.DataFrame, source_col: str, target_col: str
) -> pd.DataFrame:
    rels = relationships.copy()
    rels[source_col] = pd.to_numeric(rels[source_col], errors='coerce')
    rels[target_col] = pd.to_numeric(rels[target_col], errors='coerce')
    before = len(rels)
    rels = rels.dropna(subset=[source_col, target_col], how='any')
    dropped = before - len(rels)
    if dropped:
        logger.warning(
            'relationships.csv: bỏ %s dòng không hợp lệ (thiếu %s/%s)',
            dropped,
            source_col,
            target_col,
        )
    if rels.empty:
        raise ValueError('relationships.csv không còn cạnh hợp lệ sau khi lọc')
    return rels


def _discover_dataset_dirs() -> list[Path]:
    """Các thư mục output_* / output_uploaded_* trong outputs/ và (legacy) root repo."""
    out = _REPO_ROOT / 'outputs'
    found: list[Path] = []
    if out.is_dir():
        found.extend(p for p in out.glob('output_*') if p.is_dir())
        found.extend(p for p in out.glob('output_uploaded_*') if p.is_dir())
    found.extend(p for p in _REPO_ROOT.glob('output_*') if p.is_dir())
    found.extend(p for p in _REPO_ROOT.glob('output_uploaded_*') if p.is_dir())
    return found


class PureSIRSimulation:
    """
    Lớp mô phỏng mô hình SIR thuần
    
    Attributes:
        output_dir (str): Thư mục chứa dữ liệu input
        graph (nx.Graph): Đồ thị mạng xã hội
        users (pd.DataFrame): Dữ liệu người dùng
        relationships (pd.DataFrame): Dữ liệu quan hệ
        history (pd.DataFrame): Lịch sử mô phỏng
        results_dir (str): Thư mục lưu kết quả
    """
    
    def __init__(
        self,
        output_dir: str = None,
        *,
        graph: nx.Graph | None = None,
        users: pd.DataFrame | None = None,
        relationships: pd.DataFrame | None = None,
    ):
        """
        Khởi tạo mô phỏng SIR
        
        Args:
            output_dir (str): Thư mục chứa dữ liệu (nếu None tìm tự động)
            
        Raises:
            FileNotFoundError: Nếu không tìm thấy thư mục output
        """
        self.output_dir = self._find_output_dir(output_dir)

        self.graph = graph
        self.users = users
        self.relationships = relationships
        self.history = None
        self.results_dir = None

        if self.graph is None:
            self._load_data()

    # ========================
    # LOAD DATA
    # ========================
    def _find_output_dir(self, path: str) -> str:
        """
        Tìm thư mục output
        
        Args:
            path (str): Đường dẫn thư mục (nếu cung cấp)
            
        Returns:
            str: Đường dẫn thư mục output tìm được
            
        Raises:
            FileNotFoundError: Nếu không tìm thấy thư mục
        """
        if path and os.path.exists(path):
            return path

        # Find the most recent output folder
        output_folders = _discover_dataset_dirs()
        if output_folders:
            # Sort by modification time, get the most recent
            most_recent = max(output_folders, key=lambda p: p.stat().st_mtime)
            return str(most_recent)

        raise FileNotFoundError("Không tìm thấy folder output!")

    def _load_data(self) -> None:
        """
        Tải dữ liệu từ CSV và xây dựng đồ thị
        
        Raises:
            FileNotFoundError: Nếu file dữ liệu không tồn tại
        """
        try:
            logger.info(f"📁 Load dữ liệu từ: {self.output_dir}\n")

            self.users = pd.read_csv(os.path.join(self.output_dir, 'users.csv'))
            self.relationships = pd.read_csv(os.path.join(self.output_dir, 'relationships.csv'))

            user_id_col = 'user_id' if 'user_id' in self.users.columns else 'id'
            source_col = 'user1_id' if 'user1_id' in self.relationships.columns else 'source'
            target_col = 'user2_id' if 'user2_id' in self.relationships.columns else 'target'
            self.relationships = _drop_invalid_relationship_rows(
                self.relationships, source_col, target_col
            )

            self.graph = nx.Graph()

            self.graph.add_nodes_from(self.users[user_id_col].astype(np.int64, copy=False))
            self.graph.add_edges_from(
                zip(
                    self.relationships[source_col].astype(np.int64),
                    self.relationships[target_col].astype(np.int64),
                )
            )

            logger.info(f"✓ Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges\n")

            self.results_dir = None
        except FileNotFoundError as e:
            logger.error(f"Lỗi tải dữ liệu: {e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi không mong đợi khi tải dữ liệu: {e}")
            raise
    
    # ========================
    # SIR SIMULATION
    # ========================
    def simulate(
        self,
        transmission_rate: float = 0.3,
        recovery_rate: float = 0.1,
        max_days: int = 300,
        seed: int = 42,
        *,
        misinfo_source_mode: str = 'random',
        num_initial_sources: int = 1,
    ) -> None:
        """
        Mô phỏng mô hình SIR
        
        Args:
            transmission_rate (float): Tỷ lệ lây nhiễm (0-1)
            recovery_rate (float): Tỷ lệ hồi phục (0-1)
            max_days (int): Số ngày tối đa mô phỏng
            seed (int): Seed cho random
            
        Raises:
            ValueError: Nếu tham số không hợp lệ
        """
        if not (0 <= transmission_rate <= 1):
            raise ValueError("transmission_rate phải trong khoảng [0, 1]")
        if not (0 <= recovery_rate <= 1):
            raise ValueError("recovery_rate phải trong khoảng [0, 1]")
        if max_days <= 0:
            raise ValueError("max_days phải > 0")
        
        try:
            random.seed(seed)
            np.random.seed(seed)

            misinfo_mode = normalize_misinfo_mode(misinfo_source_mode)
            self.results_dir = pure_dataset_subdir_fs(self.output_dir, misinfo_mode)
            os.makedirs(self.results_dir, exist_ok=True)
            logger.info(f"✓ Results directory: {self.results_dir}\n")

            n = self.graph.number_of_nodes()
            node_list = list(self.graph.nodes())
            idx_of = {node_list[i]: i for i in range(n)}

            # 0=S, 1=I, 2=R
            state = np.zeros(n, dtype=int)
            init_nodes = pick_top_nodes_by_score(
                self.graph, misinfo_mode, num_initial_sources, seed=seed
            )
            init_indices = [idx_of[nid] for nid in init_nodes]
            for init_idx in init_indices:
                state[init_idx] = 1
            ever_infected = np.zeros(n, dtype=bool)
            for init_idx in init_indices:
                ever_infected[init_idx] = True

            self.misinfo_source_mode = misinfo_mode
            self.initial_infected_nodes = list(init_nodes)
            logger.info(
                "🦠 Nguồn thông tin xấu (%s): %s",
                misinfo_mode,
                ', '.join(str(node_list[i]) for i in init_indices),
            )

            history = {
                'day': [0],
                'S': [np.sum(state == 0)],
                'I': [np.sum(state == 1)],
                'R': [np.sum(state == 2)],
                'cum_infected': [int(np.sum(ever_infected))],
            }

            logger.info(f"Day 0: S={history['S'][0]}, I={history['I'][0]}, R={history['R'][0]}")

            # ========================
            # LOOP MỐ PHỎNG
            # ========================
            for day in range(1, max_days + 1):

                new_state = state.copy()

                for i in range(n):
                    if state[i] == 1:

                        # hồi phục
                        if random.random() < recovery_rate:
                            new_state[i] = 2

                        # lây nhiễm
                        node_id = node_list[i]
                        for nei in self.graph.neighbors(node_id):
                            nei_idx = idx_of[nei]
                            if state[nei_idx] == 0 and random.random() < transmission_rate:
                                new_state[nei_idx] = 1

                state = new_state
                ever_infected |= state == 1

                S = int(np.sum(state == 0))
                I = int(np.sum(state == 1))
                R = int(np.sum(state == 2))

                history['day'].append(day)
                history['S'].append(S)
                history['I'].append(I)
                history['R'].append(R)
                history['cum_infected'].append(int(np.sum(ever_infected)))

                if day % 10 == 0:
                    logger.info(f"Day {day}: S={S}, I={I}, R={R}")

                # Dừng khi không còn ca nhiễm (hết nguồn lây)
                if I == 0:
                    logger.info(f"\n🎯 Dịch kết thúc tại ngày {day} (không còn nút I)")
                    break

            self.history = pd.DataFrame(history)
            self.total_infected_nodes = int(np.sum(ever_infected))
            self.never_infected_nodes = n - self.total_infected_nodes

            logger.info("\n✓ Hoàn thành mô phỏng!\n")
        except Exception as e:
            logger.error(f"Lỗi khi mô phỏng: {e}")
            raise

    
    # ========================
    # THỐNG KÊ
    # ========================
    def get_statistics(self) -> tuple:
        """
        Tính toán thống kê mô phỏng
        
        Returns:
            tuple: (peak_day, peak_infected, final_day, total_infected, never_infected)
            
        Raises:
            ValueError: Nếu chưa có dữ liệu mô phỏng
        """
        if self.history is None:
            raise ValueError("Chưa có dữ liệu mô phỏng. Gọi simulate() trước")
        
        try:
            peak_idx = self.history['I'].idxmax()
            peak_day = int(self.history.loc[peak_idx, 'day'])
            peak_infected = int(self.history['I'].max())

            final_day = epidemic_final_day_from_history(self.history)
            total_inf, never_inf = sir_epidemic_totals_from_history(
                self.history,
                self.graph.number_of_nodes() if self.graph is not None else None,
            )

            logger.info("="*60)
            logger.info("THỐNG KÊ SIR")
            logger.info("="*60)
            logger.info(f"🔥 Ngày đỉnh dịch: {peak_day}")
            logger.info(f"👥 Đỉnh số ca nhiễm: {peak_infected}")
            logger.info(f"🛡️ Ngày kết thúc dịch: {final_day}")
            logger.info(f"📊 Tổng nút từng nhiễm: {total_inf}")
            logger.info(f"🟢 Không bao giờ nhiễm: {never_inf}")
            logger.info("="*60 + "\n")

            return peak_day, peak_infected, final_day, total_inf, never_inf
        except Exception as e:
            logger.error(f"Lỗi tính toán thống kê: {e}")
            raise

    # ========================
    # VẼ BIỂU ĐỒ
    # ========================
    def visualize(self) -> None:
        """
        Vẽ biểu đồ mô phỏng SIR
        
        Raises:
            ValueError: Nếu chưa có dữ liệu mô phỏng
        """
        if self.history is None:
            raise ValueError("Chưa có dữ liệu mô phỏng. Gọi simulate() trước")
        
        try:
            peak_day, peak_infected, final_day, total_inf, never_inf = self.get_statistics()

            df = self.history[self.history['day'] <= final_day]

            plt.figure(figsize=(12, 6))

            # vẽ đường
            plt.plot(df['day'], df['S'], label='Susceptible (S)', linewidth=2)
            plt.plot(df['day'], df['I'], label='Infected (I)', linewidth=2)
            plt.plot(df['day'], df['R'], label='Recovered (R)', linewidth=2)

            # đánh dấu peak
            plt.axvline(peak_day, linestyle='--', color='red', alpha=0.7)
            plt.scatter(peak_day, peak_infected, color='red', s=100, zorder=5)

            # đánh dấu ngày kết thúc
            plt.axvline(final_day, linestyle='--', color='green', alpha=0.7)

            # TEXT HIỂN THỊ
            text_str = (
                f"Ngày đỉnh dịch: {peak_day}\n"
                f"Đỉnh số ca nhiễm: {peak_infected}\n"
                f"Ngày kết thúc: {final_day}\n"
                f"Tổng từng nhiễm: {total_inf}\n"
                f"Không bao giờ nhiễm: {never_inf}"
            )

            plt.text(
                0.02, 0.95, text_str,
                transform=plt.gca().transAxes,
                fontsize=11,
                verticalalignment='top',
                bbox=dict(boxstyle='round', alpha=0.8, facecolor='lightyellow')
            )

            plt.title("Mô phỏng SIR - Mạng Xã Hội", fontsize=14, fontweight='bold')
            plt.xlabel("Ngày", fontsize=12)
            plt.ylabel("Số người", fontsize=12)
            plt.legend(fontsize=11, loc='upper right')
            plt.grid(True, alpha=0.3)

            path = os.path.join(self.results_dir, "sir_plot.png")
            plt.savefig(path, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"✓ Lưu biểu đồ: {path}")
        except Exception as e:
            logger.error(f"Lỗi khi vẽ biểu đồ: {e}")
            raise

    # ========================
    # LƯU DỮ LIỆU
    # ========================
    def save(self) -> None:
        """
        Lưu lịch sử mô phỏng
        
        Raises:
            OSError: Nếu lỗi ghi file
        """
        if self.history is None:
            raise ValueError("Chưa có dữ liệu mô phỏng. Gọi simulate() trước")
        
        try:
            path = os.path.join(self.results_dir, "sir_history.csv")
            self.history.to_csv(path, index=False)
            logger.info(f"✓ Lưu history: {path}")
            meta_path = os.path.join(self.results_dir, "misinfo_source.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "misinfo_source_mode": getattr(self, "misinfo_source_mode", "random"),
                        "node_ids": [int(x) for x in getattr(self, "initial_infected_nodes", [])],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f"✓ Lưu nguồn phát: {meta_path}")
        except OSError as e:
            logger.error(f"Lỗi lưu dữ liệu: {e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi không mong đợi: {e}")
            raise

class SIRDynamicImmunization:
    """
    Lớp mô phỏng mô hình SIR với chiến lược miễn nhiễm động
    
    Attributes:
        output_dir (str): Thư mục chứa dữ liệu input
        top_k (int): Số node hàng đầu để miễn nhiễm
        intervention_day (int): Ngày (1-based) thực hiện miễn nhiễm top-k
        graph (nx.Graph): Đồ thị mạng xã hội
        users (pd.DataFrame): Dữ liệu người dùng
        relationships (pd.DataFrame): Dữ liệu quan hệ
        history (pd.DataFrame): Lịch sử mô phỏng
        results_dir (str): Thư mục lưu kết quả
    """

    def __init__(
        self,
        output_dir: str = None,
        top_k: int = 10,
        strategy: str = "betweenness",
        intervention_day: int = 1,
        misinfo_source_mode: str = "random",
        *,
        graph: nx.Graph | None = None,
        users: pd.DataFrame | None = None,
        relationships: pd.DataFrame | None = None,
    ):
        """
        Khởi tạo mô phỏng SIR với miễn nhiễm động
        
        Args:
            output_dir (str): Thư mục chứa dữ liệu (nếu None tìm tự động)
            top_k (int): Số node hàng đầu để miễn nhiễm (mặc định 10)
            strategy (str): Chiến lược chọn node để miễn nhiễm: "random" | "betweenness" | "degree" | "eigenvector" | "pagerank"
            intervention_day (int): Ngày mô phỏng (1-based) thực hiện miễn nhiễm top-k (mặc định 1)
            
        Raises:
            ValueError: Nếu top_k <= 0 hoặc intervention_day < 1
            FileNotFoundError: Nếu không tìm thấy thư mục output
        """
        if top_k <= 0:
            raise ValueError("top_k phải > 0")

        strategy = normalize_dynamic_strategy(strategy or "betweenness")

        intervention_day = int(intervention_day)
        if intervention_day < 1:
            raise ValueError("intervention_day phải >= 1")
        
        self.output_dir = self._find_output_dir(output_dir)
        self.top_k = top_k
        self.strategy = strategy
        self.intervention_day = intervention_day
        self.misinfo_source_mode = normalize_misinfo_mode(misinfo_source_mode)

        self.graph = graph
        self.users = users
        self.relationships = relationships
        self.history = None
        self.results_dir = None
        self.immunized_nodes = []

        if self.graph is None:
            self._load_data()
        else:
            self.results_dir = dynamic_dataset_subdir_fs(
                self.output_dir,
                self.strategy,
                self.intervention_day,
                self.top_k,
                self.misinfo_source_mode,
            )
            os.makedirs(self.results_dir, exist_ok=True)
        logger.info(
            f"Khởi tạo SIRDynamicImmunization: top_k={top_k}, strategy={strategy}, "
            f"intervention_day={self.intervention_day}"
        )

    # =========================
    # LOAD DATA
    # =========================
    def _find_output_dir(self, path: str) -> str:
        """
        Tìm thư mục output
        
        Args:
            path (str): Đường dẫn thư mục (nếu cung cấp)
            
        Returns:
            str: Đường dẫn thư mục output tìm được
            
        Raises:
            FileNotFoundError: Nếu không tìm thấy thư mục
        """
        if path and os.path.exists(path):
            return path

        # Find the most recent output folder
        output_folders = _discover_dataset_dirs()
        if output_folders:
            # Sort by modification time, get the most recent
            most_recent = max(output_folders, key=lambda p: p.stat().st_mtime)
            return str(most_recent)

        raise FileNotFoundError("Không tìm thấy folder output!")

    def _load_data(self) -> None:
        """
        Tải dữ liệu từ CSV và xây dựng đồ thị
        
        Raises:
            FileNotFoundError: Nếu file dữ liệu không tồn tại
        """
        try:
            logger.info(f"📁 Load dữ liệu từ: {self.output_dir}\n")

            self.users = pd.read_csv(os.path.join(self.output_dir, 'users.csv'))
            self.relationships = pd.read_csv(os.path.join(self.output_dir, 'relationships.csv'))

            user_id_col = 'user_id' if 'user_id' in self.users.columns else 'id'
            source_col = 'user1_id' if 'user1_id' in self.relationships.columns else 'source'
            target_col = 'user2_id' if 'user2_id' in self.relationships.columns else 'target'
            self.relationships = _drop_invalid_relationship_rows(
                self.relationships, source_col, target_col
            )

            self.graph = nx.Graph()

            self.graph.add_nodes_from(self.users[user_id_col].astype(np.int64, copy=False))
            self.graph.add_edges_from(
                zip(
                    self.relationships[source_col].astype(np.int64),
                    self.relationships[target_col].astype(np.int64),
                )
            )

            logger.info(f"✓ Graph: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges\n")

            self.results_dir = dynamic_dataset_subdir_fs(
                self.output_dir,
                self.strategy,
                self.intervention_day,
                self.top_k,
                self.misinfo_source_mode,
            )
            os.makedirs(self.results_dir, exist_ok=True)
            logger.info(f"✓ Results directory: {self.results_dir}\n")
        except FileNotFoundError as e:
            logger.error(f"Lỗi tải dữ liệu: {e}")
            raise
        except Exception as e:
            logger.error(f"Lỗi không mong đợi khi tải dữ liệu: {e}")
            raise

    # =========================
    # CHỌN TOP NODE THEO CHIẾN LƯỢC
    # =========================
    def get_top_nodes(self) -> list:
        """
        Chọn top_k node theo chiến lược (random hoặc centrality)
        
        Returns:
            list: Danh sách top node
            
        Raises:
            ValueError: Nếu top_k lớn hơn số node
        """
        if self.top_k > self.graph.number_of_nodes():
            raise ValueError(f"top_k ({self.top_k}) lớn hơn số node ({self.graph.number_of_nodes()})")
        
        try:
            logger.info("Tính chỉ số can thiệp: %s ...", self.strategy)
            if self.strategy == "random":
                top_nodes = random.sample(list(self.graph.nodes()), self.top_k)
                score = {int(node): 0.0 for node in top_nodes}
            else:
                score = compute_centrality_scores(self.graph, self.strategy)
                ranked = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
                top_nodes = [node for node, _ in ranked[: self.top_k]]

            logger.info("\n💉 Top node được chuyển sang R:")
            for i, node in enumerate(top_nodes, 1):
                val = score.get(int(node), 0)
                logger.info(f"{i}. Node {node} ({self.strategy}={val:.6f})")

            return top_nodes
        except Exception as e:
            logger.error(f"Lỗi khi chọn top nodes: {e}")
            raise
    # =========================
    # SIR + IMMUNIZATION
    # =========================
    def simulate(
        self,
        transmission_rate: float = 0.3,
        recovery_rate: float = 0.1,
        days: int = 200,
        seed: int = 42,
        *,
        misinfo_source_mode: str = 'random',
        num_initial_sources: int = 1,
    ) -> int:
        """
        Mô phỏng mô hình SIR với chiến lược miễn nhiễm động
        
        Args:
            transmission_rate (float): Tỷ lệ lây nhiễm (0-1)
            recovery_rate (float): Tỷ lệ hồi phục (0-1)
            days (int): Số ngày mô phỏng
            seed (int): Seed cho random

        Note:
            Miễn nhiễm top-k diễn ra tại ngày ``self.intervention_day`` (phải ≤ ``days``).
            
        Returns:
            int: Ngày bắt đầu miễn nhiễm
            
        Raises:
            ValueError: Nếu tham số không hợp lệ
        """
        if not (0 <= transmission_rate <= 1):
            raise ValueError("transmission_rate phải trong khoảng [0, 1]")
        if not (0 <= recovery_rate <= 1):
            raise ValueError("recovery_rate phải trong khoảng [0, 1]")
        if days <= 0:
            raise ValueError("days phải > 0")
        if self.intervention_day > days:
            raise ValueError(
                f"intervention_day ({self.intervention_day}) không được lớn hơn days ({days})"
            )
        
        try:
            random.seed(seed)
            np.random.seed(seed)

            node_list = list(self.graph.nodes())
            n = len(node_list)
            idx_of = {node_list[i]: i for i in range(n)}

            state = np.zeros(n, dtype=int)  # 0=S,1=I,2=R

            misinfo_mode = normalize_misinfo_mode(
                misinfo_source_mode or self.misinfo_source_mode
            )
            self.misinfo_source_mode = misinfo_mode
            init_nodes = pick_top_nodes_by_score(
                self.graph, misinfo_mode, num_initial_sources, seed=seed
            )
            init_indices = [idx_of[nid] for nid in init_nodes]
            for init_idx in init_indices:
                state[init_idx] = 1
            ever_infected = np.zeros(n, dtype=bool)
            for init_idx in init_indices:
                ever_infected[init_idx] = True
            self.initial_infected_nodes = list(init_nodes)
            logger.info(
                "🦠 Nguồn thông tin xấu (%s): %s",
                misinfo_mode,
                ', '.join(str(node_list[i]) for i in init_indices),
            )

            history = {
                'day': [0],
                'S': [np.sum(state == 0)],
                'I': [np.sum(state == 1)],
                'R': [np.sum(state == 2)],
                'cum_infected': [int(np.sum(ever_infected))],
            }

            immunized = False
            immune_day = None

            for day in range(1, days + 1):
                new_state = state.copy()

                # =====================
                # LÂY + HỒI PHỤC
                # =====================
                for i in range(n):
                    if state[i] == 1:
                        # hồi phục
                        if random.random() < recovery_rate:
                            new_state[i] = 2

                        # lây
                        node_id = node_list[i]
                        for nei in self.graph.neighbors(node_id):
                            j = idx_of[nei]
                            if state[j] == 0 and random.random() < transmission_rate:
                                new_state[j] = 1

                state = new_state
                ever_infected |= state == 1

                # =====================
                # TẠI intervention_day → MIỄN NHIỄM
                # =====================
                if day == self.intervention_day and not immunized:
                    top_nodes = self.get_top_nodes()
                    self.immunized_nodes = list(top_nodes)

                    for node in top_nodes:
                        state[idx_of[node]] = 2

                    immunized = True
                    immune_day = day

                    logger.info(f"\nĐã miễn nhiễm {self.top_k} node tại ngày {day}\n")

                # =====================
                # GHI LỊCH SỬ
                # =====================
                S = int(np.sum(state == 0))
                I = int(np.sum(state == 1))
                R = int(np.sum(state == 2))

                history['day'].append(day)
                history['S'].append(S)
                history['I'].append(I)
                history['R'].append(R)
                history['cum_infected'].append(int(np.sum(ever_infected)))

                if day % 10 == 0:
                    logger.info(f"Day {day}: S={S}, I={I}, R={R}")

                # Dừng khi không còn ca nhiễm (hết nguồn lây)
                if I == 0:
                    logger.info(f"\n🎯 Dịch kết thúc tại ngày {day} (không còn nút I)")
                    break

            self.history = pd.DataFrame(history)
            self.total_infected_nodes = int(np.sum(ever_infected))
            self.never_infected_nodes = n - self.total_infected_nodes
            history_path = os.path.join(self.results_dir, 'sir_history.csv')
            self.history.to_csv(history_path, index=False)
            logger.info(f'✓ Lưu history: {history_path}')

            imm_path = os.path.join(self.results_dir, 'immunized_nodes.json')
            with open(imm_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        'strategy': self.strategy,
                        'top_k': self.top_k,
                        'seed': seed,
                        'intervention_day': self.intervention_day,
                        'immune_day': immune_day,
                        'misinfo_source_mode': getattr(self, 'misinfo_source_mode', 'random'),
                        'misinfo_source_node_ids': [
                            int(x) for x in getattr(self, 'initial_infected_nodes', [])
                        ],
                        'node_ids': [int(x) for x in self.immunized_nodes],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            mis_path = os.path.join(self.results_dir, 'misinfo_source.json')
            with open(mis_path, 'w', encoding='utf-8') as f:
                json.dump(
                    {
                        'misinfo_source_mode': getattr(self, 'misinfo_source_mode', 'random'),
                        'node_ids': [
                            int(x) for x in getattr(self, 'initial_infected_nodes', [])
                        ],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.info(f'✓ Lưu danh sách can thiệp: {imm_path}')

            logger.info("\n✓ Hoàn thành mô phỏng!\n")

            return immune_day
        except Exception as e:
            logger.error(f"Lỗi khi mô phỏng: {e}")
            raise

    
    # =========================
    # THỐNG KÊ
    # =========================
    def get_statistics(self) -> tuple:
        """
        Tính toán thống kê mô phỏng
        
        Returns:
            tuple: (peak_day, peak_I, final_day, total_infected, never_infected)
            
        Raises:
            ValueError: Nếu chưa có dữ liệu mô phỏng
        """
        if self.history is None:
            raise ValueError("Chưa có dữ liệu mô phỏng. Gọi simulate() trước")
        
        try:
            peak_idx = self.history['I'].idxmax()
            peak_day = int(self.history.loc[peak_idx, 'day'])
            peak_I = int(self.history['I'].max())
            final_day = epidemic_final_day_from_history(self.history)
            total_inf, never_inf = sir_epidemic_totals_from_history(
                self.history,
                self.graph.number_of_nodes() if self.graph is not None else None,
            )

            logger.info("\n" + "="*60)
            logger.info("📊 THỐNG KÊ")
            logger.info("="*60)
            logger.info(f"Số ca nhiễm: {peak_I} người tại ngày {peak_day}")
            logger.info(f"Ngày kết thúc dịch (I=0): {final_day}")
            logger.info(f"Tổng nút từng nhiễm: {total_inf}")
            logger.info(f"Không bao giờ nhiễm: {never_inf}")
            logger.info("="*60)

            return peak_day, peak_I, final_day, total_inf, never_inf
        except Exception as e:
            logger.error(f"Lỗi tính toán thống kê: {e}")
            raise

    # =========================
    # VẼ BIỂU ĐỒ
    # =========================
    def visualize(self, peak_day: int, peak_I: int, final_day: int) -> None:
        """
        Vẽ biểu đồ mô phỏng SIR
        
        Args:
            peak_day (int): Ngày đỉnh dịch
            peak_I (int): Số ca nhiễm tối đa
            final_day (int): Ngày kết thúc
            
        Raises:
            ValueError: Nếu chưa có dữ liệu mô phỏng
        """
        if self.history is None:
            raise ValueError("Chưa có dữ liệu mô phỏng. Gọi simulate() trước")
        
        try:
            plt.figure(figsize=(12, 6))

            plt.plot(self.history['day'], self.history['S'], label='S (Susceptible)', linewidth=2)
            plt.plot(self.history['day'], self.history['I'], label='I (Infected)', linewidth=2)
            plt.plot(self.history['day'], self.history['R'], label='R (Recovered)', linewidth=2)

            # đánh dấu peak
            plt.scatter(peak_day, peak_I, color='red', s=100, zorder=5)
            plt.text(peak_day, peak_I, f'Peak\nDay {peak_day}\nI={peak_I}', ha='center')

            # đánh dấu miễn nhiễm
            plt.axvline(final_day, linestyle='--', color='green', alpha=0.7)
            plt.text(final_day, 0, f'Immune\nDay {final_day}', ha='center')

            plt.xlabel("Ngày", fontsize=12, fontweight='bold')
            plt.ylabel("Số người", fontsize=12, fontweight='bold')
            plt.title("SIR + Dynamic Immunization (Day 1)", fontsize=14, fontweight='bold')
            plt.legend(fontsize=11, loc='best')
            plt.grid(True, alpha=0.3)

            path = os.path.join(self.results_dir, "sir_final.png")
            plt.savefig(path, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"✓ Đã lưu biểu đồ: {path}")
        except Exception as e:
            logger.error(f"Lỗi khi vẽ biểu đồ: {e}")
            raise


if __name__ == "__main__":
    sim = PureSIRSimulation()
    sim.simulate(transmission_rate=0.3, recovery_rate=0.02, max_days=300)
    sim.get_statistics()
    sim.visualize()
    sim.save()
