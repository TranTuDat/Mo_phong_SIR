# -*- coding: utf-8 -*-
"""Sinh simulation.html và recommendations.html từ shell index.html."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
INDEX = ROOT / "html" / "index.html"

def extract_block(text, start_pat, end_pat):
    m = re.search(start_pat, text, re.S)
    if not m:
        raise SystemExit(f"Missing: {start_pat}")
    start = m.start()
    m2 = re.search(end_pat, text[m.end() :], re.S)
    if not m2:
        raise SystemExit(f"Missing end: {end_pat}")
    return text[start : m.end() + m2.end()]

def sidebar(active: str) -> str:
    idx = INDEX.read_text(encoding="utf-8")
    aside = re.search(r"<aside class=\"sidebar\">.*?</aside>", idx, re.S).group(0)
    aside = re.sub(r'class="nav-item active"', 'class="nav-item"', aside)
    aside = re.sub(
        rf'<div class="nav-item" data-mau-nav="{active}"',
        f'<div class="nav-item active" data-mau-nav="{active}"',
        aside,
        count=1,
    )
    return aside

def header_block() -> str:
    idx = INDEX.read_text(encoding="utf-8")
    return re.search(r"<header class=\"header\">.*?</header>", idx, re.S).group(0)

def footer_block() -> str:
    idx = INDEX.read_text(encoding="utf-8")
    return re.search(r"<footer class=\"footer\">.*?</footer>", idx, re.S).group(0)

def modal_block() -> str:
    idx = INDEX.read_text(encoding="utf-8")
    return re.search(r'<div id="dataGenModal".*?</div>\s*\n\s*\n', idx, re.S).group(0)

def page_shell(active: str, title: str, body_inner: str, extra_head: str, scripts: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="/css/dashboard-mau.css" />
  <link rel="stylesheet" href="/css/mau-typography.css" />
  <link rel="stylesheet" href="/css/mau-pages.css" />
  <link rel="stylesheet" href="/css/mau-viewport.css" />
{extra_head}
</head>
<body data-mau-page="{active}">
<div class="dashboard">
{sidebar(active)}
    <main class="main-content">
{header_block()}
      <div class="content mau-subpage-content">
{body_inner}
      </div>
{footer_block()}
    </main>
  </div>

{modal_block()}
{scripts}
</body>
</html>
"""

SIM_BODY = """
        <div class="mau-sim-head">
          <div class="mau-sim-head-text">
            <h2 class="mau-page-title">Phân tích mạng</h2>
            <p class="mau-page-subtitle">Mô phỏng SIR trên mạng xã hội — theo dõi lan truyền, so sánh can thiệp theo nút trọng yếu (betweenness, degree, eigenvector).</p>
          </div>
          <p id="dataHint" class="mau-sim-alert" hidden>Chưa có dữ liệu mạng. Chọn <strong>Nhập dữ liệu</strong> trên menu để sinh mạng hoặc tải CSV.</p>
        </div>
        <div class="simulation-container">
          <div class="card sim-controls-panel">
            <div class="card-header"><span class="card-title">Tham số mô hình</span></div>
            <div class="card-body">
              <div class="model-tabs">
                <button type="button" class="tab-btn sim-tab-model active" data-model="pure">SIR thuần</button>
                <button type="button" class="tab-btn sim-tab-model" data-model="dynamic">SIR + can thiệp</button>
              </div>
              <div id="pure-controls" class="model-controls">
                <div class="mau-form-group mau-range-row">
                  <div class="mau-range-label"><label for="pureTrans">Tỷ lệ lây (β)</label><span id="pureTransValue" class="mau-range-val mau-num">0.30</span></div>
                  <input type="range" id="pureTrans" min="0.01" max="0.5" step="0.01" value="0.3" />
                </div>
                <div class="mau-form-group mau-range-row">
                  <div class="mau-range-label"><label for="pureRecov">Tỷ lệ hồi phục (γ)</label><span id="pureRecovValue" class="mau-range-val mau-num">0.10</span></div>
                  <input type="range" id="pureRecov" min="0.01" max="0.5" step="0.01" value="0.1" />
                </div>
                <div class="mau-form-group"><label for="pureDays">Số ngày tối đa</label><input type="number" id="pureDays" value="300" min="10" max="2000" step="10" /></div>
                <div class="mau-form-group"><label for="pureSeed">Seed (tái lập)</label><input type="number" id="pureSeed" value="42" min="1" max="99999" /></div>
                <button type="button" id="btnRunPureSimulation" class="sim-run-btn">▶ Chạy SIR thuần</button>
              </div>
              <div id="dynamic-controls" class="model-controls" style="display:none">
                <div class="mau-form-group mau-range-row">
                  <div class="mau-range-label"><label for="dynTrans">Tỷ lệ lây (β)</label><span id="dynTransValue" class="mau-range-val mau-num">0.30</span></div>
                  <input type="range" id="dynTrans" min="0.01" max="0.5" step="0.01" value="0.3" />
                </div>
                <div class="mau-form-group mau-range-row">
                  <div class="mau-range-label"><label for="dynRecov">Tỷ lệ hồi phục (γ)</label><span id="dynRecovValue" class="mau-range-val mau-num">0.10</span></div>
                  <input type="range" id="dynRecov" min="0.01" max="0.5" step="0.01" value="0.1" />
                </div>
                <div class="mau-form-group"><label for="dynDays">Số ngày tối đa</label><input type="number" id="dynDays" value="300" min="10" max="2000" step="10" /></div>
                <div class="mau-form-group mau-range-row">
                  <div class="mau-range-label"><label for="topK">Top-k miễn nhiễm</label><span id="topKValue" class="mau-range-val mau-num">10</span></div>
                  <input type="range" id="topK" min="1" max="50" step="1" value="10" />
                </div>
                <div class="mau-form-group"><label for="interventionStrategy">Chiến lược can thiệp</label>
                  <select id="interventionStrategy"><option value="betweenness">Betweenness</option><option value="degree">Degree</option><option value="eigenvector">Eigenvector</option></select>
                </div>
                <div class="mau-form-group"><label for="interventionDay">Ngày can thiệp</label><input type="number" id="interventionDay" value="1" min="1" max="300" /><p class="mau-note">Ngày 1 = ngày đầu tiên của mô phỏng</p></div>
                <div class="mau-form-group"><label for="dynSeed">Seed (tái lập)</label><input type="number" id="dynSeed" value="42" min="1" max="99999" /></div>
                <button type="button" id="btnRunDynamicSimulation" class="sim-run-btn">▶ Chạy SIR + can thiệp</button>
              </div>
              <div id="simStatus" class="sim-status-msg" role="status"></div>
            </div>
          </div>
          <div class="card sim-results-panel">
            <div class="card-header sim-results-header">
              <span class="card-title">Kết quả mô phỏng</span>
              <div id="sirRunPicker" class="sir-run-picker sir-run-picker--head" hidden>
                <label for="sirRunSelect">Lần chạy</label>
                <select id="sirRunSelect"></select>
                <span id="sirRunPickerCount" hidden></span>
              </div>
            </div>
            <div id="sirResultsStrip" class="sir-results-strip" hidden>
              <div class="sir-strip-card"><span class="sir-strip-label">Ngày đỉnh</span><strong id="stripPeakDay" class="mau-num">—</strong></div>
              <div class="sir-strip-card"><span class="sir-strip-label">Max I</span><strong id="stripPeakInfected" class="mau-num">—</strong></div>
              <div class="sir-strip-card"><span class="sir-strip-label">Ngày kết thúc</span><strong id="stripFinalDay" class="mau-num">—</strong></div>
              <div class="sir-strip-card"><span class="sir-strip-label">S cuối</span><strong id="stripSusceptibleEnd" class="mau-num">—</strong></div>
            </div>
            <div class="results-tabs">
              <button type="button" class="result-tab-btn active" data-sir-tab="chart">Đồ thị S-I-R</button>
              <button type="button" class="result-tab-btn" data-sir-tab="stats">Chỉ số tóm tắt</button>
              <button type="button" class="result-tab-btn" data-sir-tab="comparison">So sánh can thiệp</button>
            </div>
            <div class="card-body sim-results-body">
              <div id="sir-chart-tab" class="result-tab-content active">
                <div class="sim-chart-wrap sir-chart-tall" id="sirChartWrap">
                  <div id="sirChartPlaceholder" class="sir-chart-placeholder">
                    <p>Điều chỉnh tham số bên trái, sau đó bấm <strong>Chạy SIR</strong> để xem đường cong lan truyền.</p>
                  </div>
                  <canvas id="sirSimChart"></canvas>
                </div>
              </div>
              <div id="sir-stats-tab" class="result-tab-content">
                <div class="sim-stats-grid">
                  <div class="mau-mini-stat"><span>Ngày đỉnh</span><strong id="statPeakDaySim" class="mau-num">—</strong></div>
                  <div class="mau-mini-stat"><span>Max I</span><strong id="statPeakInfectedSim" class="mau-num">—</strong></div>
                  <div class="mau-mini-stat"><span>Ngày kết thúc</span><strong id="statFinalDaySim" class="mau-num">—</strong></div>
                  <div class="mau-mini-stat"><span>R cuối</span><strong id="statTotalRecoveredSim" class="mau-num">—</strong></div>
                </div>
                <div class="additional-stats"><h4>Chi tiết</h4>
                  <table id="statsTableSim" class="mau-detail-table">
                    <tr><td>Mô hình</td><td id="detailModelSim">—</td></tr>
                    <tr><td>β / γ</td><td><span id="detailTransSim" class="mau-num">—</span> / <span id="detailRecovSim" class="mau-num">—</span></td></tr>
                    <tr><td>Thư mục</td><td id="detailOutputPath" class="mau-path">—</td></tr>
                    <tr><td>Ghi chú</td><td id="detailRuntimeSim">—</td></tr>
                  </table>
                </div>
              </div>
              <div id="sir-comparison-tab" class="result-tab-content">
                <div class="sim-chart-wrap sir-chart-tall sir-chart-has-data" id="sirCmpChartWrap"><canvas id="comparisonSimChart"></canvas></div>
                <div class="comparison-table"><table><thead><tr id="comparisonSimTableHeadRow"></tr></thead><tbody id="comparisonSimTableBody"></tbody></table></div>
              </div>
            </div>
          </div>
        </div>
"""

REC_BODY = """
        <div class="mau-rec-head">
          <div class="mau-rec-head-text">
            <h2 class="mau-page-title">Đề xuất can thiệp</h2>
            <p class="mau-page-subtitle">So sánh chiến lược miễn nhiễm nút trọng yếu (SIR + can thiệp) — chọn phương án làm giảm đỉnh nhiễm đồng thời (I).</p>
            <p class="mau-rec-meta">Bộ dữ liệu: <code id="recOutputFolder" class="rec-folder-code">—</code></p>
          </div>
          <div class="mau-rec-head-actions">
            <a href="/simulation" class="card-btn rec-link-sim">Mô phỏng SIR</a>
            <button type="button" class="sim-run-btn rec-refresh-btn" id="btnAnalyze">Phân tích lại</button>
          </div>
        </div>
        <div id="recStatus" class="sim-status-msg rec-status-bar" role="status" hidden></div>
        <div class="stats-row rec-kpi-row">
          <div class="stat-card cyan rec-kpi">
            <div class="stat-icon cyan"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93z"/></svg></div>
            <div class="stat-content">
              <div class="stat-label">SIR thuần — Max I</div>
              <div class="stat-value mau-num" id="recPurePeakI">—</div>
              <div class="stat-change">Kịch bản không can thiệp</div>
            </div>
          </div>
          <div class="stat-card blue rec-kpi">
            <div class="stat-icon blue"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg></div>
            <div class="stat-content">
              <div class="stat-label">SIR thuần — Ngày đỉnh</div>
              <div class="stat-value mau-num" id="recPurePeakDay">—</div>
              <div class="stat-change">Tham chiếu thời gian</div>
            </div>
          </div>
          <div class="stat-card red rec-kpi">
            <div class="stat-icon red"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg></div>
            <div class="stat-content">
              <div class="stat-label">Can thiệp tốt nhất — Max I</div>
              <div class="stat-value mau-num" id="recWinnerPeakI">—</div>
              <div class="stat-change" id="recWinnerDelta">—</div>
            </div>
          </div>
          <div class="stat-card yellow rec-kpi">
            <div class="stat-icon yellow"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg></div>
            <div class="stat-content">
              <div class="stat-label">Chiến lược đề xuất</div>
              <div class="stat-value rec-strat-name" id="recWinnerStrategy">—</div>
              <div class="stat-change" id="recWinnerFinal">—</div>
            </div>
          </div>
        </div>
        <div class="rec-main-grid">
          <div class="rec-tables-stack">
            <div class="card rec-table-card">
              <div class="card-header">
                <span class="card-title">Theo chỉ số trung tâm</span>
                <span class="rec-table-hint">Mỗi loại: kịch bản tốt nhất</span>
              </div>
              <div class="card-body rec-table-body">
                <div class="table-container">
                  <table class="rec-table">
                    <thead><tr><th>Chiến lược</th><th>Ngày CT</th><th>Top-k</th><th>Đỉnh I</th><th>Ngày đỉnh</th><th>Kết thúc</th><th>Δ I</th></tr></thead>
                    <tbody id="recStrategiesBody"></tbody>
                  </table>
                </div>
              </div>
            </div>
            <div class="card rec-table-card rec-runs-card">
              <div class="card-header">
                <span class="card-title">Các mẫu can thiệp đã mô phỏng</span>
                <span class="rec-table-hint">Mọi lần chạy — hàng xanh = đề xuất chung</span>
              </div>
              <div class="card-body rec-table-body">
                <div class="table-container">
                  <table class="rec-table">
                    <thead><tr><th>Chiến lược</th><th>Ngày CT</th><th>Top-k</th><th>Đỉnh I</th><th>Ngày đỉnh</th><th>Kết thúc</th><th>Δ I</th><th></th></tr></thead>
                    <tbody id="recRunsBody"></tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
          <div class="card rec-winner-card">
            <div class="card-header"><span class="card-title">Kết luận &amp; nút ưu tiên</span></div>
            <div class="card-body">
              <div class="recommendation-item rec-winner-hero rec-winner-empty" id="recWinnerHero">
                <div class="recommendation-icon green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>
                <div class="recommendation-content">
                  <div class="recommendation-title" id="recWinnerTitle">Chưa có đề xuất</div>
                  <div class="recommendation-desc" id="recWinnerSummary">Chạy mô phỏng SIR + can thiệp tại Phân tích mạng.</div>
                </div>
                <span class="recommendation-priority p1">Ưu tiên 1</span>
              </div>
              <h4 class="rec-nodes-heading">Danh sách nút miễn nhiễm (Top-k)</h4>
              <ul id="recWinnerNodes" class="rec-node-list"></ul>
            </div>
          </div>
        </div>
"""

def main():
    (ROOT / "html" / "simulation.html").write_text(
        page_shell(
            "simulation",
            "Phân tích mạng — Mô phỏng SIR | InfoOps Analyzer",
            SIM_BODY,
            '  <script src="/vendor/chart.min.js"></script>',
            """  <script src="/js/i18n.js"></script>
  <script src="/js/mau-shell.js"></script>
  <script src="/vendor/chart.min.js"></script>
  <script src="/js/sir_page.js"></script>""",
        ),
        encoding="utf-8",
    )
    (ROOT / "html" / "recommendations.html").write_text(
        page_shell(
            "recommendations",
            "Đề xuất can thiệp | InfoOps Analyzer",
            REC_BODY,
            "",
            """  <script src="/js/mau-shell.js"></script>
  <script src="/js/recommendations.js"></script>""",
        ),
        encoding="utf-8",
    )
    print("Built simulation.html, recommendations.html")

if __name__ == "__main__":
    main()
