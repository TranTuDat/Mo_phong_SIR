"""
Đường dẫn lưu và đọc mô phỏng SIR trong mỗi thư mục dataset (output_*).
Bố cục mới: simulation_sir/pure/ và simulation_sir/dynamic/<strategy>_day<N>/
Vẫn hỗ trợ đọc Pure_SIR, SIR_dynamic_* cũ.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

SIR_SIM_ROOT = "simulation_sir"

DYNAMIC_STRATEGIES = ("betweenness", "degree", "eigenvector")


def pure_dataset_subdir_fs(output_root: str) -> str:
    """Thư mục con để ghi kết quả SIR thuần."""
    return os.path.join(output_root, SIR_SIM_ROOT, "pure")


def dynamic_dataset_subdir_fs(output_root: str, strategy: str, intervention_day: int) -> str:
    """Thư mục con để ghi kết quả SIR + can thiệp."""
    s = (strategy or "betweenness").strip().lower()
    return os.path.join(output_root, SIR_SIM_ROOT, "dynamic", f"{s}_day{int(intervention_day)}")


def _first_existing_file(candidates: list[Path]) -> Optional[Path]:
    for p in candidates:
        if p.is_file():
            return p
    return None


def find_pure_sir_history_csv(folder: Path) -> Optional[Path]:
    return _first_existing_file(
        [
            folder / SIR_SIM_ROOT / "pure" / "sir_history.csv",
            folder / "Pure_SIR" / "sir_history.csv",
        ]
    )


def dynamic_sir_history_csv_candidates(folder: Path, strategy: str, intervention_day: int) -> list[Path]:
    s = (strategy or "betweenness").strip().lower()
    d = int(intervention_day)
    c = [
        folder / SIR_SIM_ROOT / "dynamic" / f"{s}_day{d}" / "sir_history.csv",
        folder / f"SIR_dynamic_{s}_day{d}" / "sir_history.csv",
        folder / f"SIR_dynamic_{s}" / "sir_history.csv",
    ]
    if s == "betweenness" and d == 1:
        c.append(folder / "SIR_dynamic_immunization" / "sir_history.csv")
    return c


def find_dynamic_sir_history_csv(folder: Path, strategy: str, intervention_day: int) -> Optional[Path]:
    return _first_existing_file(dynamic_sir_history_csv_candidates(folder, strategy, intervention_day))


def _parse_new_dynamic_dirname(dirname: str) -> Optional[tuple[str, int]]:
    if "_day" not in dirname:
        return None
    strat, sep, day_part = dirname.rpartition("_day")
    if sep != "_day" or strat not in DYNAMIC_STRATEGIES:
        return None
    try:
        return strat, int(day_part)
    except ValueError:
        return None


def _parse_legacy_dynamic_folder_name(name: str) -> Optional[tuple[str, int]]:
    if name == "SIR_dynamic_immunization":
        return ("betweenness", 1)
    prefix = "SIR_dynamic_"
    if not name.startswith(prefix):
        return None
    rest = name[len(prefix) :]
    if rest in DYNAMIC_STRATEGIES:
        return (rest, 1)
    if "_day" in rest:
        strat, sep, day_part = rest.rpartition("_day")
        if sep == "_day" and strat in DYNAMIC_STRATEGIES:
            try:
                return strat, int(day_part)
            except ValueError:
                return None
    return None


def list_saved_dynamic_sir_runs(folder: Path) -> list[dict[str, Any]]:
    """Các lần chạy SIR + can thiệp đã có sir_history.csv (không trùng strategy + ngày)."""
    seen: set[tuple[str, int]] = set()
    rows: list[dict[str, int]] = []

    def add(strategy: str, day: int) -> None:
        key = (strategy, day)
        if key in seen:
            return
        seen.add(key)
        rows.append({"strategy": strategy, "intervention_day": day})

    droot = folder / SIR_SIM_ROOT / "dynamic"
    if droot.is_dir():
        for sub in sorted(droot.iterdir()):
            if not sub.is_dir():
                continue
            if not (sub / "sir_history.csv").is_file():
                continue
            p = _parse_new_dynamic_dirname(sub.name)
            if p:
                add(p[0], p[1])

    if folder.is_dir():
        for sub in sorted(folder.iterdir()):
            if not sub.is_dir():
                continue
            if not sub.name.startswith("SIR_dynamic_"):
                continue
            if not (sub / "sir_history.csv").is_file():
                continue
            p = _parse_legacy_dynamic_folder_name(sub.name)
            if p:
                add(p[0], p[1])

    rows.sort(key=lambda r: (r["strategy"], r["intervention_day"]))
    return rows


def immunized_json_candidates(folder: Path, strategy: str, intervention_day: int) -> list[Path]:
    s = (strategy or "betweenness").strip().lower()
    d = int(intervention_day)
    c = [
        folder / SIR_SIM_ROOT / "dynamic" / f"{s}_day{d}" / "immunized_nodes.json",
        folder / f"SIR_dynamic_{s}_day{d}" / "immunized_nodes.json",
        folder / f"SIR_dynamic_{s}" / "immunized_nodes.json",
    ]
    if s == "betweenness" and d == 1:
        c.append(folder / "SIR_dynamic_immunization" / "immunized_nodes.json")
    return c


def read_immunized_node_ids(folder: Path, strategy: str, intervention_day: int) -> list[int]:
    for p in immunized_json_candidates(folder, strategy, intervention_day):
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return [int(x) for x in data.get("node_ids", [])]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return []
