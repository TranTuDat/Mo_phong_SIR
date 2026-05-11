/**
 * Đa ngôn ngữ VI / EN — dùng chung dashboard và trang SIR.
 * HTML: data-i18n="key.sub" | data-i18n-placeholder | data-i18n-title | data-i18n-html (HTML nhỏ, cẩn thận XSS)
 */
(function (global) {
  const STORAGE_KEY = 'appLang';

  const STRINGS = {
    vi: {
      meta: { appTitle: 'InfoOps Analyzer', sirTitle: 'Mô phỏng SIR — InfoOps Analyzer' },
      shell: {
        themeLight: 'Chế độ sáng',
        themeDark: 'Chế độ tối',
        langToEn: 'English',
        langToVi: 'Tiếng Việt',
      },
      nav: {
        overview: 'Tổng quan',
        sirPage: 'Mô phỏng SIR',
        sirPageLong: 'Trang mô phỏng SIR',
        networkOverview: 'Tổng quan mạng',
        sirActive: 'Mô phỏng SIR',
      },
      brand: {
        subtitle: 'Phân tích mạng & lan truyền',
        sirSubtitle: 'Mô hình SIR trên đồ thị xã hội',
      },
      sidebar: {
        nodes: 'Số nút (node)',
        edges: 'Số cạnh (edge)',
        interaction: 'Loại tương tác',
        interactionVal: 'Chia sẻ / Bình luận',
        dataDate: 'Ngày dữ liệu',
        ready: 'Dữ liệu sẵn sàng',
        nodesShort: 'Node (bộ hiện tại)',
        edgesShort: 'Edge',
      },
      dashboard: {
        title: 'Tổng quan',
        simLink: 'Trang mô phỏng SIR',
        generate: 'Tạo dữ liệu',
        sirPure: 'SIR thuần',
        sirDyn: 'SIR động',
        cleanup: 'Dọn output cũ',
        metricUsers: 'Tổng tài khoản',
        metricEdges: 'Tổng quan hệ',
        metricEngagement: 'Tương tác (ước lượng)',
        metricHighRisk: 'Nguy cơ cao (ước lượng)',
        metricFootnote: 'Ước lượng từ kích thước mạng',
        graphTitle: 'Bản đồ mạng',
        graphSub: 'Node theo mức độ nguy cơ và vai trò cấu trúc.',
        labels: 'Nhãn',
        yes: 'Có',
        no: 'Không',
        refresh: 'Làm mới',
        riskHigh: 'Nguy cơ cao',
        riskMed: 'Trung bình',
        riskLow: 'Thấp',
        riskUnknown: 'Chưa xác định',
        graphHint: 'Nhấp nút để xem chi tiết và chỉ số.',
        sirPanel: 'Kết quả SIR (nhanh)',
        sirNone: 'Chưa chạy mô phỏng',
        sirDone: 'Đã chạy xong',
        lblModel: 'Mô hình',
        lblPeakDay: 'Ngày đỉnh',
        lblPeakI: 'Đỉnh nhiễm (I)',
        lblFinal: 'Ngày kết thúc',
        lblOutput: 'Thư mục kết quả',
        topNodes: 'Top 10 nút',
        topAuto: 'Tự động',
        thRank: '#',
        thAccount: 'Tài khoản',
        thRole: 'Vai trò',
        thDegree: 'Degree',
        thBetw: 'Betweenness',
        thEigen: 'Eigenvector',
        thRisk: 'Điểm nguy cơ',
        profileRoleIntro: 'Vai trò:',
        clusters: 'Cụm cộng đồng',
        clusterUnit: 'cụm',
        accountsCount: '{n} tài khoản',
        clustersCount: 'cụm',
        profileFollowers: 'Người theo dõi',
        profilePosts: 'Bài viết',
        recs: 'Gợi ý can thiệp',
        footerVer: 'Phiên bản',
        footerUpd: 'Cập nhật',
        modalTitle: 'Tạo dữ liệu mạng',
        lblNumUsers: 'Số người dùng',
        hintUsers: '10–2000',
        lblProb: 'Xác suất có cạnh',
        hintProb: '0,001–0,1 (càng cao càng dày)',
        lblSeed: 'Seed',
        hintSeed: 'Tái lập kết quả',
        lblSource: 'Nguồn',
        srcGen: 'Sinh ngẫu nhiên',
        srcUp: 'Tải CSV',
        lblFile: 'File CSV',
        hintCsv: 'Cột: id, name, followers, posts, shares, comments, risk',
        cancel: 'Hủy',
        confirmGen: 'Tạo dữ liệu',
      },
      sir: {
        pageTitle: 'Mô phỏng SIR trên mạng xã hội',
        backDash: 'Về tổng quan',
        intro:
          'Chỉnh tham số rồi chạy trên <strong>bộ dữ liệu output mới nhất</strong> (tạo từ tổng quan). Kết quả: đồ thị S–I–R, đỉnh dịch, ngày kết thúc.',
        params: 'Tham số mô hình',
        tabPure: 'SIR thuần',
        tabDyn: 'SIR + can thiệp',
        beta: 'Tỷ lệ lây (β)',
        gamma: 'Tỷ lệ hồi phục (γ)',
        maxDays: 'Số ngày tối đa',
        seed: 'Seed',
        topK: 'Top-k miễn nhiễm (betweenness)',
        runPure: 'Chạy SIR thuần',
        runDyn: 'Chạy SIR + can thiệp',
        hintCompare: 'Gợi ý: chạy SIR thuần trước, rồi SIR + can thiệp để mở tab so sánh.',
        hintCompareHtml:
          'Gợi ý: chạy <strong>SIR thuần</strong> trước, rồi <strong>SIR + can thiệp</strong> để mở tab so sánh.',
        stripPeak: 'Ngày đỉnh',
        stripPeakI: 'Max đồng thời nhiễm (I)',
        stripFinal: 'Ngày kết thúc (ghi nhận)',
        stripS: 'Nhạy cảm (S) cuối',
        tabChart: 'Đồ thị S–I–R',
        tabStats: 'Chỉ số',
        tabCompare: 'So sánh',
        chartFoot: 'Trục ngang: ngày · Trục dọc: số cá thể.',
        statPeakLabel: 'Ngày đỉnh (index I max)',
        statPeakI: 'Max đồng thời nhiễm',
        statFinal: 'Ngày kết thúc',
        statR: 'Hồi phục (R) ngày cuối',
        detailTitle: 'Chi tiết lần chạy',
        rowModel: 'Mô hình',
        rowRates: 'β / γ đã dùng',
        rowOut: 'Thư mục kết quả',
        rowNote: 'Ghi chú',
        cmpMetric: 'Chỉ số',
        cmpPure: 'SIR thuần',
        cmpDyn: 'SIR + can thiệp',
        cmpDelta: 'Chênh (%)',
        cmpPeak: 'Ngày đỉnh',
        cmpPeakI: 'Đỉnh I',
        cmpFinal: 'Ngày kết thúc',
        footerNote: 'Kết quả: Pure_SIR / SIR_dynamic_immunization',
        dataHint: 'Chưa có output. Về tổng quan và bấm «Tạo dữ liệu».',
        dataHintHtml:
          'Chưa có bộ dữ liệu output. Về <a href="/">tổng quan</a> và dùng «Tạo dữ liệu».',
        chartPure: 'Đường cong S–I–R (SIR thuần)',
        chartDyn: 'Đường cong S–I–R (SIR + can thiệp)',
        chartCmp: 'So sánh số ca nhiễm (I)',
        noteImmune: 'Miễn nhiễm top-{k} nút (ngày 1)',
        noteDash: '—',
        datasetS: 'Dễ bị lây (S)',
        datasetI: 'Đang nhiễm (I)',
        datasetR: 'Hồi phục (R)',
        datasetPureI: 'SIR thuần — I',
        datasetDynI: 'SIR + can thiệp — I',
      },
      risk: { High: 'Cao', Medium: 'Trung bình', Low: 'Thấp', Unknown: 'Chưa rõ' },
      roles: {
        bridge: 'Nút trung gian',
        spreader: 'Nút lan truyền',
        observer: 'Quan sát',
      },
      msgs: {
        loadingGraph: 'Đang tải dữ liệu…',
        errLoad: 'Không tải được dữ liệu.',
        errUpload: 'Lỗi upload.',
        okUpload: 'Upload thành công.',
        errGen: 'Lỗi tạo dữ liệu.',
        okGen: 'Tạo dữ liệu thành công.',
        errSir: 'Lỗi mô phỏng.',
        okSir: 'Mô phỏng hoàn thành.',
        askOpenSir: 'Mở trang Mô phỏng SIR để xem biểu đồ đầy đủ?',
        savedSir: 'Đã lưu kết quả.',
        cleanupAsk: 'Giữ 3 bản mới nhất và xóa output cũ?',
        cleanupOk: 'Đã xóa {n} thư mục.',
        errCleanup: 'Không dọn được output.',
        pickCsv: 'Chọn file CSV.',
        runningPure: 'Đang chạy SIR thuần…',
        runningDyn: 'Đang chạy SIR + can thiệp…',
        donePure: 'Hoàn thành SIR thuần.',
        doneDyn: 'Hoàn thành SIR + can thiệp.',
        errParams: 'Điền đủ tham số.',
        errRun: 'Lỗi: ',
        noDesc: 'Chưa có mô tả.',
        processing: 'Đang xử lý…',
      },
      rec: {
        r1: 'Kiểm soát luồng tại tài khoản nguy cơ cao',
        r2: 'Giám sát nút betweenness lớn',
        r3: 'Cảnh báo nhóm tương tác bất thường',
        r4: 'Rà soát cụm chưa xác định',
        p1: 'Ưu tiên 1',
        p2: 'Ưu tiên 2',
        p3: 'Ưu tiên 3',
        p4: 'Ưu tiên 4',
      },
    },
    en: {
      meta: { appTitle: 'InfoOps Analyzer', sirTitle: 'SIR simulation — InfoOps Analyzer' },
      shell: {
        themeLight: 'Light mode',
        themeDark: 'Dark mode',
        langToEn: 'English',
        langToVi: 'Tiếng Việt',
      },
      nav: {
        overview: 'Overview',
        sirPage: 'SIR simulation',
        sirPageLong: 'SIR simulation page',
        networkOverview: 'Network overview',
        sirActive: 'SIR simulation',
      },
      brand: {
        subtitle: 'Network & propagation analytics',
        sirSubtitle: 'SIR on social graph',
      },
      sidebar: {
        nodes: 'Nodes',
        edges: 'Edges',
        interaction: 'Interaction type',
        interactionVal: 'Share / comment',
        dataDate: 'Data date',
        ready: 'Data ready',
        nodesShort: 'Nodes (current set)',
        edgesShort: 'Edges',
      },
      dashboard: {
        title: 'Overview',
        simLink: 'SIR simulation page',
        generate: 'Generate data',
        sirPure: 'Pure SIR',
        sirDyn: 'Dynamic SIR',
        cleanup: 'Clean old outputs',
        metricUsers: 'Accounts',
        metricEdges: 'Relationships',
        metricEngagement: 'Engagement (est.)',
        metricHighRisk: 'High risk (est.)',
        metricFootnote: 'Estimated from network size',
        graphTitle: 'Interaction map',
        graphSub: 'Nodes by risk level and structural role.',
        labels: 'Labels',
        yes: 'On',
        no: 'Off',
        refresh: 'Refresh',
        riskHigh: 'High risk',
        riskMed: 'Medium',
        riskLow: 'Low',
        riskUnknown: 'Unknown',
        graphHint: 'Click a node for details and metrics.',
        sirPanel: 'SIR snapshot (quick)',
        sirNone: 'No run yet',
        sirDone: 'Run completed',
        lblModel: 'Model',
        lblPeakDay: 'Peak day',
        lblPeakI: 'Peak infected (I)',
        lblFinal: 'End day',
        lblOutput: 'Output folder',
        topNodes: 'Top 10 nodes',
        topAuto: 'Auto',
        thRank: '#',
        thAccount: 'Account',
        thRole: 'Role',
        thDegree: 'Degree',
        thBetw: 'Betweenness',
        thEigen: 'Eigenvector',
        thRisk: 'Risk score',
        profileRoleIntro: 'Role:',
        clusters: 'Communities',
        clusterUnit: 'clusters',
        accountsCount: '{n} accounts',
        clustersCount: 'clusters',
        profileFollowers: 'Followers',
        profilePosts: 'Posts',
        recs: 'Suggested actions',
        footerVer: 'Version',
        footerUpd: 'Updated',
        modalTitle: 'Generate network data',
        lblNumUsers: 'Number of users',
        hintUsers: '10–2000',
        lblProb: 'Edge probability',
        hintProb: '0.001–0.1 (higher = denser)',
        lblSeed: 'Random seed',
        hintSeed: 'Reproducible runs',
        lblSource: 'Source',
        srcGen: 'Random',
        srcUp: 'Upload CSV',
        lblFile: 'CSV file',
        hintCsv: 'Columns: id, name, followers, posts, shares, comments, risk',
        cancel: 'Cancel',
        confirmGen: 'Generate',
      },
      sir: {
        pageTitle: 'SIR simulation on social network',
        backDash: 'Back to overview',
        intro:
          'Tune parameters and run on the <strong>latest output dataset</strong> (from overview). Results: S–I–R curves, epidemic peak, end day.',
        params: 'Model parameters',
        tabPure: 'Pure SIR',
        tabDyn: 'SIR + intervention',
        beta: 'Transmission rate (β)',
        gamma: 'Recovery rate (γ)',
        maxDays: 'Max days',
        seed: 'Seed',
        topK: 'Immunized top-k (by betweenness)',
        runPure: 'Run pure SIR',
        runDyn: 'Run SIR + intervention',
        hintCompare: 'Tip: run pure SIR first, then SIR + intervention to unlock comparison.',
        hintCompareHtml:
          'Tip: run <strong>pure SIR</strong> first, then <strong>SIR + intervention</strong> to unlock comparison.',
        stripPeak: 'Peak day',
        stripPeakI: 'Peak concurrent I',
        stripFinal: 'Recorded end day',
        stripS: 'Susceptible (S) at end',
        tabChart: 'S–I–R chart',
        tabStats: 'Metrics',
        tabCompare: 'Compare',
        chartFoot: 'Horizontal: day · Vertical: compartment counts.',
        statPeakLabel: 'Peak day (argmax I)',
        statPeakI: 'Peak concurrent infected',
        statFinal: 'End day',
        statR: 'Recovered (R) at end',
        detailTitle: 'Run details',
        rowModel: 'Model',
        rowRates: 'β / γ used',
        rowOut: 'Output path',
        rowNote: 'Notes',
        cmpMetric: 'Metric',
        cmpPure: 'Pure SIR',
        cmpDyn: 'SIR + intervention',
        cmpDelta: 'Delta (%)',
        cmpPeak: 'Peak day',
        cmpPeakI: 'Peak I',
        cmpFinal: 'End day',
        footerNote: 'Outputs: Pure_SIR / SIR_dynamic_immunization',
        dataHint: 'No output yet. Go to overview and click «Generate data».',
        dataHintHtml:
          'No output dataset yet. Go to <a href="/">overview</a> and use «Generate data».',
        chartPure: 'S–I–R curves (pure SIR)',
        chartDyn: 'S–I–R curves (SIR + intervention)',
        chartCmp: 'Infected compartment (I) comparison',
        noteImmune: 'Immunized top-{k} nodes (day 1)',
        noteDash: '—',
        datasetS: 'Susceptible (S)',
        datasetI: 'Infected (I)',
        datasetR: 'Recovered (R)',
        datasetPureI: 'Pure SIR — I',
        datasetDynI: 'SIR + intervention — I',
      },
      risk: { High: 'High', Medium: 'Medium', Low: 'Low', Unknown: 'Unknown' },
      roles: {
        bridge: 'Bridge node',
        spreader: 'Spreader node',
        observer: 'Observer',
      },
      msgs: {
        loadingGraph: 'Loading data…',
        errLoad: 'Could not load data.',
        errUpload: 'Upload failed.',
        okUpload: 'Upload successful.',
        errGen: 'Generation failed.',
        okGen: 'Data generated.',
        errSir: 'Simulation failed.',
        okSir: 'Simulation finished.',
        askOpenSir: 'Open the SIR page for full charts?',
        savedSir: 'Results saved.',
        cleanupAsk: 'Keep 3 newest outputs and delete the rest?',
        cleanupOk: 'Removed {n} folders.',
        errCleanup: 'Cleanup failed.',
        pickCsv: 'Please choose a CSV file.',
        runningPure: 'Running pure SIR…',
        runningDyn: 'Running SIR + intervention…',
        donePure: 'Pure SIR completed.',
        doneDyn: 'SIR + intervention completed.',
        errParams: 'Please fill all parameters.',
        errRun: 'Error: ',
        noDesc: 'No description.',
        processing: 'Processing…',
      },
      rec: {
        r1: 'Control flows at high-risk accounts',
        r2: 'Monitor high-betweenness nodes',
        r3: 'Alert on anomalous engagement spikes',
        r4: 'Review undefined clusters',
        p1: 'Priority 1',
        p2: 'Priority 2',
        p3: 'Priority 3',
        p4: 'Priority 4',
      },
    },
  };

  function getLang() {
    const s = localStorage.getItem(STORAGE_KEY);
    return s === 'en' ? 'en' : 'vi';
  }

  function resolve(obj, path) {
    return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);
  }

  function t(key, vars) {
    let s = resolve(STRINGS[getLang()], key) ?? resolve(STRINGS.vi, key) ?? key;
    if (vars && typeof s === 'string') {
      Object.keys(vars).forEach((k) => {
        s = s.replace(new RegExp(`\\{${k}\\}`, 'g'), String(vars[k]));
      });
    }
    return s;
  }

  function applyI18n(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-i18n]').forEach((el) => {
      const key = el.getAttribute('data-i18n');
      if (!key) return;
      const val = t(key);
      if (el.tagName === 'OPTION') {
        el.textContent = val;
      } else {
        el.textContent = val;
      }
    });
    scope.querySelectorAll('[data-i18n-html]').forEach((el) => {
      const key = el.getAttribute('data-i18n-html');
      if (key) el.innerHTML = t(key);
    });
    scope.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (key) el.setAttribute('placeholder', t(key));
    });
    scope.querySelectorAll('[data-i18n-title]').forEach((el) => {
      const key = el.getAttribute('data-i18n-title');
      if (key) el.setAttribute('title', t(key));
    });
    const meta = STRINGS[getLang()].meta;
    if (meta) {
      const isSir = document.body.classList.contains('sir-page-body');
      document.title = isSir ? meta.sirTitle : meta.appTitle;
    }
    const langToggle = document.getElementById('langToggle');
    if (langToggle) {
      langToggle.textContent = getLang() === 'vi' ? 'EN' : 'VI';
      langToggle.setAttribute('title', getLang() === 'vi' ? t('shell.langToEn') : t('shell.langToVi'));
    }
    const themeBtn = document.getElementById('themeToggle');
    if (themeBtn) {
      const th = document.documentElement.getAttribute('data-theme') || 'light';
      themeBtn.setAttribute('title', th === 'dark' ? t('shell.themeLight') : t('shell.themeDark'));
    }
  }

  function setLang(lang) {
    const next = lang === 'en' ? 'en' : 'vi';
    localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next === 'en' ? 'en' : 'vi';
    applyI18n();
    window.dispatchEvent(new CustomEvent('app:langchange', { detail: { lang: next } }));
  }

  function toggleLang() {
    setLang(getLang() === 'vi' ? 'en' : 'vi');
  }

  global.I18N = { t, getLang, setLang, toggleLang, applyI18n, STRINGS };
})(typeof window !== 'undefined' ? window : globalThis);
