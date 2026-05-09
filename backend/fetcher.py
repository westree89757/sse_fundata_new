import akshare as ak
import os
import subprocess
import json
from datetime import datetime, timedelta

CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


def _safe_float(val) -> float | None:
    if val is None: return None
    try: return float(str(val).replace("%", ""))
    except (ValueError, TypeError): return None


def _fetch_json(url: str, referer: str = "") -> dict:
    """通过系统 curl 绕过代理拉取 JSON 数据"""
    cmd = ["curl", "-s", "--noproxy", "*", "--max-time", "30", url]
    if referer:
        cmd.extend(["-H", f"Referer: {referer}"])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    if result.returncode != 0 or not result.stdout.strip():
        raise Exception(f"curl failed: {result.stderr[:100]}")
    return json.loads(result.stdout)


async def fetch_and_store_etf_data():
    """拉取沪深300ETF列表及其日线数据，存入数据库"""
    from backend.database import upsert_etf_basic, upsert_etf_daily, init_db

    await init_db()

    # 1. 获取所有ETF基金信息 — AKShare fund_etf_fund_daily_em (fund.eastmoney.com 可访问)
    df_info = ak.fund_etf_fund_daily_em()
    mask = df_info["基金简称"].apply(
        lambda x: any(kw in str(x) for kw in CSI300_KEYWORDS)
    )
    df_csi300 = df_info[mask].copy()

    if df_csi300.empty:
        print("No CSI 300 ETFs found"); return 0

    df_csi300 = df_csi300[df_csi300["基金代码"].astype(str).str.startswith("5")]
    if df_csi300.empty:
        print("No SSE CSI 300 ETFs found"); return 0

    df_csi300 = df_csi300.sort_values("基金代码").head(7)

    today_str = datetime.now().strftime("%Y-%m-%d")
    nav_col = f"{today_str}-单位净值"

    etf_codes = [str(c) for c in df_csi300["基金代码"].tolist()]
    etf_basic_list = []
    for _, row in df_csi300.iterrows():
        code = str(row["基金代码"])
        etf_basic_list.append({
            "code": code,
            "name": str(row["基金简称"]),
            "total_shares": None,
            "nav": _safe_float(row.get(nav_col)) if nav_col in df_csi300.columns else None,
            "premium": _safe_float(row.get("折价率")),
        })

    # 2. 通过 curl 拉取每只ETF近一年日线数据 (push2his.eastmoney.com 用 curl 直连)
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    all_dates = []
    for etf in etf_basic_list:
        code = etf["code"]
        secid = f"1.{code}"
        try:
            url = (
                f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
                f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
                f"&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
                f"&klt=101&fqt=0&beg={start_date}&end={end_date}"
            )
            data = _fetch_json(url, referer="https://quote.eastmoney.com/")
            klines = (data.get("data") or {}).get("klines") or []
            records = []
            for line in klines:
                parts = line.split(",")
                if len(parts) < 6: continue
                date_str = parts[0]
                if date_str not in all_dates:
                    all_dates.append(date_str)
                records.append({
                    "code": code,
                    "date": date_str,
                    "open": _safe_float(parts[1]),
                    "close": _safe_float(parts[2]),
                    "high": _safe_float(parts[3]),
                    "low": _safe_float(parts[4]),
                    "volume": _safe_float(parts[5]),
                    "total_shares": None,
                    "turnover": _safe_float(parts[10]) if len(parts) > 10 else None,
                })
            if records:
                await upsert_etf_daily(records)
        except Exception as e:
            print(f"Failed history for {code} {etf['name']}: {e}")

    # 3. 从上交所 API 拉取历史份额数据
    all_dates.sort()
    sample_dates = all_dates[::5]
    if all_dates and all_dates[-1] not in sample_dates:
        sample_dates.append(all_dates[-1])

    shares_map = {code: {} for code in etf_codes}
    for date_str in sample_dates:
        try:
            d = date_str.replace("-", "")
            data_str = "-".join([d[:4], d[4:6], d[6:]])
            url = (
                f"https://query.sse.com.cn/commonQuery.do?"
                f"isPagination=true&pageHelp.pageSize=10000&pageHelp.pageNo=1"
                f"&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=1"
                f"&sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L&STAT_DATE={d}"
            )
            text = subprocess.run(
                ["curl", "-s", "--noproxy", "*", "--max-time", "15",
                 "-H", "Referer: https://www.sse.com.cn/", url],
                capture_output=True, text=True, timeout=20
            ).stdout
            if not text: continue
            data = json.loads(text)
            for item in data.get("result", []):
                code = str(item.get("SEC_CODE", ""))
                if code in etf_codes:
                    shares_map[code][date_str] = float(item.get("TOT_VOL", 0))
        except Exception as e:
            print(f"Failed SSE scale for {date_str}: {e}")

    for etf in etf_basic_list:
        latest_shares = None
        for d in sorted(shares_map.get(etf["code"], {}).keys(), reverse=True):
            if shares_map[etf["code"]][d] is not None:
                latest_shares = shares_map[etf["code"]][d]; break
        etf["total_shares"] = latest_shares

    await upsert_etf_basic(etf_basic_list)

    # 插值填充到 etf_daily.total_shares
    from backend.database import update_etf_shares
    for code in etf_codes:
        s_map = shares_map[code]
        if not s_map: continue
        sorted_keys = sorted(s_map.keys())
        share_records = []
        for date_str in all_dates:
            if date_str in s_map:
                shares = s_map[date_str]
            else:
                prev_date, prev_val = None, None
                next_date, next_val = None, None
                for d in sorted_keys:
                    if d <= date_str: prev_date, prev_val = d, s_map[d]
                for d in sorted_keys:
                    if d >= date_str and next_date is None: next_date, next_val = d, s_map[d]
                if prev_val is not None and next_val is not None and prev_date != next_date:
                    try:
                        ratio = (all_dates.index(date_str) - all_dates.index(prev_date)) / max(
                            all_dates.index(next_date) - all_dates.index(prev_date), 1)
                        shares = prev_val + (next_val - prev_val) * ratio
                    except ValueError:
                        shares = prev_val
                elif prev_val is not None: shares = prev_val
                elif next_val is not None: shares = next_val
                else: shares = None
            share_records.append({"code": code, "date": date_str, "total_shares": shares})
        await update_etf_shares(share_records)

    return len(etf_basic_list)


async def fetch_and_store_index_data(symbol="000001", table="index"):
    """拉取指数日线数据"""
    from backend.database import upsert_index_daily, init_db

    await init_db()
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    end_date = datetime.now().strftime("%Y%m%d")

    secid = f"1.{symbol}" if symbol == "000001" else f"1.{symbol}"
    try:
        url = (
            f"https://push2his.eastmoney.com/api/qt/stock/kline/get?"
            f"secid={secid}&fields1=f1,f2,f3,f4,f5,f6"
            f"&fields2=f51,f52,f53,f54,f55,f56,f57"
            f"&klt=101&fqt=0&beg={start_date}&end={end_date}"
        )
        data = _fetch_json(url, referer="https://quote.eastmoney.com/")
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
            })
        if symbol == "000300":
            from backend.database import upsert_hs300_daily
            await upsert_hs300_daily(records)
        else:
            await upsert_index_daily(records)
        return len(records)
    except Exception as e:
        print(f"Failed index {symbol}: {e}")
        return 0


async def fetch_and_store_hs300_data():
    return await fetch_and_store_index_data(symbol="000300", table="hs300")
