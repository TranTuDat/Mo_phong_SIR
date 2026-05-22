# -*- coding: utf-8 -*-
"""Đồng bộ html/index.html và css/dashboard-mau.css từ Mau.html."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MAU = ROOT / "Mau.html"
CSS_OUT = ROOT / "css" / "dashboard-mau.css"
HTML_OUT = ROOT / "html" / "index.html"

MODAL_CSS = """
.modal-overlay {
  display: none; position: fixed; inset: 0; background: rgba(15,23,42,0.45);
  z-index: 1000; align-items: center; justify-content: center; padding: 16px;
}
.modal-overlay.open { display: flex; }
.modal-box {
  background: #fff; border-radius: 10px; width: 100%; max-width: 400px;
  box-shadow: 0 20px 40px rgba(0,0,0,0.15); overflow: hidden;
}
.modal-head {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 14px; border-bottom: 1px solid #e5e7eb;
}
.modal-head h3 { font-size: 13px; font-weight: 600; color: #1f2937; }
.modal-close {
  border: none; background: none; font-size: 22px; line-height: 1; cursor: pointer; color: #6b7280;
}
.modal-body { padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.modal-body label { font-size: 11px; color: #374151; font-weight: 500; }
.modal-body input, .modal-body select {
  width: 100%; padding: 6px 8px; border: 1px solid #d1d5db; border-radius: 6px; font-size: 12px;
}
.modal-body small { font-size: 10px; color: #9ca3af; }
.modal-foot {
  display: flex; justify-content: flex-end; gap: 8px; padding: 10px 14px;
  border-top: 1px solid #e5e7eb; background: #f9fafb;
}
.modal-foot button {
  padding: 6px 12px; font-size: 11px; border-radius: 6px; border: 1px solid #d1d5db;
  background: #fff; cursor: pointer;
}
.modal-foot button.primary { background: #3b82f6; color: #fff; border-color: #3b82f6; }
.toast-msg {
  position: fixed; bottom: 20px; right: 20px; background: #1e293b; color: #fff;
  padding: 10px 14px; border-radius: 8px; font-size: 12px; z-index: 1100;
  max-width: 360px; box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}
"""

def main():
    text = MAU.read_text(encoding="utf-8")
    m_style = re.search(r"<style>(.*?)</style>", text, re.S)
    if not m_style:
        raise SystemExit("Không tìm thấy <style> trong Mau.html")
    css = m_style.group(1).strip()
    css_lines = [ln[4:] if ln.startswith("    ") else ln for ln in css.splitlines()]
    css_body = "\n".join(css_lines).strip() + "\n" + MODAL_CSS.strip() + "\n"
    CSS_OUT.write_text(css_body, encoding="utf-8")

    m_body = re.search(r"<body>(.*?)</body>", text, re.S)
    if not m_body:
        raise SystemExit("Không tìm thấy <body> trong Mau.html")
    body = m_body.group(1).strip()
    # Bỏ script inline Mau
    body = re.sub(r"<script>.*?</script>", "", body, flags=re.S).strip()

    # Hook API — giữ nguyên markup Mau
    body = body.replace(
        '<div class="nav-item">\n          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>\n          <span>Nhập dữ liệu</span>',
        '<div class="nav-item" id="menuOpenData">\n          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>\n          <span>Nhập dữ liệu</span>',
        1,
    )
    body = body.replace(
        '<div class="data-row">\n          <span>Tài khoản (Node):</span>\n          <span>1,248</span>',
        '<div class="data-row">\n          <span>Tài khoản (Node):</span>\n          <span id="sideStatNodes">1,248</span>',
        1,
    )
    body = body.replace(
        '<div class="data-row">\n          <span>Quan hệ (Edge):</span>\n          <span>3,682</span>',
        '<div class="data-row">\n          <span>Quan hệ (Edge):</span>\n          <span id="sideStatEdges">3,682</span>',
        1,
    )
    body = body.replace(
        '<div class="data-row">\n          <span>Ngày dữ liệu:</span>\n          <span>20/04/2026</span>',
        '<div class="data-row">\n          <span>Ngày dữ liệu:</span>\n          <span id="sideStatDate">20/04/2026</span>',
        1,
    )
    body = body.replace(
        '<div class="data-ready">',
        '<div class="data-ready" id="dataReadyBadge">',
        1,
    )

    body = body.replace(
        '<div class="stat-value">1,248</div>',
        '<div class="stat-value" id="stat-users">1,248</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-value">3,682</div>',
        '<div class="stat-value" id="stat-edges">3,682</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-value">5,874</div>',
        '<div class="stat-value" id="stat-interactions">5,874</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-value">87</div>',
        '<div class="stat-value" id="stat-high-risk">87</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-change">+12.5% so với lần trước</div>',
        '<div class="stat-change" id="stat-users-trend">+12.5% so với lần trước</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-change">+15.3% so với lần trước</div>',
        '<div class="stat-change" id="stat-edges-trend">+15.3% so với lần trước</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-change">+18.7% so với lần trước</div>',
        '<div class="stat-change" id="stat-interactions-trend">+18.7% so với lần trước</div>',
        1,
    )
    body = body.replace(
        '<div class="stat-change negative">+9 so với lần trước</div>',
        '<div class="stat-change negative" id="stat-high-risk-trend">+9 so với lần trước</div>',
        1,
    )

    body = body.replace(
        '<button class="card-btn" onclick="initGraph()">',
        '<button class="card-btn" id="refreshGraph">',
        1,
    )
    body = body.replace(
        '<button class="zoom-btn" onclick="zoomIn()">+</button>',
        '<button class="zoom-btn" id="zoomIn">+</button>',
        1,
    )
    body = body.replace(
        '<button class="zoom-btn" onclick="zoomOut()">−</button>',
        '<button class="zoom-btn" id="zoomOut">−</button>',
        1,
    )
    body = body.replace(
        '<select class="card-btn" style="border: 1px solid #e5e7eb;">\n                  <option>Hiển thị nhãn</option>',
        '<select class="card-btn" id="labelToggle" style="border: 1px solid #e5e7eb;">\n                  <option>Hiển thị nhãn</option>',
        1,
    )

    body = body.replace("<tbody>", '<tbody id="topNodesTable">', 1)
    body = body.replace(
        '<div class="community-list">',
        '<div class="community-list" id="clustersList">',
        1,
    )
    body = body.replace(
        '<div class="recommendation-list">',
        '<div class="recommendation-list" id="recommendationList">',
        1,
    )

    body = body.replace(
        """<div class="account-name">
                    User_15
                    <span class="account-badge">Nguy cơ cao</span>
                  </div>""",
        """<div class="account-name">
                    <span id="selectedName">User_15</span>
                    <span class="account-badge" id="selectedAccountBadge">Nguy cơ cao</span>
                  </div>""",
        1,
    )
    body = body.replace(
        "<span>Người theo dõi: <strong>12,480</strong></span>",
        '<span>Người theo dõi: <strong id="selectedFollowers">12,480</strong></span>',
        1,
    )
    body = body.replace(
        "<span>Bài viết: <strong>245</strong></span>",
        '<span>Bài viết: <strong id="selectedPosts">245</strong></span>',
        1,
    )
    body = body.replace(
        "<span>Share: <strong>1,023</strong></span>",
        '<span>Share: <strong id="selectedShares">1,023</strong></span>',
        1,
    )
    body = body.replace(
        "<span>Comment: <strong>652</strong></span>",
        '<span>Comment: <strong id="selectedComments">652</strong></span>',
        1,
    )
    body = body.replace(
        "<strong>Vai:</strong> Nút trung gian trọng yếu, lan truyền mạnh",
        '<strong>Vai:</strong> <span id="selectedRoleLine">Nút trung gian trọng yếu, lan truyền mạnh</span>',
        1,
    )
    body = body.replace(
        "<strong>Mô tả:</strong> Kết nối nhiều nhóm cộng đồng, có tần suất chia sẻ cao.",
        '<strong>Mô tả:</strong> <span id="selectedDescLine">Kết nối nhiều nhóm cộng đồng, có tần suất chia sẻ cao.</span>',
        1,
    )
    body = body.replace(
        '<span class="community-total">Số cụm: 5</span>',
        '<span class="community-total">Số cụm: <span id="clusterCountNum">5</span></span>',
        1,
    )
    body = body.replace(
        "<span>Phiên bản 1.0.0 | 20/04/2026 10:30:45</span>",
        '<span>Phiên bản 1.0.0 | <span id="footerTimestamp">20/04/2026 10:30:45</span></span>',
        1,
    )

    for bid, label in [
        ("btnGuide", "Hướng dẫn"),
        ("btnReport", "Báo cáo"),
        ("btnExport", "Xuất dữ liệu"),
    ]:
        body = body.replace(
            f'<button class="header-btn">\n          <svg',
            f'<button type="button" class="header-btn" id="{bid}">\n          <svg',
            1,
        )
    body = body.replace(
        '<button class="header-btn">\n          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15',
        '<button type="button" class="header-btn" id="btnSettings">\n          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15',
        1,
    )

    modal = """
<div id="dataGenModal" class="modal-overlay">
  <div class="modal-box">
    <div class="modal-head"><h3>Tạo dữ liệu mạng</h3><button type="button" class="modal-close" id="modalClose">&times;</button></div>
    <div class="modal-body">
      <div><label for="numUsers">Số người dùng</label><input type="number" id="numUsers" value="500" min="10" max="2000" step="10" /><small>10–2000</small></div>
      <div><label for="relationshipProb">Xác suất có cạnh</label><input type="number" id="relationshipProb" value="0.025" min="0.001" max="0.1" step="0.001" /><small>0,001–0,1</small></div>
      <div><label for="randomSeed">Seed</label><input type="number" id="randomSeed" value="42" min="1" max="9999" /></div>
      <div><label for="dataSource">Nguồn</label><select id="dataSource"><option value="generate">Sinh ngẫu nhiên</option><option value="upload">Tải CSV</option></select></div>
      <div id="fileUploadGroup" style="display:none"><label for="dataFile">File CSV</label><input type="file" id="dataFile" accept=".csv" /></div>
    </div>
    <div class="modal-foot"><button type="button" id="modalCancel">Hủy</button><button type="button" class="primary" id="btnConfirmGenerate">Tạo dữ liệu</button></div>
  </div>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>InfoOps Analyzer - Công cụ phân tích mạng xã hội</title>
  <link rel="stylesheet" href="/css/dashboard-mau.css" />
</head>
<body>
{body}

{modal}

  <script src="/js/mau-graph.js"></script>
  <script src="/js/mau-dashboard.js"></script>
</body>
</html>
"""
    HTML_OUT.write_text(html, encoding="utf-8")
    print("OK:", CSS_OUT, HTML_OUT)

if __name__ == "__main__":
    main()
