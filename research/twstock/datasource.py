"""FinMind 資料抓取層，含磁碟快取與除權息還原。

設計重點：
1. 價格一律還原除權息。台股殖利率高，不還原會在除息日產生假的 -5% 跳空，
   任何動能／報酬類的特徵都會被汙染。
2. 月營收用「公布日」對齊，不是「營收月份」。這是台股研究最常見的前視偏誤。
3. 全部結果落地成 CSV 快取。FinMind 免費版有流量限制（約 600 requests/hr），
   反覆調參時不該每次都重抓。
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from config import END_DATE, REVENUE_PUBLISH_DAY, START_DATE

API_URL = "https://api.finmindtrade.com/api/v4/data"
CACHE_DIR = Path(__file__).parent / ".cache"

BLOCKED_HOSTS_HINT = """
無法連到 FinMind (api.finmindtrade.com)。

如果這是 Claude Code 的遠端 session，最可能的原因是環境的網路政策擋掉了這個網域。
請在環境設定的允許網域清單裡加入：

    api.finmindtrade.com
    finmindtrade.com
    www.twse.com.tw
    openapi.twse.com.tw
    mops.twse.com.tw
    mopsov.twse.com.tw

改完網路政策後需要開新的 session 才會生效。

診斷指令：
    curl -sS "$HTTPS_PROXY/__agentproxy/status"
被政策擋掉時 recentRelayFailures 會出現 connect_rejected / 403。
"""


class DataUnavailable(RuntimeError):
    """資料抓不到，且已經沒有可用的備援路徑。"""


def _token() -> str:
    tok = os.environ.get("FINMIND_TOKEN", "").strip()
    if not tok:
        print(
            "[warn] 沒有設定 FINMIND_TOKEN，將以匿名額度呼叫（限制很緊，容易中途失敗）。\n"
            "       到 https://finmindtrade.com 註冊後把 token 設成環境變數 FINMIND_TOKEN。",
            file=sys.stderr,
        )
    return tok


def _cache_path(dataset: str, stock_id: str, start: str, end: str | None) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    tag = f"{dataset}__{stock_id}__{start}__{end or 'latest'}.csv"
    return CACHE_DIR / tag


def fetch(
    dataset: str,
    stock_id: str,
    start_date: str = START_DATE,
    end_date: str | None = END_DATE,
    use_cache: bool = True,
    max_retries: int = 3,
) -> pd.DataFrame:
    """打一次 FinMind，帶磁碟快取與退避重試。

    回傳空的 DataFrame 代表「查得到但沒有資料」（例如標的當時還沒上市）；
    連線失敗或權限不足則丟 DataUnavailable。
    """
    path = _cache_path(dataset, stock_id, start_date, end_date)
    if use_cache and path.exists():
        return pd.read_csv(path)

    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
    }
    if end_date:
        params["end_date"] = end_date
    tok = _token()
    if tok:
        params["token"] = tok

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(API_URL, params=params, timeout=45)
        except requests.exceptions.RequestException as exc:
            last_err = exc
            if attempt == max_retries - 1:
                raise DataUnavailable(f"{BLOCKED_HOSTS_HINT}\n原始錯誤：{exc}") from exc
            time.sleep(2 ** (attempt + 1))
            continue

        if resp.status_code == 402:
            raise DataUnavailable(
                f"dataset={dataset} 需要 FinMind 付費方案（HTTP 402）。"
                "請改用免費資料集，或升級方案。"
            )
        if resp.status_code == 429:
            # 免費版流量用完，退避後再試
            time.sleep(10 * (attempt + 1))
            last_err = RuntimeError("HTTP 429 rate limited")
            continue
        if resp.status_code != 200:
            last_err = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if attempt == max_retries - 1:
                raise DataUnavailable(str(last_err))
            time.sleep(2 ** (attempt + 1))
            continue

        payload = resp.json()
        if payload.get("status") != 200:
            raise DataUnavailable(
                f"FinMind 回傳錯誤 dataset={dataset} stock={stock_id}: {payload.get('msg')}"
            )

        df = pd.DataFrame(payload.get("data", []))
        if use_cache:
            df.to_csv(path, index=False)
        return df

    raise DataUnavailable(f"重試 {max_retries} 次後仍失敗：{last_err}")


# --- 價格 -----------------------------------------------------------------


def _reconstruct_adjustment(raw: pd.DataFrame, stock_id: str) -> pd.DataFrame:
    """用除權息結果表反推還原因子。

    TaiwanStockPriceAdj 屬於付費資料集，免費帳號拿不到，所以這裡用
    TaiwanStockDividendResult 的 before_price / after_price 自己還原。

    做法是標準的向後還原（back-adjust）：某個除權息日之前的所有價格，
    乘上該次的 after/before 比率，並且往前累乘。這樣最新價格保持原值，
    歷史價格被調降，報酬率序列才連續。
    """
    try:
        div = fetch("TaiwanStockDividendResult", stock_id)
    except DataUnavailable:
        div = pd.DataFrame()

    out = raw.copy()
    price_cols = [c for c in ("open", "max", "min", "close") if c in out.columns]

    if div.empty or not {"before_price", "after_price", "date"} <= set(div.columns):
        print(
            f"[warn] {stock_id} 取不到除權息資料，價格「未」還原。"
            "報酬率會在除息日出現假跳空，動能類特徵不可信。",
            file=sys.stderr,
        )
        out["adj_factor"] = 1.0
        for c in price_cols:
            out[f"adj_{c}"] = out[c]
        return out

    div = div.copy()
    div["date"] = pd.to_datetime(div["date"])
    div = div[(div["before_price"] > 0) & (div["after_price"] > 0)]
    div = div.sort_values("date")
    div["factor"] = div["after_price"] / div["before_price"]

    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)

    # 對每個交易日，累乘所有「在它之後」發生的除權息因子
    factors = pd.Series(1.0, index=out.index)
    for _, row in div.iloc[::-1].iterrows():
        mask = out["date"] < row["date"]
        factors[mask] *= row["factor"]

    out["adj_factor"] = factors
    for c in price_cols:
        out[f"adj_{c}"] = out[c] * factors
    return out


def get_prices(stock_id: str, use_cache: bool = True) -> pd.DataFrame:
    """日線，含還原後的收盤價 adj_close 與報酬率 ret。

    優先用 FinMind 的還原股價資料集；拿不到就用除權息表自己還原。
    """
    adj = pd.DataFrame()
    try:
        adj = fetch("TaiwanStockPriceAdj", stock_id, use_cache=use_cache)
    except DataUnavailable as exc:
        print(f"[info] {stock_id} 還原股價資料集不可用（{exc}），改用自行還原。", file=sys.stderr)

    if not adj.empty and "close" in adj.columns:
        df = adj.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        df["adj_close"] = df["close"]
        df["adj_factor"] = 1.0
    else:
        raw = fetch("TaiwanStockPrice", stock_id, use_cache=use_cache)
        if raw.empty:
            raise DataUnavailable(f"{stock_id} 抓不到任何價格資料")
        df = _reconstruct_adjustment(raw, stock_id)

    df = df[df["adj_close"] > 0].reset_index(drop=True)
    df["ret"] = df["adj_close"].pct_change()
    df["stock_id"] = str(stock_id)
    return df[["date", "stock_id", "close", "adj_close", "adj_factor", "ret", "Trading_money"]
              if "Trading_money" in df.columns
              else ["date", "stock_id", "close", "adj_close", "adj_factor", "ret"]]


# --- 月營收 ---------------------------------------------------------------


def get_monthly_revenue(stock_id: str, use_cache: bool = True) -> pd.DataFrame:
    """月營收，附上「可用日期」avail_date 與 YoY／加速度。

    avail_date 是這筆資料最早可以進入模型的日子：營收月份的次月 10 日。
    所有回測都必須用 avail_date 對齊，用 revenue_month 對齊就是前視偏誤 ——
    你會拿 3 月營收去解釋 3 月的股價，但 3 月營收要 4/10 才公布。
    """
    df = fetch("TaiwanStockMonthRevenue", stock_id, use_cache=use_cache)
    if df.empty:
        raise DataUnavailable(f"{stock_id} 抓不到月營收")

    df = df.copy()
    if "revenue_year" not in df.columns or "revenue_month" not in df.columns:
        raise DataUnavailable(f"{stock_id} 月營收欄位不符預期：{list(df.columns)}")

    df["period"] = pd.to_datetime(
        df["revenue_year"].astype(int).astype(str)
        + "-"
        + df["revenue_month"].astype(int).astype(str).str.zfill(2)
        + "-01"
    )
    df = df.sort_values("period").drop_duplicates("period").reset_index(drop=True)

    # 次月 10 日公布
    df["avail_date"] = (
        df["period"] + pd.offsets.MonthBegin(1) + pd.Timedelta(days=REVENUE_PUBLISH_DAY - 1)
    )

    df["revenue"] = pd.to_numeric(df["revenue"], errors="coerce")
    df["yoy"] = df["revenue"].pct_change(12)
    df["mom"] = df["revenue"].pct_change(1)

    # 加速度：本月 YoY 相對前三個月 YoY 平均的變化。
    # 用「變化率的變化」而不是絕對成長率，是因為市場定價的是預期的修正，
    # 不是成長率本身 —— 高成長已經在價格裡了。
    df["yoy_accel"] = df["yoy"] - df["yoy"].shift(1).rolling(3).mean()

    df["stock_id"] = str(stock_id)
    return df[
        ["stock_id", "period", "avail_date", "revenue", "yoy", "mom", "yoy_accel"]
    ].dropna(subset=["revenue"])


# --- 三大法人 -------------------------------------------------------------


def get_institutional(stock_id: str, use_cache: bool = True) -> pd.DataFrame:
    """三大法人買賣超（股數），拆成外資／投信／自營。"""
    df = fetch("TaiwanStockInstitutionalInvestorsBuySell", stock_id, use_cache=use_cache)
    if df.empty:
        return pd.DataFrame(columns=["date", "stock_id", "foreign", "trust", "dealer"])

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["net"] = pd.to_numeric(df["buy"], errors="coerce") - pd.to_numeric(
        df["sell"], errors="coerce"
    )
    wide = df.pivot_table(index="date", columns="name", values="net", aggfunc="sum").fillna(0)

    def col(*candidates: str) -> pd.Series:
        for c in candidates:
            if c in wide.columns:
                return wide[c]
        return pd.Series(0.0, index=wide.index)

    out = pd.DataFrame(
        {
            "date": wide.index,
            "foreign": col("Foreign_Investor", "Foreign_Dealer_Self").values,
            "trust": col("Investment_Trust").values,
            "dealer": (col("Dealer_self") + col("Dealer_Hedging")).values,
        }
    )
    out["stock_id"] = str(stock_id)
    return out.reset_index(drop=True)
