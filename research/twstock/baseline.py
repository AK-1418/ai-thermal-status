"""基準比較：智邦 vs 緯穎 vs CPE 對照組，用風險調整後的角度看。

這支的存在理由是回答一個具體問題：「智邦在股價上到底有沒有優勢？」

散戶習慣只比絕對漲幅，那是系統性的錯誤。如果 A 的報酬是 B 的七成、
但波動只有一半，那麼把 A 放大到跟 B 同樣的波動水準之後，A 是贏的 ——
而且波動小的部位你抱得住，不會在回檔時被洗出場。

所以這裡的主指標是 Sharpe 和「波動對齊後的報酬」，不是累積報酬。
同時也產出任何策略都必須先打敗的門檻：買進持有 + 扣掉來回交易成本。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config
from datasource import DataUnavailable, get_prices

TRADING_DAYS = 252


def _load_returns(stock_ids: list[str]) -> pd.DataFrame:
    """組出以日期為 index、各標的還原報酬率為欄位的表。"""
    series = {}
    for sid in stock_ids:
        try:
            px = get_prices(sid)
        except DataUnavailable as exc:
            print(f"[warn] 跳過 {config.name_of(sid)}（{sid}）：{exc}")
            continue
        s = px.set_index("date")["ret"]
        series[sid] = s[~s.index.duplicated(keep="last")]

    if not series:
        raise DataUnavailable("沒有任何標的取得價格資料")
    return pd.DataFrame(series).sort_index()


def metrics(ret: pd.Series, cost: float = 0.0) -> dict[str, float]:
    """單一報酬序列的風險與報酬指標。

    cost 是一次進出的總成本，從累積報酬裡一次性扣掉（買進持有只交易一次來回）。
    """
    r = ret.dropna()
    if len(r) < 30:
        return {}

    cum = float((1 + r).prod() * (1 - cost) - 1)
    years = len(r) / TRADING_DAYS
    cagr = (1 + cum) ** (1 / years) - 1 if years > 0 and cum > -1 else np.nan
    vol = float(r.std() * np.sqrt(TRADING_DAYS))
    sharpe = cagr / vol if vol > 0 and pd.notna(cagr) else np.nan

    equity = (1 + r).cumprod()
    drawdown = equity / equity.cummax() - 1
    mdd = float(drawdown.min())
    calmar = cagr / abs(mdd) if mdd < 0 and pd.notna(cagr) else np.nan

    return {
        "累積報酬": cum,
        "年化報酬": float(cagr) if pd.notna(cagr) else np.nan,
        "年化波動": vol,
        "Sharpe": float(sharpe) if pd.notna(sharpe) else np.nan,
        "最大回撤": mdd,
        "Calmar": float(calmar) if pd.notna(calmar) else np.nan,
        "交易日數": len(r),
    }


def vol_matched_return(ret: pd.Series, target_vol: float) -> float:
    """把部位縮放到指定波動水準後的年化報酬。

    這是「用槓桿調整後誰比較強」的直接答案，也是絕對漲幅排行榜看不出來的東西。

    注意這裡是先縮放日報酬再複利，所以波動拖累（volatility drag，約 σ²/2）
    有被算進去 —— 放大槓桿不是免費的。低波動標的放大後不必然反超高波動標的，
    Sharpe 差距要夠大才行。想看沒有拖累的版本就直接比 Sharpe。
    """
    r = ret.dropna()
    vol = r.std() * np.sqrt(TRADING_DAYS)
    if vol <= 0:
        return np.nan
    scale = target_vol / vol
    scaled = r * scale
    years = len(scaled) / TRADING_DAYS
    cum = float((1 + scaled).prod() - 1)
    return (1 + cum) ** (1 / years) - 1 if years > 0 and cum > -1 else np.nan


def excess_vs_benchmark(ret: pd.DataFrame, benchmark: str) -> pd.DataFrame:
    """扣掉 beta 之後的超額報酬（alpha）。

    這幾檔的 beta 都很高，不剝掉的話，任何「預測」多半只是在預測大盤。
    """
    if benchmark not in ret.columns:
        return pd.DataFrame()

    bench = ret[benchmark]
    rows = []
    for col in ret.columns:
        if col == benchmark:
            continue
        pair = pd.concat([ret[col], bench], axis=1).dropna()
        if len(pair) < 60:
            continue
        y = pair.iloc[:, 0].to_numpy()
        x = pair.iloc[:, 1].to_numpy()
        beta = float(np.cov(y, x)[0, 1] / np.var(x)) if np.var(x) > 0 else np.nan
        alpha_daily = float(y.mean() - beta * x.mean()) if pd.notna(beta) else np.nan
        resid = y - (beta * x) if pd.notna(beta) else np.array([])
        rows.append(
            {
                "標的": config.name_of(col),
                "beta": round(beta, 3) if pd.notna(beta) else np.nan,
                "年化alpha": round(alpha_daily * TRADING_DAYS, 4)
                if pd.notna(alpha_daily) else np.nan,
                "殘差年化波動": round(float(resid.std() * np.sqrt(TRADING_DAYS)), 4)
                if resid.size else np.nan,
                "資訊比": round(
                    (alpha_daily * TRADING_DAYS) / (resid.std() * np.sqrt(TRADING_DAYS)), 3
                ) if resid.size and resid.std() > 0 and pd.notna(alpha_daily) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def run(include_optics: bool = False) -> dict[str, pd.DataFrame]:
    ids = config.all_stocks(include_optics=include_optics)
    ret = _load_returns(ids)

    # 取共同期間，否則上市時間不同會讓比較失真（緯穎 2019 才上市）
    common = ret.dropna(how="any")
    cost = config.round_trip_cost()

    rows = []
    for col in ret.columns:
        m = metrics(common[col], cost=cost)
        if not m:
            continue
        rows.append({"標的": config.name_of(col), "代號": col, **m})
    table = pd.DataFrame(rows)

    # 波動對齊：全部縮放到智邦的波動水準再比報酬
    if config.TARGET in common.columns:
        target_vol = float(common[config.TARGET].std() * np.sqrt(TRADING_DAYS))
        table["波動對齊後年化報酬"] = [
            round(vol_matched_return(common[c], target_vol), 4)
            for c in table["代號"]
        ]

    for c in ("累積報酬", "年化報酬", "年化波動", "最大回撤"):
        if c in table.columns:
            table[c] = table[c].round(4)
    for c in ("Sharpe", "Calmar"):
        if c in table.columns:
            table[c] = table[c].round(3)

    return {
        "風險報酬總表": table.sort_values("Sharpe", ascending=False),
        "超額報酬(剝除beta)": excess_vs_benchmark(common, config.BENCHMARK),
        "期間": pd.DataFrame(
            [{"起": str(common.index.min().date()),
              "訖": str(common.index.max().date()),
              "共同交易日": len(common),
              "來回成本": round(cost, 5)}]
        ),
    }
