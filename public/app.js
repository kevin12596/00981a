/* 00981A ETF Tracker — Frontend Logic */

const DATA_URL    = './data/latest_diff.json';
const HISTORY_URL = './data/history.json';

// ─────────────────────────────────────────────
// TradingView link
// ─────────────────────────────────────────────

function tvUrl(code) {
  const n = parseInt(code, 10);
  const exchange = (n >= 6000 && n <= 6999) ? 'TPEX' : 'TWSE';
  return `https://www.tradingview.com/chart/?symbol=${exchange}%3A${code}`;
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function fmt(n, decimals = 2) {
  if (n == null || isNaN(n)) return '—';
  return n.toLocaleString('zh-TW', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function fmtShares(n) {
  if (n == null) return '—';
  const abs = Math.abs(n);
  if (abs >= 1000000) return (n / 1000000).toFixed(2) + 'M';
  if (abs >= 1000) return (n / 1000).toFixed(0) + 'K';
  return n.toString();
}

function fmtPct(n, decimals = 2) {
  if (n == null || isNaN(n)) return '—';
  const sign = n > 0 ? '+' : '';
  return sign + fmt(n, decimals) + '%';
}

function pctClass(n) {
  if (n == null) return 'neutral';
  if (n > 0) return 'positive';
  if (n < 0) return 'negative';
  return 'neutral';
}

function actionInfo(action) {
  const map = {
    NEW:    { label: '新增 ＋',  cls: 'badge-new',    rowCls: 'row-new'    },
    ADD:    { label: '加碼 ↗',   cls: 'badge-add',    rowCls: 'row-add'    },
    REDUCE: { label: '減碼 ↘',   cls: 'badge-reduce', rowCls: 'row-reduce' },
    CLOSE:  { label: '出清 ✕',   cls: 'badge-close',  rowCls: 'row-close'  },
  };
  return map[action] || { label: action, cls: '', rowCls: '' };
}

// ─────────────────────────────────────────────
// Render functions
// ─────────────────────────────────────────────

function renderHeader(data) {
  const d = document.getElementById('report-date');
  if (d) d.textContent = data.date;
}

function renderFundSize(data) {
  document.getElementById('fund-size').textContent = fmt(data.fund_size_today, 2);
  document.getElementById('nav-value').textContent = data.nav ? fmt(data.nav, 2) : '—';
  document.getElementById('total-stocks').textContent = data.total_stocks ?? '—';
  document.getElementById('prev-date').textContent = data.prev_date ?? '—';
  document.getElementById('today-date').textContent = data.date ?? '—';

  const changeEl = document.getElementById('fund-size-change');
  const pct = data.fund_size_change_pct;
  if (pct != null) {
    changeEl.textContent = fmtPct(pct);
    changeEl.className = 'size-change ' + (pct >= 0 ? 'positive' : 'negative');
  }
}

function renderSummary(data) {
  const s = data.summary || {};
  document.getElementById('count-new').textContent    = s.new_positions    ?? 0;
  document.getElementById('count-add').textContent    = s.added_positions  ?? 0;
  document.getElementById('count-reduce').textContent = s.reduced_positions ?? 0;
  document.getElementById('count-close').textContent  = s.closed_positions ?? 0;
}

function renderChanges(data) {
  const changes = data.changes || [];
  const tbody = document.getElementById('changes-tbody');
  const badge = document.getElementById('changes-count');
  badge.textContent = `${changes.length} 檔異動`;

  tbody.innerHTML = changes.map(row => {
    const info = actionInfo(row.action);
    const shareSign = row.shares_change >= 0 ? '+' : '';
    const sharePctTxt = row.shares_change_pct != null
      ? `<span class="pct-value ${pctClass(row.shares_change_pct)}">${fmtPct(row.shares_change_pct)}</span>`
      : `<span class="neutral">—</span>`;

    const weightChangeTxt = row.weight_change != null
      ? `<span class="pct-value ${pctClass(row.weight_change)}">${fmtPct(row.weight_change)}</span>`
      : `<span class="neutral">—</span>`;

    // mini bar for current weight (max 12% = full bar for display)
    const barPct = Math.min((row.weight_today / 12) * 100, 100);

    return `<tr class="${info.rowCls}">
      <td class="col-stock">
        <a class="stock-link" href="${escHtml(tvUrl(row.code))}" target="_blank" rel="noopener noreferrer">
          <div class="stock-cell">
            <span class="stock-code">${escHtml(row.code)}</span>
            <span class="stock-name">${escHtml(row.name)}</span>
            <span class="tv-icon">↗</span>
          </div>
        </a>
      </td>
      <td>
        <span class="action-badge ${info.cls}">${info.label}</span>
      </td>
      <td class="col-number">
        <span class="${pctClass(row.shares_change)}">${shareSign}${fmtShares(row.shares_change)}</span>
        <br><span class="shares-value">→ ${fmtShares(row.shares_today)}</span>
      </td>
      <td class="col-number col-shares-pct-hide">
        ${sharePctTxt}
      </td>
      <td class="col-number">
        ${weightChangeTxt}
      </td>
      <td class="col-number">
        <span class="weight-bar"><span class="weight-bar-fill" style="width:${barPct}%"></span></span>
        <span class="pct-value">${fmt(row.weight_today)}%</span>
      </td>
    </tr>`;
  }).join('');
}

function renderUnchanged(data) {
  const rows = data.unchanged || [];
  const tbody = document.getElementById('unchanged-tbody');
  document.getElementById('unchanged-count').textContent = `${rows.length} 檔`;

  tbody.innerHTML = rows
    .sort((a, b) => b.weight_pct - a.weight_pct)
    .map(row => {
      const barPct = Math.min((row.weight_pct / 12) * 100, 100);
      return `<tr>
        <td class="col-stock">
          <a class="stock-link" href="${escHtml(tvUrl(row.code))}" target="_blank" rel="noopener noreferrer">
            <div class="stock-cell">
              <span class="stock-code">${escHtml(row.code)}</span>
              <span class="stock-name">${escHtml(row.name)}</span>
              <span class="tv-icon">↗</span>
            </div>
          </a>
        </td>
        <td class="col-number">
          <span class="neutral">${fmtShares(row.shares)}</span>
        </td>
        <td class="col-number">
          <span class="weight-bar"><span class="weight-bar-fill" style="width:${barPct}%"></span></span>
          <span class="pct-value">${fmt(row.weight_pct)}%</span>
        </td>
        <td>
          <span class="badge-unchanged">未異動</span>
        </td>
      </tr>`;
    }).join('');
}

function renderScrapeTime(data) {
  const el = document.getElementById('scrape-time');
  if (data.scrape_time) {
    el.textContent = `資料更新時間：${data.scrape_time}`;
  }
}

// ─────────────────────────────────────────────
// Collapsible section
// ─────────────────────────────────────────────

function initCollapsible() {
  const toggle = document.getElementById('unchanged-toggle');
  const wrap   = document.getElementById('unchanged-wrap');
  const icon   = document.getElementById('collapse-icon');

  toggle.addEventListener('click', () => {
    const collapsed = wrap.style.display === 'none';
    wrap.style.display = collapsed ? '' : 'none';
    icon.classList.toggle('collapsed', !collapsed);
  });

  toggle.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') toggle.click();
  });
}

// ─────────────────────────────────────────────
// Security helper
// ─────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ─────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────

async function loadDashboard() {
  const loadingEl = document.getElementById('loading');
  const errorEl   = document.getElementById('error-state');
  const mainEl    = document.getElementById('main-content');

  try {
    const res = await fetch(DATA_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    renderHeader(data);
    renderFundSize(data);
    renderSummary(data);
    renderChanges(data);
    renderUnchanged(data);
    renderScrapeTime(data);
    initCollapsible();

    loadingEl.style.display = 'none';
    mainEl.style.display = '';

  } catch (err) {
    loadingEl.style.display = 'none';
    errorEl.style.display = '';
    document.getElementById('error-message').textContent =
      `資料載入失敗：${err.message}。請確認資料檔案存在或使用 HTTP server 開啟。`;
    console.error('[ETF Tracker]', err);
  }
}

// ─────────────────────────────────────────────
// Force-refresh button
// ─────────────────────────────────────────────

function showToast(msg, type = 'info', durationMs = 5000) {
  const el = document.getElementById('toast');
  if (!el) return;
  el.textContent = msg;
  el.className = `toast toast--${type} toast--show`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.remove('toast--show'), durationMs);
}

async function triggerRefresh() {
  const btn   = document.getElementById('refresh-btn');
  const icon  = document.getElementById('refresh-icon');
  const label = document.getElementById('refresh-label');

  btn.disabled = true;
  icon.classList.add('spin');
  label.textContent = '更新中…';

  try {
    const res = await fetch('/api/refresh', { method: 'POST' });
    const data = await res.json();

    if (res.ok && data.success) {
      showToast('✓ 已觸發更新！爬蟲執行中，約 5-10 分鐘後資料更新並自動部署。', 'success', 8000);
    } else if (data.fallback_url) {
      // GITHUB_TOKEN not configured — fall back to manual trigger
      showToast('⚠ 尚未設定 GITHUB_TOKEN，請至 GitHub Actions 手動執行。', 'warn', 10000);
      window.open(data.fallback_url, '_blank', 'noopener');
    } else {
      showToast(`⚠ 觸發失敗：${data.error || res.status}`, 'error');
    }
  } catch (err) {
    // /api/refresh not reachable (e.g. local file open) — open GH Actions directly
    window.open('https://github.com/kevin12596/00981a/actions/workflows/daily_scrape.yml', '_blank', 'noopener');
  } finally {
    // Re-enable button after 30 s to prevent spam
    setTimeout(() => {
      btn.disabled = false;
      icon.classList.remove('spin');
      label.textContent = '更新資料';
    }, 30_000);
  }
}

function initRefreshButton() {
  const btn = document.getElementById('refresh-btn');
  if (btn) btn.addEventListener('click', triggerRefresh);
}

// ─────────────────────────────────────────────
// Weight History Chart
// ─────────────────────────────────────────────

const CHART_PALETTE = [
  '#4FC3F7','#81C784','#FFB74D','#F06292','#CE93D8',
  '#80DEEA','#FFCC02','#FF8A65','#A5D6A7','#90CAF9',
  '#FFAB91','#B39DDB','#80CBC4','#EF9A9A','#FFF176',
  '#4DB6AC','#DCE775','#F48FB1','#E6EE9C','#80DEEA',
];

let weightChart   = null;
let historyData   = null;
let activeTopN    = 10;

function buildDatasets(history, topN) {
  return history.stocks.map((stock, i) => ({
    label:           `${stock.code} ${stock.name}`,
    data:            stock.weights,
    borderColor:     CHART_PALETTE[i % CHART_PALETTE.length],
    backgroundColor: 'transparent',
    borderWidth:     (topN === 0 || i < topN) ? 2 : 1.5,
    pointRadius:     history.dates.length <= 10 ? 4 : 2,
    pointHoverRadius: 6,
    tension:         0.3,
    hidden:          topN > 0 && i >= topN,
    spanGaps:        true,
  }));
}

function renderWeightChart(history, topN) {
  const ctx = document.getElementById('weight-chart');
  if (!ctx) return;

  const labels = history.dates.map(d => d.slice(5).replace('-', '/'));

  if (weightChart) { weightChart.destroy(); weightChart = null; }

  weightChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: buildDatasets(history, topN) },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 350 },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#8b949e',
            usePointStyle: true,
            pointStyle: 'circle',
            padding: 14,
            font: { size: 11, family: "'Segoe UI','PingFang TC',sans-serif" },
          },
        },
        tooltip: {
          backgroundColor: '#161b22',
          borderColor: '#30363d',
          borderWidth: 1,
          titleColor: '#e6edf3',
          bodyColor: '#8b949e',
          padding: 10,
          callbacks: {
            title: items => history.dates[items[0].dataIndex],
            label: item => {
              const v = item.parsed.y;
              if (v == null) return null;
              return ` ${item.dataset.label}: ${v.toFixed(2)}%`;
            },
          },
        },
      },
      scales: {
        x: {
          grid:  { color: 'rgba(48,54,61,0.5)' },
          ticks: { color: '#6e7681', font: { size: 11 } },
        },
        y: {
          grid:  { color: 'rgba(48,54,61,0.5)' },
          ticks: { color: '#6e7681', font: { size: 11 }, callback: v => v + '%' },
          title: { display: true, text: '持股占比 (%)', color: '#6e7681', font: { size: 11 } },
        },
      },
    },
  });
}

async function loadChart() {
  try {
    const res = await fetch(HISTORY_URL);
    if (!res.ok) return;
    historyData = await res.json();
    if (!historyData.dates || historyData.dates.length < 1) return;
    renderWeightChart(historyData, activeTopN);
  } catch (e) {
    console.warn('[ETF Chart] Failed to load history:', e);
  }
}

function initChartFilter() {
  document.querySelectorAll('#chart-filter .pill').forEach(pill => {
    pill.addEventListener('click', () => {
      document.querySelectorAll('#chart-filter .pill').forEach(p => p.classList.remove('pill--active'));
      pill.classList.add('pill--active');
      activeTopN = parseInt(pill.dataset.n, 10);
      if (historyData) renderWeightChart(historyData, activeTopN);
    });
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadDashboard();
  initRefreshButton();
  loadChart();
  initChartFilter();
});
