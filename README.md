# 00981A 主動統一台股增長 — 持股追蹤 Dashboard

每日自動追蹤 **00981A（主動統一台股增長 ETF）** 的持股異動，以深色主題 Dashboard 呈現加減碼明細。

🔗 **Live Dashboard**: [https://00981a.vercel.app](https://00981a.vercel.app)

---

## 功能

| 功能 | 說明 |
|------|------|
| 新增/加碼/減碼/出清 | 自動分類每日持股變動 |
| 基金規模追蹤 | 顯示基金規模與淨值，較昨日漲跌 % |
| 操作明細表格 | 股數變動、股數%、權重變動、目前權重 |
| 未異動持股 | 可收合的未變動持股列表 |
| 響應式設計 | 支援桌機與手機瀏覽 |

---

## 專案架構

```
00981a/
├── public/                # Vercel 靜態網站
│   ├── index.html         # Dashboard 主頁
│   ├── style.css          # 深色主題樣式
│   ├── app.js             # 前端邏輯
│   └── data/
│       ├── latest_diff.json   # 最新比對結果（每日更新）
│       └── YYYY-MM-DD.json    # 每日快照
│
├── scraper/               # Python 爬蟲（本機或 GitHub Actions 執行）
│   ├── config.py          # 設定檔
│   ├── scraper.py         # Playwright 爬蟲
│   ├── comparator.py      # 持股比對邏輯
│   └── main.py            # 主入口
│
├── .github/workflows/
│   └── daily_scrape.yml   # 每日 18:30 自動執行
│
├── requirements.txt
└── vercel.json
```

---

## 本機執行爬蟲

```bash
# 1. 建立虛擬環境
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. 安裝套件
pip install -r requirements.txt
playwright install chromium

# 3. 執行爬蟲（抓取 + 比對 + 輸出 latest_diff.json）
python scraper/main.py

# 乾跑模式（不寫檔，只看輸出）
python scraper/main.py --dry-run
```

執行後會更新 `public/data/latest_diff.json`，推送到 GitHub 後 Vercel 自動重新部署。

---

## 自動化排程

**GitHub Actions**（推薦）：`daily_scrape.yml` 每個工作日 18:30 自動執行並提交資料。

**Windows 工作排程器**（本機備用）：
1. 程式：`C:\path\to\.venv\Scripts\python.exe`
2. 引數：`scraper/main.py`
3. 起始位置：`C:\path\to\00981a`
4. 時間：每日 18:30，週一至週五

---

## 資料格式

**`latest_diff.json`** — 每日比對結果

```json
{
  "date": "2026-03-18",
  "prev_date": "2026-03-17",
  "fund_size_today": 414.96,
  "fund_size_change_pct": -0.17,
  "summary": { "new_positions": 1, "added_positions": 3, ... },
  "changes": [ { "code": "2330", "action": "ADD", ... } ],
  "unchanged": [ ... ]
}
```

---

## 免責聲明

資料來源為統一投信 / ezmoney，僅供參考。投資有風險，請自行評估。
