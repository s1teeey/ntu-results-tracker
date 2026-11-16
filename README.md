# NTU Results Tracker

追蹤臺大碩士班甄試（116 學年度第 2 梯次，11/19 放榜）。榜單一出現，網頁會跳出「已放榜」視窗，並顯示每位一階考生的錄取狀況與備取遞補預估。

## 架構

```
雲端排程工作 ──(tracker/run.py)──▶ 每 10 秒檢查教務處 ──▶ 把 data/*.json 推進這個 repo
                                                              │
GitHub Pages ◀─────────────── index.html 每 15 秒讀 data/*.json ◀┘   (手機、電腦開著就會自動更新)
```

| 路徑 | 作用 |
|---|---|
| `index.html` | 網頁本體（單檔，淺色，四個分頁：總覽／名冊／歷年／紀錄；頂欄與「我的結果」列固定；放榜彈窗）。可加入手機主畫面。 |
| `data/status.json` | 追蹤狀態（`phase`: waiting / watching / found / timeout、`lastBeatAt`、`checks`、`foundAt`、`url`、`log`）。 |
| `data/roster.json` | 一階名冊與人與人的對應（商研所 7010、國企 7070、財金 7040/7050/7060）。 |
| `data/outcomes.json` | 放榜後由程式產生：五個組別的正取／備取名單與核對結果。 |
| `tracker/run.py` | 追蹤主程式：檢查、定時推送狀態、找到後下載榜單、解析、推送結果。 |
| `tracker/extract_all.py` | 解析榜單文字並核對（五組別都在、人數與榜單合計一致、名冊准考證對得上）。 |

## 啟用 GitHub Pages

Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/ (root)`。
免費方案只支援公開 repo；私人 repo 需要付費方案。

## 執行追蹤程式

```bash
python3 tracker/run.py --repo . --batch 2 --deadline <結束時間 epoch> --hb 300
# 乾跑（不推送）: 加 --no-push；用指定 PDF 測試: 加 --test-url <pdf 網址>
```

需要：可推送的 clone、`curl`、`pdftotext`、`python3`。學校網站憑證只簽 `www.aca.ntu.edu.tw`，請一律用 www 網域。

## 資料來源與限制

- 歷年遞補：商研所、國企為各年「備取序」（遞補到備取第幾順位）；財金為官方第一輪遞補名單（下限）。113 年財金榜單格式抓不到，缺漏。
- 一階名冊中「商研所與國企是同一人」是用遮罩姓名（姓＋末字）加准考證順序一致性推得，不是官方資料；與財金的對應僅標為「可能」。
- 檔名規律涵蓋 111–116 學年度；若學校改命名，只靠索引頁那一路偵測。

## 隱私

`data/roster.json` 含其他考生的遮罩姓名與准考證號碼（來自學校公告的口試名單）以及上述推測。公開此 repo 前請自行評估。
