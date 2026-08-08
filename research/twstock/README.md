# 智邦（2345）研究 pipeline

跟這個 repo 的公開狀態頁完全獨立，只是借地方放。不影響 GitHub Pages 的內容。

## 這在做什麼

研究主體是**智邦 2345**（資料中心白牌交換器）。整套設計回答兩個問題：

1. **緯穎的月營收動能，是不是領先智邦？**
   假設 AI 資料中心是「運算先進場、網路後擴充」，那麼整櫃代工廠（緯穎／廣達／緯創）
   的營收加速度，應該領先交換器廠 1~3 個月。
   這是最便宜也最該先做的檢驗——它有機會直接推翻整個想法，省下後面所有建模工作。

2. **智邦在風險調整後，到底有沒有優勢？**
   不是比累積漲幅，是比 Sharpe 和「波動對齊後的報酬」。

## 為什麼是這個標的組合

台股講的「網通族群」混了三群完全不同的公司，只有一群跟 AI 論點有關：

| 分群 | 標的 | 跟 AI 資料中心的關係 |
|---|---|---|
| 研究主體 | 智邦 2345 | 白牌交換器，scale-out 乙太網路層 |
| 領先指標候選 | 緯穎 6669、廣達 2382、緯創 3231 | 整櫃代工，AI capex 的高 beta 放大器 |
| **安慰劑對照組** | 中磊 5388、智易 3596、明泰 3380 | 消費性 CPE，**幾乎無關** |
| 延伸觀察 | 光聖 6442、聯亞 3081、華星光 4979 | 光通訊，傳輸瓶頸的物理解方 |
| 基準 | 元大台灣50 0050 | 算超額報酬用 |

**對照組是整套設計的關鍵。** 如果訊號在 CPE 上一樣有效，那抓到的是台股整體風險偏好，
不是 AI 供應鏈的傳導——這個檢驗很便宜，但能擋掉大量的自我欺騙。

## 前置需求

### 1. 網路政策

**這一步不做，什麼都跑不了。** Claude Code 遠端環境預設只放行開發用網域
（PyPI、GitHub），台股資料源全部被擋（gateway 回 403）。

到環境設定的允許網域清單加入：

```
api.finmindtrade.com      # 主要資料源
finmindtrade.com          # 註冊 / 取 token
www.twse.com.tw           # 證交所盤後資料
openapi.twse.com.tw       # 證交所 OpenAPI
mops.twse.com.tw          # 公開資訊觀測站
mopsov.twse.com.tw        # 同上，備援站台
www.tpex.org.tw           # 櫃買中心
www.tdcc.com.tw           # 集保股權分散表
query1.finance.yahoo.com  # yfinance 備援
query2.finance.yahoo.com
fc.yahoo.com
```

前六個是必要的。**改完要開新 session 才生效**（容器是用舊政策啟動的）。

診斷：`curl -sS "$HTTPS_PROXY/__agentproxy/status"`，被擋時 `recentRelayFailures`
會出現 `connect_rejected` / 403。

### 2. FinMind token

到 <https://finmindtrade.com> 註冊，免費版約 600 requests/hr。

Token 設成環境變數，**不要寫進程式碼或貼進對話**：

```bash
export FINMIND_TOKEN=<your-token>
```

## 執行

```bash
pip install -r requirements.txt

python run.py --check      # 先確認連線與 token 就緒
python run.py              # 兩項都跑
python run.py --leadlag    # 只跑領先落後檢驗
python run.py --baseline   # 只跑基準比較
```

結果寫到 `output/`，原始資料快取在 `.cache/`（兩者都已 gitignore）。
重跑不會重新打 API，要強制更新就把 `.cache/` 刪掉。

## 檔案

| 檔案 | 內容 |
|---|---|
| `config.py` | 標的分群、期間、交易成本、制度性斷點 |
| `datasource.py` | FinMind 抓取、磁碟快取、除權息還原、月營收公布日對齊 |
| `leadlag.py` | 交叉相關掃描 + 有效樣本數修正 + 安慰劑檢驗 |
| `baseline.py` | 風險報酬指標、波動對齊比較、剝除 beta 的 alpha |
| `run.py` | 執行入口與報表輸出 |

## 方法上刻意處理的幾個坑

**除權息還原**：台股殖利率高，不還原會在除息日產生假的 -5% 跳空。
優先用 FinMind 的還原股價；那是付費資料集，拿不到就用除權息結果表的
`after_price / before_price` 自己向後還原。兩者都失敗會印警告，不會靜默地給你錯的數字。

**月營收的前視偏誤**：台股規定每月 10 日前公布上月營收。所以 M 月營收最早
M+1 月 10 日才可用。程式用 `avail_date` 對齊，不是 `revenue_month`——
用後者對齊等於拿還沒公布的資料去解釋股價。

**自我相關造成的假顯著**：YoY 序列自我相關極強，兩條都在趨勢向上的序列
隨便算相關都很高。所以（a）主要判讀看加速度而非水準值，（b）用
Bartlett–Quenouille 有效樣本數修正把 n 打折後再算 t 統計量。

**交易成本**：手續費 0.1425%（預設打 6 折）+ 賣出證交稅 0.3%，
來回約 0.47%。買進持有基準已扣掉。任何主動策略要有意義，
預測邊際必須明顯大於這個數。

**共同期間**：緯穎 2019 才上市，比較時取所有標的的交集期間，
否則不同上市時間會讓風險指標失真。

## 已知限制

- **這套程式碼還沒有對實際 API 跑過**（撰寫時網路政策擋住資料源）。
  第一次執行時 FinMind 的欄位名稱若有變動，可能需要微調 `datasource.py`。
  先跑 `--check` 確認連線，再跑 `--leadlag`。
- `TaiwanStockPriceAdj` 是付費資料集，免費帳號會走自行還原的路徑。
- 這裡算的全部是已實現的歷史統計，**不是預測，也不是投資建議**。

## 接下來可以加的

按價值排序，但**建議先看完領先落後的結果再決定要不要往下做**——
如果第一個檢驗就否定了供應鏈傳導的假設，加再多特徵也是白費：

1. 三大法人買賣超（`datasource.get_institutional` 已經寫好，還沒接進分析）
2. 營收公布後的漂移效應（post-announcement drift）
3. 毛利率——對智邦這種高毛利標的，季報毛利率可能比月營收更有訊息量
4. 集保大戶持股比率變化（週資料）
