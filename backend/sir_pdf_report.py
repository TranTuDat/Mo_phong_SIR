"""Tạo báo cáo PDF: đồ thị, kết quả từng mô phỏng, so sánh, đề xuất can thiệp."""
from __future__ import annotations

import datetime
import logging
from io import BytesIO
from typing import Optional

import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties, findfont

logger = logging.getLogger(__name__)

_FONT_NAME: Optional[str] = None

STRATEGY_LABELS_VI = {
    'betweenness': ('Betweenness', 'Trung gian (cầu nối)'),
    'degree': ('Degree', 'Bậc cao'),
    'eigenvector': ('Eigenvector', 'Ảnh hưởng lan truyền'),
    'pagerank': ('PageRank', 'Ảnh hưởng lan truyền (PR)'),
}
STRATEGY_LABELS_EN = {
    'betweenness': ('Betweenness', 'Bridge / broker nodes'),
    'degree': ('Degree', 'High degree'),
    'eigenvector': ('Eigenvector', 'Propagation influence'),
    'pagerank': ('PageRank', 'Propagation rank'),
}


def _setup_pdf_font() -> str:
    """Arial hoặc Times New Roman — hỗ trợ tiếng Việt trên Windows."""
    global _FONT_NAME
    if _FONT_NAME:
        return _FONT_NAME

    for family in ('Arial', 'Times New Roman', 'Times'):
        try:
            path = findfont(FontProperties(family=family), fallback_to_default=False)
            if path and 'dejavu' not in path.lower():
                mpl.rcParams['font.family'] = family
                mpl.rcParams['font.sans-serif'] = [family]
                _FONT_NAME = family
                break
        except (OSError, ValueError):
            continue
    if not _FONT_NAME:
        mpl.rcParams['font.sans-serif'] = ['Arial', 'Times New Roman', 'DejaVu Sans']
        _FONT_NAME = 'Arial'

    mpl.rcParams['axes.unicode_minus'] = False
    mpl.rcParams['pdf.fonttype'] = 42
    mpl.rcParams['ps.fonttype'] = 42
    return _FONT_NAME


def _save_fig_pdf(pdf: PdfPages, fig: plt.Figure) -> None:
    fig.patch.set_facecolor('white')
    pdf.savefig(
        fig,
        facecolor='white',
        edgecolor='none',
        bbox_inches='tight',
        pad_inches=0.25,
    )
    plt.close(fig)


def _strategy_title(strategy: str, lang: str) -> str:
    key = (strategy or '').lower()
    labels = STRATEGY_LABELS_VI if lang == 'vi' else STRATEGY_LABELS_EN
    if key in labels:
        return labels[key][0]
    return strategy or '—'


def _history_df(history: list[dict]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    if 'day' not in df.columns:
        return pd.DataFrame()
    return df.sort_values('day')


def _history_to_series(history: list[dict], col: str = 'I') -> tuple[list[int], list[int]]:
    df = _history_df(history)
    if df.empty or col not in df.columns:
        return [], []
    return [int(x) for x in df['day']], [int(x) for x in df[col]]


def _run_label_short(run: dict, lang: str = 'vi') -> str:
    if run.get('model') == 'pure' or run.get('is_pure'):
        return 'SIR thuần' if lang == 'vi' else 'Pure SIR'
    strat = (run.get('strategy') or 'bet')[:4]
    day = run.get('intervention_day', '—')
    k = run.get('top_k', '—')
    return f'{strat}·d{day}·k{k}'


def _run_label_long(run: dict, lang: str = 'vi') -> str:
    if run.get('model') == 'pure' or run.get('is_pure'):
        return 'SIR thuần' if lang == 'vi' else 'Pure SIR'
    strat = _strategy_title(run.get('strategy') or 'betweenness', lang)
    day = run.get('intervention_day', '—')
    k = run.get('top_k', '—')
    if lang == 'vi':
        return f'Can thiệp {strat}, ngày {day}, k={k}'
    return f'Intervention {strat}, day {day}, k={k}'


def _format_delta(pure_peak: Optional[int], row_peak: Optional[int], lang: str) -> str:
    if pure_peak is None or row_peak is None:
        return '—'
    d = int(row_peak) - int(pure_peak)
    if d < 0:
        return f'−{abs(d)}' + (' (tốt hơn SIR thuần)' if lang == 'vi' else ' (better than pure)')
    if d > 0:
        return f'+{d}' + (' (cao hơn SIR thuần)' if lang == 'vi' else ' (worse than pure)')
    return '0'


def _val(run: dict, key: str) -> str:
    v = run.get(key)
    return '—' if v is None else str(v)


def _run_metrics_rows(run: dict, lang: str, pure_metrics: Optional[dict]) -> list[list[str]]:
    """Hàng [nhãn, giá trị] cho bảng kết quả một mô phỏng."""
    vi = lang == 'vi'
    rows: list[list[str]] = []
    is_pure = run.get('model') == 'pure' or run.get('is_pure')

    if is_pure:
        rows.append([
            'Loại mô phỏng' if vi else 'Simulation',
            'SIR thuần (không can thiệp)' if vi else 'Pure SIR (no intervention)',
        ])
    else:
        strat = run.get('strategy') or 'betweenness'
        meta = (STRATEGY_LABELS_VI if vi else STRATEGY_LABELS_EN).get(strat.lower())
        sub = meta[1] if meta else ''
        rows.append(['Chiến lược' if vi else 'Strategy', _strategy_title(strat, lang)])
        if sub:
            rows.append(['Mô tả' if vi else 'Description', sub])
        rows.append(['Ngày can thiệp' if vi else 'Intervention day', _val(run, 'intervention_day')])
        rows.append(['Top-k miễn nhiễm' if vi else 'Top-k immunized', _val(run, 'top_k')])
        nodes = run.get('intervened_nodes') or []
        n_ids = len(run.get('node_ids') or [])
        rows.append(['Số nút can thiệp' if vi else 'Nodes intervened', str(n_ids or len(nodes))])
        if nodes:
            names = [str(n.get('name', n.get('id', ''))) for n in nodes[:12]]
            extra = (n_ids or len(nodes)) - len(names)
            line = ', '.join(names)
            if extra > 0:
                line += f' … (+{extra} ' + ('nút khác)' if vi else 'more)')
            rows.append(['Nút được chọn' if vi else 'Selected nodes', line])

    rows.append(['Ngày đỉnh (peak day)' if vi else 'Peak day', _val(run, 'peak_day')])
    rows.append(['Max I (đỉnh đồng thời)' if vi else 'Peak infected (I)', _val(run, 'peak_infected')])
    rows.append(['Ngày kết thúc dịch' if vi else 'Epidemic end day', _val(run, 'final_day')])
    rows.append(['Tổng nút từng nhiễm' if vi else 'Total ever infected', _val(run, 'total_infected')])
    if run.get('never_infected') is not None:
        rows.append(['Không bao giờ nhiễm' if vi else 'Never infected', _val(run, 'never_infected')])

    if not is_pure and pure_metrics:
        pp = pure_metrics.get('peak_infected')
        rows.append([
            'Δ Max I so với SIR thuần' if vi else 'Δ peak I vs pure',
            _format_delta(pp, run.get('peak_infected'), lang),
        ])
        pt = pure_metrics.get('total_infected')
        if pt is not None and run.get('total_infected') is not None:
            dt = int(run['total_infected']) - int(pt)
            sign = f'−{abs(dt)}' if dt < 0 else (f'+{dt}' if dt > 0 else '0')
            rows.append(['Δ tổng nhiễm vs thuần' if vi else 'Δ total infected vs pure', sign])

    return rows


def _plot_sir_history(ax, history: list[dict], title: str, lang: str) -> bool:
    df = _history_df(history)
    if df.empty:
        return False
    if 'S' in df.columns:
        ax.plot(df['day'], df['S'], label='S', color='#3b82f6', linewidth=1.8)
    if 'I' in df.columns:
        ax.plot(df['day'], df['I'], label='I', color='#ef4444', linewidth=2)
    if 'R' in df.columns:
        ax.plot(df['day'], df['R'], label='R', color='#22c55e', linewidth=1.8)
    ax.set_xlabel('Ngày' if lang == 'vi' else 'Day', fontsize=9)
    ax.set_ylabel('Số người' if lang == 'vi' else 'Count', fontsize=9)
    ax.set_title(title, fontsize=10, pad=8)
    ax.legend(loc='best', fontsize=8, framealpha=0.95)
    ax.grid(True, alpha=0.25, linestyle='--')
    return True


def _style_comparison_table(table, font_size: float) -> None:
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#94a3b8')
        cell.set_linewidth(0.5)
        cell.set_height(0.072)
        if row == 0:
            cell.set_facecolor('#1e40af')
            cell.set_text_props(color='white', weight='bold', fontsize=font_size)
        elif col == 0:
            cell.set_facecolor('#e2e8f0')
            cell.set_text_props(weight='bold', fontsize=font_size, ha='left')
        else:
            cell.set_facecolor('#f8fafc' if row % 2 == 0 else '#ffffff')
            cell.set_text_props(fontsize=font_size, ha='center')
        cell.PAD = 0.04


def _render_metrics_table(ax, rows: list[list[str]], title: str, lang: str) -> None:
    ax.axis('off')
    ax.set_title(title, fontsize=11, fontweight='bold', pad=10, loc='left')
    if not rows:
        ax.text(0.05, 0.5, 'Không có dữ liệu.' if lang == 'vi' else 'No data.', fontsize=10)
        return
    cell_text = [[r[1]] for r in rows]
    row_labels = [r[0] for r in rows]
    table = ax.table(
        cellText=cell_text,
        rowLabels=row_labels,
        loc='center',
        cellLoc='left',
        colWidths=[0.92],
    )
    table.auto_set_font_size(False)
    fs = 9
    table.set_fontsize(fs)
    table.scale(1.0, 1.55)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor('#cbd5e1')
        cell.set_linewidth(0.4)
        if col == -1:
            cell.set_facecolor('#e2e8f0')
            cell.set_text_props(weight='bold', fontsize=fs)
        else:
            cell.set_facecolor('#ffffff' if row % 2 else '#f8fafc')
            cell.set_text_props(fontsize=fs)
        cell.set_height(0.055)
        cell.PAD = 0.03


def _render_run_detail_page(
    pdf: PdfPages,
    run: dict,
    lang: str,
    pure_metrics: Optional[dict],
) -> None:
    """Một trang: đồ thị S-I-R + bảng kết quả mô phỏng."""
    fig = plt.figure(figsize=(8.27, 11.69))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.05, 1.0], hspace=0.32)
    ax_chart = fig.add_subplot(gs[0])
    ax_metrics = fig.add_subplot(gs[1])

    title = _run_label_long(run, lang)
    fig.suptitle(title, fontsize=12, fontweight='bold', y=0.98)

    hist = run.get('history')
    chart_title = 'Đồ thị S — I — R' if lang == 'vi' else 'S — I — R chart'
    if hist and _plot_sir_history(ax_chart, hist, chart_title, lang):
        pass
    else:
        ax_chart.axis('off')
        ax_chart.text(0.5, 0.5, 'Không có lịch sử mô phỏng.', ha='center', fontsize=11)

    metrics_title = 'Kết quả mô phỏng' if lang == 'vi' else 'Simulation results'
    _render_metrics_table(ax_metrics, _run_metrics_rows(run, lang, pure_metrics), metrics_title, lang)
    _save_fig_pdf(pdf, fig)


def _render_table_page(
    pdf: PdfPages,
    title: str,
    col_labels: list[str],
    cell_text: list[list[str]],
    *,
    highlight_row: Optional[int] = None,
    col_widths: Optional[list[float]] = None,
) -> None:
    n_cols = len(col_labels)
    fig_w = max(11.0, 1.5 + n_cols * 1.2)
    fig, ax = plt.subplots(figsize=(fig_w, max(5.5, 0.45 * (len(cell_text) + 2))))
    ax.axis('off')
    ax.set_title(title, fontsize=13, fontweight='bold', pad=14)
    if col_widths is None:
        col_widths = [1.0 / n_cols] * n_cols
    table = ax.table(
        cellText=cell_text,
        colLabels=col_labels,
        loc='center',
        cellLoc='center',
        colWidths=col_widths,
    )
    fs = max(7, min(9, int(80 / n_cols)))
    table.auto_set_font_size(False)
    table.set_fontsize(fs)
    table.scale(1.0, 1.75)
    _style_comparison_table(table, fs)
    if highlight_row is not None:
        hr = highlight_row + 1
        for col in range(n_cols):
            cell = table[(hr, col)]
            cell.set_facecolor('#dbeafe')
    _save_fig_pdf(pdf, fig)


def _render_table_chunk(
    pdf: PdfPages,
    runs_chunk: list[dict],
    rows_def: list[tuple[str, str]],
    metric_col: str,
    lang: str,
    part: int,
    total_parts: int,
) -> None:
    col_labels = [metric_col] + [_run_label_short(r, lang) for r in runs_chunk]
    cell_text = []
    for field, label in rows_def:
        row = [label]
        for r in runs_chunk:
            v = r.get(field)
            row.append('—' if v is None else str(v))
        cell_text.append(row)
    title = 'Bảng so sánh chỉ số' if lang == 'vi' else 'Metrics comparison'
    if total_parts > 1:
        title += f' ({part}/{total_parts})' if lang == 'vi' else f' (part {part}/{total_parts})'
    n_cols = len(col_labels)
    col_widths = [0.22] + [0.78 / max(1, n_cols - 1)] * (n_cols - 1)
    _render_table_page(pdf, title, col_labels, cell_text, col_widths=col_widths)


def _render_recommendations_section(
    pdf: PdfPages,
    recommendations: Optional[dict],
    lang: str,
) -> None:
    if not recommendations:
        return

    vi = lang == 'vi'
    pure_metrics = recommendations.get('pure_sir')
    winner = recommendations.get('winner')
    strategies = recommendations.get('strategies') or []
    runs = [r for r in (recommendations.get('runs') or []) if r.get('available')]

    def rank_key(r: dict) -> tuple:
        big = 10**9
        return (
            int(r['total_infected']) if r.get('total_infected') is not None else big,
            int(r['peak_infected']) if r.get('peak_infected') is not None else big,
            int(r['final_day']) if r.get('final_day') is not None else big,
        )

    runs_sorted = sorted(runs, key=rank_key)

    # --- Trang đề xuất chính ---
    try:
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        ax.axis('off')
        ax.text(0.5, 0.96, 'Đề xuất can thiệp' if vi else 'Intervention recommendation',
                ha='center', fontsize=16, fontweight='bold', transform=ax.transAxes)

        y = 0.88
        if winner:
            strat = _strategy_title(winner.get('strategy', ''), lang)
            lines = [
                'Kịch bản được đề xuất' if vi else 'Recommended scenario',
                '',
                f"  • {strat}",
                f"  • {'Ngày can thiệp' if vi else 'Intervention day'}: {winner.get('intervention_day', '—')}",
                f"  • Top-k: {winner.get('top_k', '—')}",
                '',
                'Chỉ số' if vi else 'Metrics',
                f"  • {'Tổng nút từng nhiễm' if vi else 'Total infected'}: {winner.get('total_infected', '—')}",
                f"  • {'Max I' if vi else 'Peak I'}: {winner.get('peak_infected', '—')}",
                f"  • {'Ngày kết thúc' if vi else 'End day'}: {winner.get('final_day', '—')}",
                f"  • {'Ngày đỉnh' if vi else 'Peak day'}: {winner.get('peak_day', '—')}",
            ]
            if pure_metrics:
                lines.append(
                    f"  • {'Δ Max I so với SIR thuần' if vi else 'Δ peak I vs pure'}: "
                    f"{_format_delta(pure_metrics.get('peak_infected'), winner.get('peak_infected'), lang)}"
                )
            nodes = winner.get('intervened_nodes') or []
            if nodes:
                lines.append('')
                lines.append('Nút miễn nhiễm (mẫu)' if vi else 'Immunized nodes (sample)')
                for n in nodes[:15]:
                    lines.append(f"  • {n.get('name', n.get('id', ''))}")
                if len(nodes) > 15:
                    lines.append(f"  … +{len(nodes) - 15} " + ('nút khác' if vi else 'more'))
        else:
            lines = [
                'Chưa có đề xuất.' if vi else 'No recommendation yet.',
                'Chạy mô phỏng SIR + can thiệp trước.' if vi else 'Run SIR + interventions first.',
            ]

        lines.extend([
            '',
            'Tiêu chí xếp hạng (ưu tiên thấp hơn = tốt hơn):' if vi else 'Ranking criteria (lower is better):',
            '  1. Tổng nút từng nhiễm' if vi else '  1. Total ever infected',
            '  2. Max I (đỉnh đồng thời)' if vi else '  2. Peak infected (I)',
            '  3. Ngày kết thúc dịch' if vi else '  3. Epidemic end day',
        ])

        ax.text(0.08, y, '\n'.join(lines), transform=ax.transAxes, fontsize=10.5, va='top', linespacing=1.35)
        _save_fig_pdf(pdf, fig)
    except Exception as e:
        logger.warning('PDF recommendation hero skipped: %s', e)
        plt.close('all')

    # --- Bảng tốt nhất theo từng chiến lược ---
    strat_rows = [s for s in strategies if s.get('available')]
    if strat_rows:
        try:
            if vi:
                headers = ['Chiến lược', 'Ngày', 'k', 'Tổng nhiễm', 'Max I', 'Kết thúc', 'Δ Max I']
            else:
                headers = ['Strategy', 'Day', 'k', 'Total inf.', 'Peak I', 'End', 'Δ peak I']
            cells = []
            for s in strat_rows:
                cells.append([
                    _strategy_title(s.get('strategy', ''), lang),
                    _val(s, 'intervention_day'),
                    _val(s, 'top_k'),
                    _val(s, 'total_infected'),
                    _val(s, 'peak_infected'),
                    _val(s, 'final_day'),
                    _format_delta(
                        pure_metrics.get('peak_infected') if pure_metrics else None,
                        s.get('peak_infected'),
                        lang,
                    ),
                ])
            _render_table_page(
                pdf,
                'Tốt nhất theo từng chiến lược' if vi else 'Best per strategy',
                headers,
                cells,
                col_widths=[0.22, 0.1, 0.08, 0.14, 0.12, 0.12, 0.22],
            )
        except Exception as e:
            logger.warning('PDF strategy summary skipped: %s', e)
            plt.close('all')

    # --- Bảng xếp hạng đầy đủ (phân trang) ---
    if runs_sorted:
        chunk = 18
        total = (len(runs_sorted) + chunk - 1) // chunk
        for pi in range(total):
            part_runs = runs_sorted[pi * chunk : (pi + 1) * chunk]
            try:
                if vi:
                    headers = ['#', 'Chiến lược', 'Ngày', 'k', 'Tổng nhiễm', 'Max I', 'Kết thúc', 'Δ Max I']
                else:
                    headers = ['#', 'Strategy', 'Day', 'k', 'Total', 'Peak I', 'End', 'Δ peak I']
                cells = []
                win_sig = None
                if winner:
                    win_sig = (
                        winner.get('strategy'),
                        winner.get('intervention_day'),
                        winner.get('top_k'),
                    )
                for rank, r in enumerate(part_runs, start=pi * chunk + 1):
                    cells.append([
                        str(rank),
                        _strategy_title(r.get('strategy', ''), lang),
                        _val(r, 'intervention_day'),
                        _val(r, 'top_k'),
                        _val(r, 'total_infected'),
                        _val(r, 'peak_infected'),
                        _val(r, 'final_day'),
                        _format_delta(
                            pure_metrics.get('peak_infected') if pure_metrics else None,
                            r.get('peak_infected'),
                            lang,
                        ),
                    ])
                title = 'Xếp hạng tất cả kịch bản' if vi else 'Full scenario ranking'
                if total > 1:
                    title += f' ({pi + 1}/{total})'
                highlight = 0
                if win_sig and part_runs:
                    for i, r in enumerate(part_runs):
                        if (
                            r.get('strategy') == win_sig[0]
                            and r.get('intervention_day') == win_sig[1]
                            and r.get('top_k') == win_sig[2]
                        ):
                            highlight = i
                            break
                    else:
                        highlight = None
                _render_table_page(
                    pdf, title, headers, cells,
                    highlight_row=highlight,
                    col_widths=[0.05, 0.2, 0.08, 0.07, 0.14, 0.12, 0.12, 0.22],
                )
            except Exception as e:
                logger.warning('PDF ranking chunk %s skipped: %s', pi + 1, e)
                plt.close('all')


def build_sir_comparison_pdf_bytes(
    *,
    output_folder: str,
    pure: Optional[dict],
    dynamic_runs: list[dict],
    lang: str = 'vi',
    recommendations: Optional[dict] = None,
) -> bytes:
    _setup_pdf_font()
    buf = BytesIO()
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    title = 'Báo cáo mô phỏng SIR' if lang == 'vi' else 'SIR simulation report'
    metric_col = 'Chỉ số' if lang == 'vi' else 'Metric'
    rows_def = [
        ('peak_day', 'Ngày đỉnh' if lang == 'vi' else 'Peak day'),
        ('peak_infected', 'Max I' if lang == 'vi' else 'Peak I'),
        ('final_day', 'Ngày kết thúc' if lang == 'vi' else 'End day'),
        ('total_infected', 'Tổng từng nhiễm' if lang == 'vi' else 'Total infected'),
    ]

    pure_metrics = (recommendations or {}).get('pure_sir')
    if not pure_metrics and pure:
        pure_metrics = {
            'peak_day': pure.get('peak_day'),
            'peak_infected': pure.get('peak_infected'),
            'final_day': pure.get('final_day'),
            'total_infected': pure.get('total_infected'),
            'never_infected': pure.get('never_infected'),
        }

    runs_for_table: list[dict] = []
    if pure:
        runs_for_table.append({**pure, 'is_pure': True, 'model': 'pure'})
    runs_for_table.extend(dynamic_runs)

    with PdfPages(buf) as pdf:
        # Mục lục
        try:
            fig, ax = plt.subplots(figsize=(8.27, 11.69))
            ax.axis('off')
            lines = [
                title,
                '',
                f"{'Thư mục' if lang == 'vi' else 'Folder'}: {output_folder or '—'}",
                f"{'Xuất lúc' if lang == 'vi' else 'Exported'}: {ts}",
                f"{'Font' if lang == 'vi' else 'Font'}: {_FONT_NAME}",
                '',
                'Nội dung:' if lang == 'vi' else 'Contents:',
                '  1. Từng mô phỏng: đồ thị S-I-R + kết quả' if lang == 'vi' else '  1. Each run: S-I-R chart + metrics',
                '  2. So sánh I — tất cả kịch bản' if lang == 'vi' else '  2. Compare I — all runs',
                '  3. Bảng so sánh chỉ số' if lang == 'vi' else '  3. Metrics comparison table',
                '  4. Đề xuất can thiệp' if lang == 'vi' else '  4. Intervention recommendations',
                '',
                f"{'Danh sách mô phỏng' if lang == 'vi' else 'Runs'}:",
            ]
            if pure:
                lines.append(f"  • {_run_label_long(pure, lang)}")
            for run in dynamic_runs:
                lines.append(f"  • {_run_label_long(run, lang)}")
            lines.append(f"\n{'Tổng' if lang == 'vi' else 'Total'}: {len(runs_for_table)}")
            ax.text(0.08, 0.92, '\n'.join(lines), transform=ax.transAxes, fontsize=11, va='top')
            _save_fig_pdf(pdf, fig)
        except Exception as e:
            logger.warning('PDF cover page skipped: %s', e)
            plt.close('all')

        # Từng mô phỏng: đồ thị + kết quả
        if pure:
            try:
                _render_run_detail_page(pdf, {**pure, 'is_pure': True, 'model': 'pure'}, lang, pure_metrics)
            except Exception as e:
                logger.warning('PDF pure detail skipped: %s', e)
                plt.close('all')

        for run in dynamic_runs:
            if not run.get('history'):
                continue
            try:
                _render_run_detail_page(pdf, run, lang, pure_metrics)
            except Exception as e:
                logger.warning('PDF run detail skipped (%s): %s', _run_label_short(run, lang), e)
                plt.close('all')

        # So sánh I
        try:
            fig, ax = plt.subplots(figsize=(8.27, 6.0))
            has_curve = False
            palette = [
                '#dc2626', '#2563eb', '#16a34a', '#9333ea', '#ea580c',
                '#db2777', '#0891b2', '#65a30d', '#4f46e5', '#0d9488',
            ]
            idx = 0
            if pure and pure.get('history'):
                days, vals = _history_to_series(pure['history'], 'I')
                if days:
                    ax.plot(days, vals, label=_run_label_short(pure, lang), color=palette[0], linewidth=2.2)
                    has_curve = True
                    idx = 1
            for run in dynamic_runs:
                hist = run.get('history')
                if not hist:
                    continue
                days, vals = _history_to_series(hist, 'I')
                if not days:
                    continue
                ax.plot(
                    days, vals,
                    label=_run_label_short(run, lang),
                    color=palette[idx % len(palette)],
                    linewidth=1.6,
                )
                has_curve = True
                idx += 1
            if has_curve:
                ax.set_xlabel('Ngày' if lang == 'vi' else 'Day', fontsize=10)
                ax.set_ylabel('Số ca nhiễm (I)' if lang == 'vi' else 'Infected (I)', fontsize=10)
                ax.set_title(
                    'So sánh I — tất cả mô phỏng' if lang == 'vi' else 'I comparison — all runs',
                    fontsize=12, fontweight='bold',
                )
                ax.grid(True, alpha=0.25, linestyle='--')
                ncol = min(4, max(1, idx))
                ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=ncol, fontsize=7, frameon=True)
                fig.subplots_adjust(bottom=0.2)
            else:
                ax.axis('off')
                ax.text(0.5, 0.5, 'Không có dữ liệu I.', ha='center', fontsize=12)
            _save_fig_pdf(pdf, fig)
        except Exception as e:
            logger.warning('PDF comparison chart skipped: %s', e)
            plt.close('all')

        # Bảng so sánh tổng hợp
        if runs_for_table:
            chunk_size = 7
            chunks = [runs_for_table[i : i + chunk_size] for i in range(0, len(runs_for_table), chunk_size)]
            for pi, chunk in enumerate(chunks, start=1):
                try:
                    _render_table_chunk(pdf, chunk, rows_def, metric_col, lang, pi, len(chunks))
                except Exception as e:
                    logger.warning('PDF table chunk %s skipped: %s', pi, e)
                    plt.close('all')

        # Đề xuất can thiệp
        try:
            _render_recommendations_section(pdf, recommendations, lang)
        except Exception as e:
            logger.warning('PDF recommendations section skipped: %s', e)
            plt.close('all')

    buf.seek(0)
    data = buf.getvalue()
    if not data.startswith(b'%PDF'):
        raise RuntimeError('Tạo PDF thất bại (dữ liệu không hợp lệ).')
    return data
