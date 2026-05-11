import akshare as ak
from datetime import datetime, timedelta
from backend.sources import fetch_etf_daily as _source_fetch_etf, fetch_index_daily as _source_fetch_index

CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


def _safe_float(val) -> float | None:
    if val is None: return None
    try: return float(str(val).replace("%", ""))
    except (ValueError, TypeError): return None


def _fetch_etf_daily(code: str, start: str, end: str) -> list[dict]:
    """ETF 日线: mootdx > 腾讯财经 > 新浪 (自动降级)"""
    return _source_fetch_etf(code, start, end)


def _fetch_index_daily(symbol: str, start: str, end: str) -> list[dict]:
    """指数日线: mootdx > 腾讯财经 > AKShare (自动降级)"""
    return _source_fetch_index(symbol, start, end)


async def fetch_and_store_etf_data():
    from backend.database import upsert_etf_basic, upsert_etf_daily, init_db, update_etf_shares

    await init_db()

    # 1. ETF 列表 (fund.eastmoney.com — 此接口仍可用)
    df_info = ak.fund_etf_fund_daily_em()
    mask = df_info["基金简称"].apply(lambda x: any(kw in str(x) for kw in CSI300_KEYWORDS))
    df_csi300 = df_info[mask].copy()
    if df_csi300.empty: print("No CSI 300 ETFs found"); return 0

    df_csi300 = df_csi300[df_csi300["基金代码"].astype(str).str.startswith("5")]
    if df_csi300.empty: print("No SSE CSI 300 ETFs found"); return 0
    df_csi300 = df_csi300.sort_values("基金代码").head(7)

    today_str = datetime.now().strftime("%Y-%m-%d")
    nav_col = f"{today_str}-单位净值"

    etf_codes = [str(c) for c in df_csi300["基金代码"].tolist()]
    etf_basic_list = []
    for _, row in df_csi300.iterrows():
        code = str(row["基金代码"])
        etf_basic_list.append({
            "code": code, "name": str(row["基金简称"]),
            "total_shares": None,
            "nav": _safe_float(row.get(nav_col)) if nav_col in df_csi300.columns else None,
            "premium": _safe_float(row.get("折价率")),
        })

    # 2. 用 Sina API 拉取每日 K 线 (push2his 已不对外可用)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end_date = datetime.now().strftime("%Y-%m-%d")
    all_dates = []

    for etf in etf_basic_list:
        code = etf["code"]
        try:
            klines = _fetch_etf_daily(code, start_date, end_date)
            records = []
            for k in klines:
                if k["date"] not in all_dates: all_dates.append(k["date"])
                records.append({
                    "code": code, "date": k["date"],
                    "open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"],
                    "volume": k["volume"], "total_shares": None,
                    # amount (成交额/元) 存为 turnover 列, 显示时转亿元
                    "turnover": k.get("amount"),
                })
            await upsert_etf_daily(records)
            print(f"  {code} {etf['name']}: {len(records)} rows")
        except Exception as e:
            print(f"  {code} FAIL: {e}")

    if not all_dates:
        print("No daily data, saving ETF basic only")
        await upsert_etf_basic(etf_basic_list)
        return len(etf_basic_list)

    # 3. SSE 份额 (每 20 天采样 ~10-12 个点以减少 API 调用, 每次 ~10s)
    all_dates.sort()
    sample_dates = all_dates[::20]
    if all_dates[-1] not in sample_dates: sample_dates.append(all_dates[-1])
    if all_dates[0] not in sample_dates: sample_dates.insert(0, all_dates[0])

    shares_map = {code: {} for code in etf_codes}
    for date_str in sample_dates:
        try:
            d = date_str.replace("-", "")
            df_scale = ak.fund_etf_scale_sse(date=d)
            if df_scale is None or df_scale.empty:
                print(f"  SSE {date_str}: empty (non-trading day?)")
                continue
            for _, item in df_scale.iterrows():
                c = str(item.get("基金代码", ""))
                if c in etf_codes:
                    shares_map[c][date_str] = _safe_float(item.get("基金份额"))
        except Exception as e:
            print(f"  SSE scale {date_str}: {e}")

    for etf in etf_basic_list:
        latest = None
        for d in sorted(shares_map.get(etf["code"], {}).keys(), reverse=True):
            v = shares_map[etf["code"]][d]
            if v is not None:
                latest = v
                break
        etf["total_shares"] = latest
    await upsert_etf_basic(etf_basic_list)

    # 份额插值
    for code in etf_codes:
        s_map = shares_map[code]
        if not s_map: continue
        sorted_keys = sorted(s_map.keys())
        share_recs = []
        for date_str in all_dates:
            if date_str in s_map:
                shares = s_map[date_str]
            else:
                prev_d, prev_v, next_d, next_v = None, None, None, None
                for d in sorted_keys:
                    if d <= date_str: prev_d, prev_v = d, s_map[d]
                for d in sorted_keys:
                    if d >= date_str and next_d is None: next_d, next_v = d, s_map[d]
                if prev_v is not None and next_v is not None and prev_d != next_d:
                    try:
                        r = (all_dates.index(date_str) - all_dates.index(prev_d)) / max(all_dates.index(next_d) - all_dates.index(prev_d), 1)
                        shares = prev_v + (next_v - prev_v) * r
                    except ValueError: shares = prev_v
                elif prev_v is not None: shares = prev_v
                elif next_v is not None: shares = next_v
                else: shares = None
            share_recs.append({"code": code, "date": date_str, "total_shares": shares})
        await update_etf_shares(share_recs)

    return len(etf_basic_list)


async def fetch_and_store_index_data():
    from backend.database import upsert_index_daily, init_db
    await init_db()
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    try:
        records = _fetch_index_daily("000001", start, end)
        if records:
            await upsert_index_daily(records)
            print(f"  上证指数: {len(records)} rows")
        return len(records)
    except Exception as e:
        print(f"  Index 000001 FAIL: {e}"); return 0


async def fetch_and_store_hs300_data():
    from backend.database import upsert_hs300_daily, init_db
    await init_db()
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    try:
        records = _fetch_index_daily("000300", start, end)
        if records:
            await upsert_hs300_daily(records)
            print(f"  沪深300: {len(records)} rows")
        return len(records)
    except Exception as e:
        print(f"  HS300 FAIL: {e}"); return 0
