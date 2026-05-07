import akshare as ak
from datetime import datetime, timedelta

CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


async def fetch_and_store_etf_data():
    """拉取沪深300ETF列表(按总份额排序取前7)及其日线数据，存入数据库"""
    from backend.database import upsert_etf_basic, upsert_etf_daily, init_db

    await init_db()

    # 1. 获取所有ETF基金信息
    df_info = ak.fund_etf_fund_daily_em()
    # 过滤沪深300ETF
    mask = df_info["基金简称"].apply(
        lambda x: any(kw in str(x) for kw in CSI300_KEYWORDS)
    )
    df_csi300 = df_info[mask].copy()

    if df_csi300.empty:
        print("No CSI 300 ETFs found")
        return 0

    # 仅保留上交所 ETF (代码以5开头)
    df_csi300 = df_csi300[df_csi300["基金代码"].astype(str).str.startswith("5")]

    if df_csi300.empty:
        print("No SSE CSI 300 ETFs found")
        return 0

    # 取前7，优先按代码排序（大体量老牌 ETF 代码更小）
    df_csi300 = df_csi300.sort_values("基金代码").head(7)

    # 获取当天净值列名
    today_str = datetime.now().strftime("%Y-%m-%d")
    nav_col = f"{today_str}-单位净值"

    etf_basic_list = []
    for _, row in df_csi300.iterrows():
        code = str(row["基金代码"])
        etf_basic_list.append({
            "code": code,
            "name": str(row["基金简称"]),
            "total_shares": None,  # AKShare 当前版本不直接提供份额数据
            "nav": float(row[nav_col]) if nav_col in df_csi300.columns and row[nav_col] else None,
        })

    await upsert_etf_basic(etf_basic_list)

    # 2. 拉取每只ETF近一年日线数据 (含成交量)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    for etf in etf_basic_list:
        try:
            df_hist = ak.fund_etf_hist_em(
                symbol=etf["code"],
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=""
            )
            records = []
            for _, row in df_hist.iterrows():
                records.append({
                    "code": etf["code"],
                    "date": str(row["日期"]),
                    "open": float(row["开盘"]) if row.get("开盘") else None,
                    "high": float(row["最高"]) if row.get("最高") else None,
                    "low": float(row["最低"]) if row.get("最低") else None,
                    "close": float(row["收盘"]) if row.get("收盘") else None,
                    "volume": float(row["成交量"]) if row.get("成交量") else None,
                    "total_shares": etf["total_shares"],
                })
            await upsert_etf_daily(records)
        except Exception as e:
            print(f"Failed to fetch history for {etf['code']} {etf['name']}: {e}")

    return len(etf_basic_list)
