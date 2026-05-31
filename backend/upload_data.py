"""
Đọc file upload (CSV / Excel): danh sách cạnh kết bạn hoặc bảng user đầy đủ (legacy).
"""
from __future__ import annotations

import datetime
import logging
from typing import BinaryIO, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EDGE_COLUMN_GROUPS = (
    ('source', 'target'),
    ('user1_id', 'user2_id'),
    ('from', 'to'),
    ('src', 'dst'),
    ('node1', 'node2'),
)

USER_PROFILE_MARKERS = frozenset(
    {
        'name',
        'followers',
        'followers_count',
        'posts',
        'posts_count',
        'shares',
        'comments',
        'risk',
        'verified',
        'join_date',
    }
)


def _strip_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lstrip('\ufeff') for c in out.columns]
    return out


def _resolve_column(df: pd.DataFrame, *candidates: str) -> str | None:
    cols = set(df.columns)
    lower = {c.lower(): c for c in df.columns}
    for name in candidates:
        if name in cols:
            return name
        hit = lower.get(name.lower())
        if hit:
            return hit
    return None


def normalize_edges_table(df: pd.DataFrame) -> pd.DataFrame:
    relationships = _strip_columns(df)
    source_col = _resolve_column(
        relationships, 'source', 'user1_id', 'from', 'src', 'node1', 'u'
    )
    target_col = _resolve_column(
        relationships, 'target', 'user2_id', 'to', 'dst', 'node2', 'v'
    )
    if source_col is None or target_col is None:
        raise ValueError(
            'Thiếu cột nguồn/đích (source/target hoặc user1_id/user2_id). '
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
    relationships = relationships.dropna(subset=['source', 'target'], how='any')
    if relationships.empty:
        raise ValueError('Không còn cạnh hợp lệ trong file.')
    relationships['source'] = relationships['source'].astype(np.int64)
    relationships['target'] = relationships['target'].astype(np.int64)
    return relationships


def read_upload_table(file_storage) -> pd.DataFrame:
    """Đọc CSV hoặc Excel (.xlsx / .xls) từ request.files['file']."""
    filename = (file_storage.filename or '').lower()
    stream: BinaryIO = file_storage.stream
    stream.seek(0)

    if filename.endswith('.csv'):
        return pd.read_csv(stream)
    if filename.endswith('.xlsx'):
        return pd.read_excel(stream, engine='openpyxl')
    if filename.endswith('.xls'):
        return pd.read_excel(stream, engine='xlrd')
    raise ValueError('Chỉ chấp nhận file .csv, .xlsx hoặc .xls')


def allowed_upload_filename(filename: str) -> bool:
    name = (filename or '').lower()
    return name.endswith(('.csv', '.xlsx', '.xls'))


def detect_upload_kind(df: pd.DataFrame) -> str:
    """
    'edges' — chỉ có cặp nút (kết bạn / quan hệ).
    'users_legacy' — bảng user đầy đủ (id, name, followers, …).
    """
    df = _strip_columns(df)
    cols = {str(c).lower() for c in df.columns}
    has_profile = bool(cols & USER_PROFILE_MARKERS) or 'name' in cols

    for a, b in EDGE_COLUMN_GROUPS:
        if a in cols and b in cols:
            return 'edges' if not has_profile else 'users_legacy'

    try:
        normalize_edges_table(df.copy())
        return 'edges'
    except ValueError:
        pass

    if 'id' in cols or 'user_id' in cols:
        return 'users_legacy'

    raise ValueError(
        'Không nhận dạng được file. Cần ít nhất hai cột quan hệ '
        '(source/target, user1_id/user2_id, from/to, …) hoặc bảng người dùng đầy đủ.'
    )


def relationships_from_edges_df(df: pd.DataFrame) -> pd.DataFrame:
    rels = normalize_edges_table(df)
    rels = rels.drop_duplicates(subset=['source', 'target'], keep='first')
    rels = rels[rels['source'] != rels['target']]
    if rels.empty:
        raise ValueError('Không có cạnh hợp lệ sau khi lọc.')
    return rels


def users_from_relationships(rels: pd.DataFrame) -> pd.DataFrame:
    """Sinh users.csv tối thiểu từ tập nút xuất hiện trên cạnh."""
    node_ids = pd.unique(
        pd.concat([rels['source'], rels['target']], ignore_index=True).astype('int64')
    )
    node_ids = sorted(int(n) for n in node_ids)
    today = datetime.date.today().isoformat()
    rows = [
        {
            'user_id': nid,
            'name': f'Người dùng {nid}',
            'followers_count': 0,
            'posts_count': 0,
            'join_date': today,
            'verified': 0,
        }
        for nid in node_ids
    ]
    return pd.DataFrame(rows)


def prepare_edges_upload(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rels = relationships_from_edges_df(df)
    users = users_from_relationships(rels)
    rels_out = pd.DataFrame(
        {'user1_id': rels['source'].astype('int64'), 'user2_id': rels['target'].astype('int64')}
    )
    return users, rels_out
