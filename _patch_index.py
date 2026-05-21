from pathlib import Path
p = Path('html/index.html')
t = p.read_text(encoding='utf-8')
start = t.find('                <motion class="dash-legend-bar"')
if start < 0:
    start = t.find('                <div class="dash-legend-bar"')
end = t.find('                <div class="sna-graph-canvas-wrap')
new_legend = """                <div class="sna-graph-legend" id="clusterLegendRow">
                  <span><span class="sna-risk-dot high"></span><span data-i18n="dashboard.riskHigh">Cao</span></span>
                  <span><span class="sna-risk-dot medium"></span><span data-i18n="dashboard.riskMed">Trung bình</span></span>
                  <span><span class="sna-risk-dot low"></span><span data-i18n="dashboard.riskLow">Thấp</span></span>
                  <span><span class="sna-risk-dot unknown"></span><span data-i18n="dashboard.riskUnknown">Chưa xác định</span></span>
                </div>
"""
if start >= 0 and end > start:
    t = t[:start] + new_legend + t[end:]
    p.write_text(t, encoding='utf-8')
    print('patched ok')
else:
    print('failed', start, end)
