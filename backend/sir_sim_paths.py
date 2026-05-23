"""
Đường dẫn lưu và đọc mô phỏng SIR trong mỗi thư mục dataset (output_*).
Bố cục: simulation_sir/pure/ và simulation_sir/dynamic/<strategy>_day<N>_k<K>/
Vẫn hỗ trợ đọc thư mục *_day<N> (không _k) cũ.
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

SIR_SIM_ROOT = "simulation_sir"

DYNAMIC_STRATEGIES = ("betweenness", "degree", "eigenvector")

_DYNAMIC_DIR_RE = re.compile(
    r"^(?P<strat>betweenness|degree|eigenvector)_day(?P<day>\d+)(?:_k(?P<k>\d+))?$"
)


def pure_dataset_subdir_fs(output_root: str) -> str:
    """Thư mục con để ghi kết quả SIR thuần."""
    return os.path.join(output_root, SIR_SIM_ROOT, "pure")


def dynamic_folder_basename(strategy: str, intervention_day: int, top_k: int) -> str:
    s = (strategy or "betweenness").strip().lower()
    return f"{s}_day{int(intervention_day)}_k{int(top_k)}"


def dynamic_dataset_subdir_fs(
    output_root: str, strategy: str, intervention_day: int, top_k: int = 10
) -> str:
    """Thư mục con để ghi kết quả SIR + can thiệp (phân biệt theo top_k)."""
    return os.path.join(
        output_root,
        SIR_SIM_ROOT,
        "dynamic",
        dynamic_folder_basename(strategy, intervention_day, top_k),
    )


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


def dynamic_sir_history_csv_candidates(
    folder: Path,
    strategy: str,
    intervention_day: int,
    top_k: int | None = None,
) -> list[Path]:
    s = (strategy or "betweenness").strip().lower()
    d = int(intervention_day)
    c: list[Path] = []
    if top_k is not None:
        c.append(
            folder
            / SIR_SIM_ROOT
            / "dynamic"
            / dynamic_folder_basename(s, d, int(top_k))
            / "sir_history.csv"
        )
    c.extend(
        [
            folder / SIR_SIM_ROOT / "dynamic" / f"{s}_day{d}" / "sir_history.csv",
            folder / f"SIR_dynamic_{s}_day{d}" / "sir_history.csv",
            folder / f"SIR_dynamic_{s}" / "sir_history.csv",
        ]
    )
    if s == "betweenness" and d == 1:
        c.append(folder / "SIR_dynamic_immunization" / "sir_history.csv")
    return c


def find_dynamic_sir_history_csv(
    folder: Path,
    strategy: str,
    intervention_day: int,
    top_k: int | None = None,
) -> Optional[Path]:
    return _first_existing_file(
        dynamic_sir_history_csv_candidates(folder, strategy, intervention_day, top_k)
    )


def _parse_new_dynamic_dirname(dirname: str) -> Optional[tuple[str, int, Optional[int]]]:
    m = _DYNAMIC_DIR_RE.match(dirname)
    if not m:
        return None
    k = int(m.group("k")) if m.group("k") else None
    return m.group("strat"), int(m.group("day")), k


def _read_top_k_from_run_dir(run_dir: Path) -> Optional[int]:
    mj = run_dir / "immunized_nodes.json"
    if not mj.is_file():
        return None
    try:
        with open(mj, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("top_k") is not None:
            return int(data["top_k"])
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
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
    """Các lần chạy SIR + can thiệp (phân biệt strategy, ngày can thiệp, top_k)."""
    seen: set[tuple[str, int, int]] = set()
    rows: list[dict[str, Any]] = []

    def add(strategy: str, day: int, top_k: int) -> None:
        key = (strategy, day, top_k)
        if key in seen:
            return
        seen.add(key)
        rows.append({"strategy": strategy, "intervention_day": day, "top_k": top_k})

    droot = folder / SIR_SIM_ROOT / "dynamic"
    if droot.is_dir():
        for sub in sorted(droot.iterdir()):
            if not sub.is_dir() or not (sub / "sir_history.csv").is_file():
                continue
            p = _parse_new_dynamic_dirname(sub.name)
            if not p:
                continue
            strat, day, k = p
            if k is None:
                k = _read_top_k_from_run_dir(sub) or 10
            add(strat, day, int(k))

    if folder.is_dir():
        for sub in sorted(folder.iterdir()):
            if not sub.is_dir() or not sub.name.startswith("SIR_dynamic_"):
                continue
            if not (sub / "sir_history.csv").is_file():
                continue
            p = _parse_legacy_dynamic_folder_name(sub.name)
            if not p:
                continue
            strat, day = p
            k = _read_top_k_from_run_dir(sub) or 10
            add(strat, day, int(k))

    rows.sort(key=lambda r: (r["strategy"], r["intervention_day"], r["top_k"]))
    return rows


def immunized_json_candidates(
    folder: Path,
    strategy: str,
    intervention_day: int,
    top_k: int | None = None,
) -> list[Path]:
    s = (strategy or "betweenness").strip().lower()
    d = int(intervention_day)
    c: list[Path] = []
    if top_k is not None:
        c.append(
            folder
            / SIR_SIM_ROOT
            / "dynamic"
            / dynamic_folder_basename(s, d, int(top_k))
            / "immunized_nodes.json"
        )
    c.extend(
        [
            folder / SIR_SIM_ROOT / "dynamic" / f"{s}_day{d}" / "immunized_nodes.json",
            folder / f"SIR_dynamic_{s}_day{d}" / "immunized_nodes.json",
            folder / f"SIR_dynamic_{s}" / "immunized_nodes.json",
        ]
    )
    if s == "betweenness" and d == 1:
        c.append(folder / "SIR_dynamic_immunization" / "immunized_nodes.json")
    return c


def read_immunized_node_ids(
    folder: Path,
    strategy: str,
    intervention_day: int,
    top_k: int | None = None,
) -> list[int]:
    for p in immunized_json_candidates(folder, strategy, intervention_day, top_k):
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return [int(x) for x in data.get("node_ids", [])]
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
    return []


def _is_legacy_sir_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    name = path.name
    return name == "Pure_SIR" or name == "SIR_dynamic_immunization" or name.startswith("SIR_dynamic_")


def clear_dataset_sir_results(folder: Path) -> int:
    """
    Xóa toàn bộ kết quả mô phỏng SIR trong một bộ dataset (output_*).
    Giữ users.csv, relationships.csv, metrics.csv.
    """
    if not folder.is_dir():
        return 0
    removed = 0
    sim_root = folder / SIR_SIM_ROOT
    if sim_root.is_dir():
        shutil.rmtree(sim_root, ignore_errors=True)
        removed += 1
    for sub in list(folder.iterdir()):
        if _is_legacy_sir_dir(sub):
            shutil.rmtree(sub, ignore_errors=True)
            removed += 1
    return removed


def clear_orphan_legacy_sir_dirs(base: Path) -> int:
    """Xóa thư mục SIR legacy nằm trực tiếp dưới base (không xóa output_*)."""
    if not base.is_dir():
        return 0
    removed = 0
    for sub in list(base.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.startswith("output_") or sub.name.startswith("output_uploaded_"):
            continue
        if _is_legacy_sir_dir(sub):
            shutil.rmtree(sub, ignore_errors=True)
            removed += 1
    return removed
