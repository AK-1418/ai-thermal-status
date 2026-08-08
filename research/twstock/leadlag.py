"""緯穎 → 智邦 的月營收領先落後檢驗。

假設：AI 資料中心的建置順序是「運算先進場、網路後擴充」，
所以整櫃代工廠（緯穎／廣達／緯創）的營收動能，應該領先交換器廠（智邦）1~3 個月。

這個檢驗是整套研究裡最便宜也最該先做的一步 —— 它有機會直接推翻整個想法，
而推翻掉的話，後面所有建模工作都省下來了。

統計上有兩個必須處理的陷阱：

1. YoY 序列自我相關極強。兩條都在趨勢向上的序列，隨便算相關係數都會很高，
   那是共同趨勢不是領先關係。所以除了 YoY 本身，一定要看「加速度」
   （相對自身近期趨勢的偏離）的相關性，後者才是有意義的。

2. 自我相關會讓 p value 嚴重高估顯著性。這裡用 Bartlett–Quenouille 的
   有效樣本數修正，把 n 打折之後再算 t 統計量。

另外還有一個安慰劑檢驗：拿同一組領先指標去對消費性 CPE（中磊／智易／明泰）。
CPE 跟 AI 資料中心無關，如果領先關係在 CPE 上一樣成立，
那抓到的就是台股整體景氣，不是供應鏈的傳導。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

import config
from datasource import DataUnavailable, get_monthly_revenue

MAX_LAG = 6


def _effective_n(x: np.ndarray, y: np.ndarray) -> float:
    """Bartlett–Quenouille 有效樣本數修正。

    兩條自我相關的序列，實際獨立資訊量遠小於觀測數。不修正的話
    t 統計量會膨脹，把共同趨勢誤判成顯著的領先關係。
    """
    n = len(x)
    if n < 4:
        return float(n)

    def ac1(s: np.ndarray) -> float:
        s = s - s.mean()
        denom = float(np.dot(s, s))
        if denom == 0:
            return 0.0
        return float(np.dot(s[:-1], s[1:]) / denom)

    r1, r2 = ac1(x), ac1(y)
    prod = r1 * r2
    if prod >= 1:
        return 2.0
    n_eff = n * (1 - prod) / (1 + prod)
    return float(max(2.0, min(n_eff, n)))


def cross_correlation(
    lead: pd.Series, target: pd.Series, max_lag: int = MAX_LAG
) -> pd.DataFrame:
    """掃 lag 0..max_lag，算 corr(lead_{t-k}, target_t)。

    lag = k 的意思是「領先指標 k 個月前的值，對應目標的當期值」。
    k > 0 且相關顯著，才叫領先。
    """
    rows = []
    joined = pd.concat([lead.rename("lead"), target.rename("target")], axis=1)

    for k in range(0, max_lag + 1):
        sub = pd.concat(
            [joined["lead"].shift(k).rename("lead"), joined["target"]], axis=1
        ).dropna()
        if len(sub) < 12:
            rows.append({"lag": k, "corr": np.nan, "n": len(sub), "n_eff": np.nan,
                         "t": np.nan, "p": np.nan})
            continue

        x = sub["lead"].to_numpy(dtype=float)
        y = sub["target"].to_numpy(dtype=float)
        if x.std() == 0 or y.std() == 0:
            rows.append({"lag": k, "corr": np.nan, "n": len(sub), "n_eff": np.nan,
                         "t": np.nan, "p": np.nan})
            continue

        r = float(np.corrcoef(x, y)[0, 1])
        n_eff = _effective_n(x, y)
        if abs(r) >= 1.0 or n_eff <= 2:
            t_stat, p_val = np.nan, np.nan
        else:
            t_stat = r * np.sqrt((n_eff - 2) / (1 - r**2))
            p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n_eff - 2))

        rows.append(
            {"lag": k, "corr": r, "n": len(sub), "n_eff": n_eff, "t": t_stat, "p": p_val}
        )

    return pd.DataFrame(rows)


def _revenue_panel(stock_ids: list[str]) -> dict[str, pd.DataFrame]:
    panel: dict[str, pd.DataFrame] = {}
    for sid in stock_ids:
        try:
            rev = get_monthly_revenue(sid)
        except DataUnavailable as exc:
            print(f"[warn] 跳過 {config.name_of(sid)}（{sid}）：{exc}")
            continue
        panel[sid] = rev.set_index("period")
    return panel


def run(target: str = config.TARGET, max_lag: int = MAX_LAG) -> dict[str, pd.DataFrame]:
    """跑完整的領先落後檢驗，回傳 {描述: 結果表}。"""
    lead_ids = list(config.LEAD_CANDIDATES)
    control_ids = list(config.CONTROL_CPE)
    panel = _revenue_panel([target, *lead_ids, *control_ids])

    if target not in panel:
        raise DataUnavailable(f"主體 {target} 沒有月營收資料，無法進行檢驗")

    results: dict[str, pd.DataFrame] = {}
    tgt = panel[target]

    for metric in ("yoy", "yoy_accel"):
        for lid in lead_ids:
            if lid not in panel:
                continue
            key = f"{metric} | {config.name_of(lid)} -> {config.name_of(target)}"
            results[key] = cross_correlation(
                panel[lid][metric], tgt[metric], max_lag=max_lag
            )

        # 安慰劑：同一組領先指標對 CPE。這裡如果也顯著，前面的結果就不值錢。
        for cid in control_ids:
            if cid not in panel:
                continue
            for lid in lead_ids:
                if lid not in panel:
                    continue
                key = (
                    f"{metric} | [安慰劑] {config.name_of(lid)} -> {config.name_of(cid)}"
                )
                results[key] = cross_correlation(
                    panel[lid][metric], panel[cid][metric], max_lag=max_lag
                )

    return results


def summarize(results: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """每組取最佳的正 lag，整理成一張可讀的摘要表。"""
    rows = []
    for key, tab in results.items():
        positive = tab[(tab["lag"] > 0) & tab["corr"].notna()]
        if positive.empty:
            continue
        best = positive.loc[positive["corr"].abs().idxmax()]
        lag0 = tab[tab["lag"] == 0]["corr"]
        rows.append(
            {
                "關係": key,
                "最佳lag(月)": int(best["lag"]),
                "相關係數": round(float(best["corr"]), 3),
                "lag0相關": round(float(lag0.iloc[0]), 3) if not lag0.empty
                            and pd.notna(lag0.iloc[0]) else np.nan,
                "有效n": round(float(best["n_eff"]), 1) if pd.notna(best["n_eff"]) else np.nan,
                "p值": round(float(best["p"]), 4) if pd.notna(best["p"]) else np.nan,
                "顯著": "是" if pd.notna(best["p"]) and best["p"] < 0.05 else "否",
            }
        )
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    return out.sort_values("相關係數", key=lambda s: s.abs(), ascending=False)


def interpret(summary: pd.DataFrame) -> str:
    """把統計結果翻成可以拿來做決策的一句話。"""
    if summary.empty:
        return "沒有足夠資料形成結論。"

    real = summary[~summary["關係"].str.contains(r"\[安慰劑\]")]
    placebo = summary[summary["關係"].str.contains(r"\[安慰劑\]")]

    accel = real[real["關係"].str.startswith("yoy_accel")]
    sig = accel[accel["顯著"] == "是"]

    lines = []
    if sig.empty:
        lines.append(
            "結論：在加速度指標上找不到顯著的領先關係。\n"
            "  → 供應鏈傳導的假設在月營收這個頻率上不成立，或訊號被雜訊蓋過。\n"
            "  → 建議停止往這個方向加特徵，改從估值與預期落差切入。"
        )
    else:
        best = sig.iloc[0]
        lines.append(
            f"結論：偵測到領先關係 —— {best['關係']}，"
            f"lag {best['最佳lag(月)']} 個月，相關 {best['相關係數']}，p={best['p值']}。"
        )
        placebo_sig = placebo[
            (placebo["顯著"] == "是") & placebo["關係"].str.startswith("yoy_accel")
        ]
        if not placebo_sig.empty:
            lines.append(
                "  ⚠ 但安慰劑組（CPE）同樣顯著 —— 這代表抓到的很可能是台股整體景氣，\n"
                "     不是 AI 供應鏈的傳導。這個訊號不該拿來當作論點的證據。"
            )
        else:
            lines.append(
                "  ✓ 安慰劑組（CPE）不顯著 —— 領先關係有供應鏈特異性，值得往下做。"
            )

    if not real.empty:
        lvl = real[real["關係"].str.startswith("yoy |")]
        if not lvl.empty and (lvl["相關係數"].abs() > 0.6).any():
            lines.append(
                "  註：YoY 水準值的相關很高，但那多半是共同趨勢造成的假相關，\n"
                "      判斷請以 yoy_accel（加速度）那組為準。"
            )
    return "\n".join(lines)
