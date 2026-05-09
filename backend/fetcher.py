import akshare as ak
import os
from datetime import datetime, timedelta

# 禁用系统代理（国内金融数据 API 不需要代理）
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ["no_proxy"] = "*"

CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


def _safe_float(val) -> float | None:
    """安全转换为 float，处理 '---' 等非数字值"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def fetch_and_store_etf_data():
    """拉取沪深300ETF列表(按总份额排序取前7)及其日线数据，存入数据库"""
    from backend.database import upsert_etf_basic, upsert_etf_daily, init_db

    await init_db()

    # 1. 获取所有ETF基金信息
    df_info = ak.fund_etf_fund_daily_em()
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

    etf_codes = [str(c) for c in df_csi300["基金代码"].tolist()]

    today_str = datetime.now().strftime("%Y-%m-%d")
    nav_col = f"{today_str}-单位净值"

    etf_basic_list = []
    for _, row in df_csi300.iterrows():
        code = str(row["基金代码"])
        etf_basic_list.append({
            "code": code,
            "name": str(row["基金简称"]),
            "total_shares": None,
            "nav": _safe_float(row.get(nav_col)) if nav_col in df_csi300.columns else None,
        })

    # 2. 拉取每只ETF近一年日线数据 (含成交量)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    all_dates = []
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
                date_str = str(row["日期"])
                if date_str not in all_dates:
                    all_dates.append(date_str)
                records.append({
                    "code": etf["code"],
                    "date": date_str,
                    "open": float(row["开盘"]) if row.get("开盘") else None,
                    "high": float(row["最高"]) if row.get("最高") else None,
                    "low": float(row["最低"]) if row.get("最低") else None,
                    "close": float(row["收盘"]) if row.get("收盘") else None,
                    "volume": float(row["成交量"]) if row.get("成交量") else None,
                    "total_shares": None,
                    "turnover": float(row["换手率"]) if row.get("换手率") else None,
                })
            await upsert_etf_daily(records)
        except Exception as e:
            print(f"Failed to fetch history for {etf['code']} {etf['name']}: {e}")

    # 3. 从上交所 API 拉取历史份额数据（每周抽样，约50个日期）
    all_dates.sort()
    sample_dates = all_dates[::5]  # 每5个交易日取一个
    if all_dates[-1] not in sample_dates:
        sample_dates.append(all_dates[-1])  # 确保包含最新日期

    shares_map = {code: {} for code in etf_codes}
    for date_str in sample_dates:
        try:
            df_scale = ak.fund_etf_scale_sse(date=date_str.replace("-", ""))
            for code in etf_codes:
                rows = df_scale[df_scale["基金代码"] == code]
                if not rows.empty:
                    shares_map[code][date_str] = float(rows.iloc[0]["基金份额"])
        except Exception as e:
            print(f"Failed SSE scale for {date_str}: {e}")

    # 更新 etf_basic.total_shares 为最新可用份额
    for etf in etf_basic_list:
        latest_shares = None
        for d in sorted(shares_map.get(etf["code"], {}).keys(), reverse=True):
            if shares_map[etf["code"]][d] is not None:
                latest_shares = shares_map[etf["code"]][d]
                break
        etf["total_shares"] = latest_shares

    await upsert_etf_basic(etf_basic_list)

    # 更新 etf_daily.total_shares (采样日期写入实际份额，中间日期插值)
    from backend.database import update_etf_shares
    for code in etf_codes:
        share_records = []
        s_map = shares_map[code]
        if not s_map:
            continue
        sorted_dates = sorted(s_map.keys())
        for date_str in all_dates:
            if date_str in s_map:
                shares = s_map[date_str]
            else:
                prev_date, prev_val = None, None
                next_date, next_val = None, None
                for d in sorted_dates:
                    if d <= date_str:
                        prev_date, prev_val = d, s_map[d]
                for d in sorted_dates:
                    if d >= date_str and (next_date is None or d < next_date):
                        next_date, next_val = d, s_map[d]
                if prev_val is not None and next_val is not None and prev_date != next_date:
                    idx_curr = all_dates.index(date_str)
                    idx_prev = all_dates.index(prev_date)
                    idx_next = all_dates.index(next_date)
                    ratio = (idx_curr - idx_prev) / max(idx_next - idx_prev, 1)
                    shares = prev_val + (next_val - prev_val) * ratio
                elif prev_val is not None:
                    shares = prev_val
                elif next_val is not None:
                    shares = next_val
                else:
                    shares = None
            share_records.append({
                "code": code,
                "date": date_str,
                "total_shares": shares,
            })
        await update_etf_shares(share_records)

    return len(etf_basic_list)


async def fetch_and_store_index_data():
    """拉取上证指数(000001)日线数据，存入数据库"""
    from backend.database import upsert_index_daily, init_db

    await init_db()

    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.index_zh_a_hist(
            symbol="000001",
            period="daily",
            start_date=start_date,
            end_date=end_date,
        )
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]) if row.get("开盘") else None,
                "high": float(row["最高"]) if row.get("最高") else None,
                "low": float(row["最低"]) if row.get("最低") else None,
                "close": float(row["收盘"]) if row.get("收盘") else None,
                "volume": float(row["成交量"]) if row.get("成交量") else None,
            })
        await upsert_index_daily(records)
        return len(records)
    except Exception as e:
        print(f"Failed to fetch index data: {e}")
        return 0


async def fetch_and_store_hs300_data():
    """拉取沪深300指数(000300)日线数据，存入数据库"""
    from backend.database import upsert_hs300_daily, init_db

    await init_db()

    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    try:
        df = ak.index_zh_a_hist(
            symbol="000300",
            period="daily",
            start_date=start_date,
            end_date=end_date,
        )
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["日期"]),
                "open": float(row["开盘"]) if row.get("开盘") else None,
                "high": float(row["最高"]) if row.get("最高") else None,
                "low": float(row["最低"]) if row.get("最低") else None,
                "close": float(row["收盘"]) if row.get("收盘") else None,
                "volume": float(row["成交量"]) if row.get("成交量") else None,
            })
        await upsert_hs300_daily(records)
        return len(records)
    except Exception as e:
        print(f"Failed to fetch HS300 data: {e}")
        return 0
