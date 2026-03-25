# 00981A 主動統一台股增長 ETF 持股追蹤系統

> 自動化追蹤 00981A 每日持股異動的 Web Dashboard，支援桌機與手機瀏覽器。

**線上網址**：https://00981a.vercel.app
**GitHub Repo**：https://github.com/kevin12596/00981a
**資料來源**：統一投信 ezmoney（每個交易日 18:30 自動更新）

---

## 功能一覽

| 功能 | 說明 |
|------|------|
| 每日持股異動日報 | 自動分類新增 / 加碼 / 減碼 / 出清 |
| 摘要卡片 | 一眼看出當日新增/加碼/減碼/出清各幾檔 |
| 操作明細表格 | 股數變動、股數%、權重變動、目前權重 mini bar |
| 未異動持股 | 可收合的完整持股列表 |
| 權重走勢圖 | 所有持股歷史權重折線圖，可切換前 5 / 10 / 15 / 全部 |
| 點擊開啟技術分析 | 點選個股代號或名稱 → 直接開啟 TradingView 全圖 |
| 強制更新按鈕 | 從網頁手動觸發 GitHub Actions 爬蟲，無需開電腦 |
| 全自動排程 | 每個交易日 18:30 自動爬取並部署，完全免人工 |

---

## 目錄結構

```
00981a/
├── public/                         # 前端靜態網頁（Vercel 部署此目錄）
│   ├── index.html                  # Dashboard 主頁
│   ├── style.css                   # 深色主題樣式
│   ├── app.js                      # 前端邏輯（渲染 + Chart.js 走勢圖）
│   └── data/                       # 每日資料（由 GitHub Actions 自動寫入）
│       ├── 2026-03-19.json         # 每日完整持股快照（格式見下）
│       ├── 2026-03-20.json
│       ├── latest_diff.json        # 最新比對結果（Dashboard 讀取此檔）
│       └── history.json            # 所有日期走勢彙整（圖表讀取此檔）
│
├── scraper/                        # Python 爬蟲（在 GitHub Actions 執行）
│   ├── main.py                     # 主入口，依序呼叫以下三個模組
│   ├── scraper.py                  # 爬蟲邏輯（Playwright + 文字提取雙策略）
│   ├── comparator.py               # 持股比對（新增/加碼/減碼/出清判定）
│   ├── history.py                  # 彙整歷史走勢至 history.json
│   └── config.py                   # 設定檔（URL、閾值、路徑）
│
├── api/
│   └── refresh.js                  # Vercel Serverless Function（觸發 GitHub Actions）
│
├── .github/
│   └── workflows/
│       └── daily_scrape.yml        # GitHub Actions 排程定義
│
├── requirements.txt                # Python 套件清單
├── vercel.json                     # Vercel 部署設定
└── README.md                       # 本文件
```

---

## 系統架構與資料流

```
[GitHub Actions 排程]
每個交易日 18:30（台灣時間）自動觸發
      │
      ▼
[scraper/main.py] — 依序執行三步驟：
  Step 1  scraper.py    Playwright 載入 ezmoney 頁面
                        → XHR 攔截 / 文字提取（雙策略）
                        → 寫出 public/data/YYYY-MM-DD.json

  Step 2  comparator.py 與前一交易日 JSON 比對
                        → 判定 NEW / ADD / REDUCE / CLOSE
                        → 寫出 public/data/latest_diff.json

  Step 3  history.py    掃描所有 YYYY-MM-DD.json
                        → 彙整寫出 public/data/history.json

  git add public/data/ → commit → git push
      │
      ▼
[Vercel] 偵測到 push → 自動重新部署 public/ 目錄
  → Dashboard 即時反映最新資料
```

---

## 資料格式說明

### [`public/data/YYYY-MM-DD.json`](public/data/) — 每日完整持股快照

```json
{
  "date": "2026-03-20",
  "fund_code": "00981A",
  "fund_name": "主動統一台股增長",
  "nav": null,
  "fund_size_billion": null,
  "total_stocks": 53,
  "scrape_time": "2026-03-20T19:03:00",
  "holdings": [
    { "code": "2330", "name": "台積電", "shares": 4107000, "weight_pct": 8.64 },
    { "code": "2383", "name": "台光電", "shares": 2317000, "weight_pct": 7.27 }
  ]
}
```

> `nav` 與 `fund_size_billion` 目前為 `null`（ezmoney 此欄位尚未爬到），不影響核心比對功能。

### [`public/data/latest_diff.json`](public/data/latest_diff.json) — 最新比對結果

```json
{
  "date": "2026-03-20",
  "prev_date": "2026-03-19",
  "fund_size_today": null,
  "fund_size_yesterday": null,
  "fund_size_change_pct": null,
  "nav": null,
  "total_stocks": 53,
  "scrape_time": "2026-03-20T19:03:00",
  "summary": {
    "new_positions": 1,
    "added_positions": 6,
    "reduced_positions": 3,
    "closed_positions": 2
  },
  "changes": [
    {
      "code": "3443", "name": "創意",
      "action": "NEW",
      "shares_today": 245000, "shares_yesterday": 0,
      "shares_change": 245000, "shares_change_pct": null,
      "weight_today": 0.69, "weight_yesterday": 0.0, "weight_change": 0.69
    }
  ],
  "unchanged": [ ... ]
}
```

**action 判定規則（定義於 [`scraper/config.py`](scraper/config.py)）：**

| action | 條件 |
|--------|------|
| `NEW` | 昨日無持股 → 今日新進 |
| `ADD` | 今日股數 > 昨日股數，且變動幅度 > 0.10% |
| `REDUCE` | 今日股數 < 昨日股數，且變動幅度 > 0.10% |
| `CLOSE` | 股數歸零，或股數變動 ≤ −99%（視同出清） |
| `UNCHANGED` | 變動幅度 ≤ 0.10%，不顯示於異動表格 |

### [`public/data/history.json`](public/data/history.json) — 走勢圖資料

```json
{
  "updated": "2026-03-20",
  "dates": ["2026-03-19", "2026-03-20"],
  "stocks": [
    { "code": "2330", "name": "台積電", "weights": [8.66, 8.64] },
    { "code": "2383", "name": "台光電", "weights": [7.69, 7.27] }
  ]
}
```

- `stocks` 依最新日期權重由高到低排序
- 股票若某日不在持股中，對應 `weights` 位置為 `null`（圖表以 `spanGaps: true` 跳過）

---

## 本地開發

### 1. Clone 專案

```bash
git clone https://github.com/kevin12596/00981a.git
cd 00981a
```

### 2. 建立 Python 虛擬環境並安裝套件

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
playwright install chromium
```

### 3. 手動執行爬蟲

```bash
# 正常執行（抓取 + 比對 + 寫出 JSON）
python scraper/main.py

# 乾跑模式（不寫檔，只看 log 輸出）
python scraper/main.py --dry-run
```

執行後會更新 `public/data/` 下的三個 JSON 檔。

### 4. 本地預覽前端

> ⚠️ 不可直接雙擊 `index.html`，`fetch()` 需要 HTTP 協定才能讀取本地 JSON。

```bash
# 方法一：Python 內建 HTTP Server
cd public
python -m http.server 8080
# 開啟瀏覽器 → http://localhost:8080
```

或在 VS Code 安裝「Live Server」擴充套件，右鍵點選 `public/index.html` → Open with Live Server。

---

## 部署設定

### Vercel（前端 + Serverless Function）

- **Framework**：None（純靜態，`vercel.json` 指定 `outputDirectory: "public"`）
- **Serverless Function**：[`api/refresh.js`](api/refresh.js) — 供「更新資料」按鈕呼叫

**必要環境變數（在 Vercel Dashboard 設定）：**

| 變數名稱 | 用途 |
|----------|------|
| `GITHUB_TOKEN` | 讓 `/api/refresh` 能觸發 GitHub Actions workflow |

**CLI 設定方式：**
```bash
# 需先安裝 Vercel CLI：npm i -g vercel
vercel env add GITHUB_TOKEN production
# 輸入 GitHub Personal Access Token（需有 repo + workflow scope）
vercel --prod   # 重新部署以套用新環境變數
```

### GitHub Actions（爬蟲排程）

檔案：[`.github/workflows/daily_scrape.yml`](.github/workflows/daily_scrape.yml)

| 項目 | 說明 |
|------|------|
| 自動觸發 | 每個工作日 UTC 10:30（= 台灣時間 18:30） |
| 手動觸發 | GitHub → Actions → Daily ETF Scrape → Run workflow |
| Timeout | 15 分鐘 |
| 所需 repo 權限 | `contents: write`（自動 commit data 檔案） |
| 執行時間 | 約 45 秒（含 Playwright browser 安裝） |

---

## 爬蟲策略

資料來源為 ezmoney（動態渲染頁面），採**雙策略**確保穩定性：

| 優先順序 | 策略 | 說明 |
|----------|------|------|
| 1st | **XHR 攔截** | Playwright 攔截頁面發出的所有 JSON API 回應，從中尋找持股結構 |
| 2nd | **文字提取** | 從渲染後的 HTML 全文以 Regex 萃取「股票代號 + 股數 + 權重」組合 |

每個策略重試 2 次，間隔 30 秒。偵測到 0 筆資料時自動切換到下一策略。

Debug 用：爬蟲執行時會將當日 ezmoney 頁面 HTML 儲存至 `public/data/_debug_ezmoney.html`，供分析頁面結構用。

---

## 常見問題

**Q：為什麼基金規模和 NAV 顯示「—」？**
ezmoney 的規模與淨值位於不同的頁面區塊，目前的文字提取策略尚未覆蓋。這是已知的待優化項目，不影響核心持股比對。

**Q：爬蟲失敗怎麼辦？**
1. 前往 [GitHub Actions 頁面](https://github.com/kevin12596/00981a/actions) 查看執行 log
2. 常見原因：ezmoney 頁面載入超時或頁面結構異動
3. 可手動點擊 Run workflow 重試
4. 若持續失敗，需檢查 [`scraper/scraper.py`](scraper/scraper.py) 的解析邏輯

**Q：如何手動補充歷史資料？**
將正確格式的 JSON 放入 `public/data/YYYY-MM-DD.json`，再執行：
```bash
python scraper/history.py
```
重新產生 `history.json` 後 commit 並 push 即可，Vercel 自動部署。

**Q：如何修改加減碼判定閾值？**
編輯 [`scraper/config.py`](scraper/config.py)：
```python
MIN_CHANGE_PCT  = 0.10   # 變動低於此值視為未異動（預設 0.10%）
CLOSE_THRESHOLD = -99.0  # 股數變動低於此值視為出清（預設 -99%）
```

**Q：如何擴展支援其他 ETF？**
修改 [`scraper/config.py`](scraper/config.py)：
```python
FUND_CODE = "00981A"           # 改為目標 ETF 代號
FUND_NAME = "主動統一台股增長"
EZ_CODE   = "49YTW"            # ezmoney 頁面 URL 中的 fundCode 參數
```

---

## 技術選型

| 層次 | 技術 | 說明 |
|------|------|------|
| 前端 | HTML5 + CSS3 + Vanilla JS | 無框架依賴 |
| 圖表 | Chart.js 4（CDN） | 折線圖，深色主題 |
| 技術分析連結 | TradingView | 點擊股票代號直接跳轉 |
| 後端爬蟲 | Python 3.12 + Playwright | 動態頁面自動化 |
| 排程 | GitHub Actions cron | 免費、無需自架伺服器 |
| 部署 | Vercel | 靜態托管 + Serverless Function |
| 資料儲存 | JSON 檔案（git 管理） | 輕量、可審計、免資料庫 |

---

## 後續優化建議

- [ ] 補全 NAV / 基金規模的爬取邏輯
- [ ] 支援台灣國定假日（現行只排除週六日）
- [ ] 每日自動發送 LINE / Email 摘要通知
- [ ] 法人籌碼整合（對異動個股補充外資/投信買賣超）
- [ ] 多 ETF 同時追蹤支援

---

## 免責聲明

本系統資料來源為統一投信及 ezmoney，僅供個人投資研究參考。
**投資有風險，本系統不構成任何投資建議，請自行評估風險。**
