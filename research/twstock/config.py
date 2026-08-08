"""研究標的與常數設定。

標的分群的原則：同一層瓶頸的公司才放在一起比較。
把資料中心交換器、AI 伺服器整櫃、消費性 CPE 混在一個「網通族群」裡，
是這類研究最常見的第一個錯誤。
"""

from __future__ import annotations

# --- 標的定義 -------------------------------------------------------------

# 研究主體：資料中心白牌交換器
TARGET = "2345"  # 智邦 Accton

# 領先指標候選：AI 伺服器整櫃代工。
# 假設是「運算先進場、網路後擴充」，所以這些公司的營收動能可能領先智邦。
LEAD_CANDIDATES = {
    "6669": "緯穎 Wiwynn",
    "2382": "廣達 Quanta",
    "3231": "緯創 Wistron",
}

# 對照組：消費性 CPE。跟 AI 資料中心幾乎無關。
# 如果訊號在這組也有效，代表抓到的是台股整體風險偏好，不是 AI 論點。
CONTROL_CPE = {
    "5388": "中磊 Sercomm",
    "3596": "智易 Arcadyan",
    "3380": "明泰 Alpha Networks",
}

# 延伸觀察：光通訊／光模組（scale-out 傳輸的物理解方）
OPTICS = {
    "6442": "光聖 Fiber Optic",
    "3081": "聯亞 LandMark",
    "4979": "華星光 Luxnet",
}

BENCHMARK = "0050"  # 元大台灣50，用來算超額報酬

NAMES = {
    TARGET: "智邦 Accton",
    BENCHMARK: "元大台灣50",
    **LEAD_CANDIDATES,
    **CONTROL_CPE,
    **OPTICS,
}


def all_stocks(include_optics: bool = False) -> list[str]:
    ids = [TARGET, BENCHMARK, *LEAD_CANDIDATES, *CONTROL_CPE]
    if include_optics:
        ids += list(OPTICS)
    # 去重但保持順序
    return list(dict.fromkeys(ids))


def name_of(stock_id: str) -> str:
    return NAMES.get(stock_id, stock_id)


# --- 期間 -----------------------------------------------------------------

# 月營收 YoY 需要 12 個月墊底，再加上 lag 掃描的範圍，所以起點要拉早。
START_DATE = "2018-01-01"
END_DATE = None  # None = 抓到最新


# --- 交易成本 -------------------------------------------------------------

BROKER_FEE_RATE = 0.001425   # 手續費，買賣各一次
BROKER_DISCOUNT = 0.6        # 常見的電子下單折扣（6 折）；不打折就設 1.0
SECURITIES_TAX_RATE = 0.003  # 證交稅，只有賣出課徵


def round_trip_cost() -> float:
    """一買一賣的總成本比率。

    回測不扣這個數字，結論通常是假的 —— 台股來回成本大約 0.4~0.6%，
    很多短週期訊號的預測邊際根本蓋不過它。
    """
    fee = BROKER_FEE_RATE * BROKER_DISCOUNT
    return fee * 2 + SECURITIES_TAX_RATE


# --- 制度性斷點 -----------------------------------------------------------

# 2020-03-23 台股由集合競價改為逐筆撮合。
# 微結構相關特徵（內外盤、委買賣價量）在這天前後不可比。
TICK_MATCHING_CHANGE = "2020-03-23"

# 漲跌停幅度 ±10%（2015-06 起）。報酬率分布在兩端有質量堆積，
# 對假設常態分布的模型是已知的問題。
PRICE_LIMIT = 0.10


# --- 月營收揭露規則 -------------------------------------------------------

# 台股規定：每月 10 日前公布「上月」營收。
# 這代表 M 月的營收，最早要到 M+1 月的 10 日才可用 —— 對齊錯了就是前視偏誤。
REVENUE_PUBLISH_DAY = 10
