#!/usr/bin/env python3
"""執行入口：跑領先落後檢驗與基準比較，輸出報表。

用法：
    export FINMIND_TOKEN=<你的 token>
    python run.py                # 兩項都跑
    python run.py --leadlag      # 只跑領先落後
    python run.py --baseline     # 只跑基準比較
    python run.py --check        # 只檢查網路與 token 是否就緒
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

import baseline
import config
import leadlag
from datasource import BLOCKED_HOSTS_HINT, DataUnavailable, fetch

OUT_DIR = Path(__file__).parent / "output"


def _rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _show(df: pd.DataFrame, empty_msg: str = "（無資料）") -> None:
    if df is None or df.empty:
        print(empty_msg)
        return
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print(df.to_string(index=False))


def check() -> bool:
    """確認資料源可達。擋在網路政策上的話直接講清楚，不要讓它半路才炸。"""
    print("檢查 FinMind 連線 ...")
    try:
        df = fetch(
            "TaiwanStockPrice",
            config.TARGET,
            start_date="2026-01-01",
            use_cache=False,
            max_retries=1,
        )
    except DataUnavailable as exc:
        print(f"\n✗ 失敗\n{exc}", file=sys.stderr)
        return False
    print(f"✓ 連線正常，取得 {config.name_of(config.TARGET)} {len(df)} 筆日線")
    return True


def run_leadlag() -> None:
    _rule("領先落後檢驗：AI 伺服器整櫃廠 → 智邦（月營收）")
    print(
        "假設：運算先進場、網路後擴充，所以整櫃代工的營收動能領先交換器廠 1~3 個月。\n"
        "判讀請以 yoy_accel（加速度）那組為準；yoy 水準值的高相關多半是共同趨勢。\n"
        "安慰劑組是同一批領先指標對消費性 CPE —— 那組若也顯著，訊號就沒有供應鏈特異性。"
    )
    results = leadlag.run()
    summary = leadlag.summarize(results)

    _rule("摘要（依相關強度排序）")
    _show(summary)

    _rule("判讀")
    print(leadlag.interpret(summary))

    OUT_DIR.mkdir(exist_ok=True)
    if not summary.empty:
        summary.to_csv(OUT_DIR / "leadlag_summary.csv", index=False)
    for key, tab in results.items():
        safe = key.replace(" ", "").replace("|", "_").replace("->", "to").replace("/", "-")
        tab.to_csv(OUT_DIR / f"leadlag_{safe}.csv", index=False)
    print(f"\n明細已寫到 {OUT_DIR}")


def run_baseline() -> None:
    _rule("基準比較：風險調整後的報酬（含來回交易成本）")
    print(
        "主指標是 Sharpe 與「波動對齊後年化報酬」，不是累積報酬。\n"
        "波動對齊 = 把每個標的縮放到智邦的波動水準再比 —— 這才是用槓桿調整後誰比較強。"
    )
    out = baseline.run()

    for title, df in out.items():
        _rule(title)
        _show(df)

    OUT_DIR.mkdir(exist_ok=True)
    for title, df in out.items():
        if df is not None and not df.empty:
            safe = title.replace("(", "_").replace(")", "").replace("/", "-")
            df.to_csv(OUT_DIR / f"baseline_{safe}.csv", index=False)
    print(f"\n明細已寫到 {OUT_DIR}")


def main() -> int:
    ap = argparse.ArgumentParser(description="台股智邦研究 pipeline")
    ap.add_argument("--leadlag", action="store_true", help="只跑領先落後檢驗")
    ap.add_argument("--baseline", action="store_true", help="只跑基準比較")
    ap.add_argument("--check", action="store_true", help="只檢查連線")
    args = ap.parse_args()

    if args.check:
        return 0 if check() else 1

    if not check():
        print(
            "\n資料源不可達，中止。\n"
            "若是網路政策問題，請依上面的清單放行網域後開新 session。",
            file=sys.stderr,
        )
        return 1

    run_all = not (args.leadlag or args.baseline)
    try:
        if args.leadlag or run_all:
            run_leadlag()
        if args.baseline or run_all:
            run_baseline()
    except DataUnavailable as exc:
        print(f"\n資料抓取失敗：{exc}", file=sys.stderr)
        print(BLOCKED_HOSTS_HINT, file=sys.stderr)
        return 1

    _rule("提醒")
    print(
        "1. 這裡跑出來的所有數字都是「已實現的歷史」，不是預測。\n"
        "2. 買進持有基準已扣掉來回成本 "
        f"{config.round_trip_cost():.4f}（手續費打 {config.BROKER_DISCOUNT} 折 + 證交稅）。\n"
        "   任何主動策略必須明顯打敗這條線才有存在價值。\n"
        "3. 月營收一律用次月 10 日的公布日對齊，沒有前視偏誤。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
