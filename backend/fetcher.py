import akshare as ak
import subprocess
import json
from datetime import datetime, timedelta

CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


def _safe_float(val) -> float | None:
    if val is None: return None
    try: return float(str(val).replace("%", ""))
    except (ValueError, TypeError): return None


def _curl_json(url: str, referer: str = "") -> dict:
    """通过系统 curl 拉取 JSON (curl 正确处理代理)"""
    cmd = ["curl", "-s", "--max-time", "30"]
    if referer:
        cmd.extend(["-H", f"Referer: {referer}"])
    cmd.append(url)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    if r.returncode != 0 or not r.stdout.strip():
        raise Exception(f"curl failed: {r.stderr[:100]}")
    return json.loads(r.stdout)


def _curl_klines(secid: str, start: str, end: str) -> list[dict]:
    """拉取 K 线数据 (push2his.eastmoney.com 必须用 curl)"""
    url = (
        f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
        f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
        f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
        f"&klt=101&fqt=0&beg={start}&end={end}"
    )
    data = _curl_json(url, referer="https://quote.eastmoney.com/")
    klines = (data.get("data") or {}).get("klines") or []
    records = []
    for line in klines:
        parts = line.split(",")
        if len(parts) < 6: continue
        records.append({
            "date": parts[0],
            "open": _safe_float(parts[1]),
            "close": _safe_float(parts[2]),
            "high": _safe_float(parts[3]),
            "low": _safe_float(parts[4]),
            "volume": _safe_float(parts[5]),
            "turnover": _safe_float(parts[10]) if len(parts) > 10 else None,
        })
    return records


async def fetch_and_store_etf_data():
    from backend.database import upsert_etf_basic, upsert_etf_daily, init_db, update_etf_shares

    await init_db()

    # 1. ETF 列表 (fund.eastmoney.com 可用 AKShare)
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

    # 2. 用 curl 拉取每只 ETF 日线 (push2his 必须用 curl)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")
    all_dates = []

    for etf in etf_basic_list:
        code = etf["code"]
        try:
            klines = _curl_klines(f"1.{code}", start_date, end_date)
            records = []
            for k in klines:
                if k["date"] not in all_dates: all_dates.append(k["date"])
                records.append({
                    "code": code, "date": k["date"],
                    "open": k["open"], "high": k["high"], "low": k["low"], "close": k["close"],
                    "volume": k["volume"], "total_shares": None, "turnover": k["turnover"],
                })
            await upsert_etf_daily(records)
            print(f"  {code} {etf['name']}: {len(records)} rows")
        except Exception as e:
            print(f"  {code} FAIL: {e}")

    if not all_dates:
        print("No daily data, saving ETF basic only")
        await upsert_etf_basic(etf_basic_list)
        return len(etf_basic_list)

    # 3. SSE 份额 (query.sse.com.cn 用 curl)
    all_dates.sort()
    sample_dates = all_dates[::5]
    if all_dates[-1] not in sample_dates: sample_dates.append(all_dates[-1])

    shares_map = {code: {} for code in etf_codes}
    for date_str in sample_dates:
        try:
            d = date_str.replace("-", "")
            url = (
                f"https://query.sse.com.cn/commonQuery.do?"
                f"isPagination=true&pageHelp.pageSize=10000&pageHelp.pageNo=1"
                f"&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1"
                f"&sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L&STAT_DATE={d}"
            )
            data = _curl_json(url, referer="https://www.sse.com.cn/")
            for item in data.get("result", []):
                c = str(item.get("SEC_CODE", ""))
                if c in etf_codes: shares_map[c][date_str] = float(item.get("TOT_VOL", 0))
        except Exception as e:
            print(f"  SSE scale {date_str}: {e}")

    for etf in etf_basic_list:
        latest = None
        for d in sorted(shares_map.get(etf["code"], {}).keys(), reverse=True):
            if shares_map[etf["code"]][d] is not None: latest = shares_map[etf["code"]][d]; break
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


async def _fetch_index(symbol: str) -> list[dict]:
    """拉取指数 K 线"""
    secid = f"1.{symbol}"
    start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end = datetime.now().strftime("%Y%m%d")
    return _curl_klines(secid, start, end)


async def fetch_and_store_index_data():
    from backend.database import upsert_index_daily, init_db
    await init_db()
    try:
        records = await _fetch_index("000001")
        if records:
            await upsert_index_daily(records)
            print(f"  上证指数: {len(records)} rows")
        return len(records)
    except Exception as e:
        print(f"  Index 000001 FAIL: {e}"); return 0


async def fetch_and_store_hs300_data():
    from backend.database import upsert_hs300_daily, init_db
    await init_db()
    try:
        records = await _fetch_index("000300")
        if records:
            await upsert_hs300_daily(records)
            print(f"  沪深300: {len(records)} rows")
        return len(records)
    except Exception as e:
        print(f"  HS300 FAIL: {e}"); return 0
