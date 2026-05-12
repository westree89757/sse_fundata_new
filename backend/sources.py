"""多数据源分级容错: mootdx > 腾讯财经 > 新浪/AKShare"""

import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MOOTDX_SERVER = "110.41.147.114:7709"
MOOTDX_OFFSET = 320
TENCENT_TIMEOUT = 10


def _safe_float(val) -> float | None:
    if val is None: return None
    try: return float(str(val).replace("%", ""))
    except (ValueError, TypeError): return None


# ── mootdx (通达信) ──────────────────────────────────────────

def _mootdx_etf(code: str, start: str, end: str) -> list[dict] | None:
    """mootdx ETF 日线: bars(frequency=9) 返回 OHLCV + amount"""
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std", server=MOOTDX_SERVER)
        df = client.bars(symbol=code, frequency=9, offset=MOOTDX_OFFSET)
        if df is None or df.empty:
            return None
        records = []
        for _, row in df.iterrows():
            date_str = f"{int(row['year']):04d}-{int(row['month']):02d}-{int(row['day']):02d}"
            if date_str < start or date_str > end:
                continue
            vol = _safe_float(row.get("volume") or row.get("vol"))
            # mootdx freq=9 返回手(100股), 统一转为股以匹配 Sina/腾讯格式
            records.append({
                "date": date_str,
                "open": _safe_float(row.get("open")),
                "close": _safe_float(row.get("close")),
                "high": _safe_float(row.get("high")),
                "low": _safe_float(row.get("low")),
                "volume": vol * 100 if vol else None,
                "amount": _safe_float(row.get("amount")),
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"mootdx ETF {code}: {e}")
        return None


def _mootdx_index(symbol: str, start: str, end: str) -> list[dict] | None:
    """mootdx 指数日线: index_bars(frequency=9)"""
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market="std", server=MOOTDX_SERVER)
        df = client.index_bars(symbol=symbol, frequency=9, offset=MOOTDX_OFFSET)
        if df is None or df.empty:
            return None
        records = []
        for _, row in df.iterrows():
            date_str = f"{int(row['year']):04d}-{int(row['month']):02d}-{int(row['day']):02d}"
            if date_str < start or date_str > end:
                continue
            vol = _safe_float(row.get("volume") or row.get("vol"))
            records.append({
                "date": date_str,
                "open": _safe_float(row.get("open")),
                "close": _safe_float(row.get("close")),
                "high": _safe_float(row.get("high")),
                "low": _safe_float(row.get("low")),
                "volume": vol * 100 if vol else None,
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"mootdx index {symbol}: {e}")
        return None


# ── 腾讯财经 API ─────────────────────────────────────────────
# ETF: 响应键 "qfqday", 指数: "day"
# 格式 [date, open, close, high, low, volume] — close 在索引 2, 非常规顺序

def _tencent_etf(code: str, start: str, end: str) -> list[dict] | None:
    try:
        import requests
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh{code},day,,,320,qfq"
        r = requests.get(url, timeout=TENCENT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        rows = data.get("data", {}).get(f"sh{code}", {}).get("qfqday")
        if not rows:
            return None
        records = []
        for row in rows:
            date_str = str(row[0])
            if date_str < start or date_str > end:
                continue
            records.append({
                "date": date_str,
                "open": _safe_float(row[1]),
                "close": _safe_float(row[2]),
                "high": _safe_float(row[3]),
                "low": _safe_float(row[4]),
                "volume": _safe_float(row[5]),
                "amount": None,  # 腾讯无成交额
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"tencent ETF {code}: {e}")
        return None


def _tencent_index(symbol: str, start: str, end: str) -> list[dict] | None:
    try:
        import requests
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh{symbol},day,,,320,qfq"
        r = requests.get(url, timeout=TENCENT_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        rows = data.get("data", {}).get(f"sh{symbol}", {}).get("day")  # 指数用 day
        if not rows:
            return None
        records = []
        for row in rows:
            date_str = str(row[0])
            if date_str < start or date_str > end:
                continue
            records.append({
                "date": date_str,
                "open": _safe_float(row[1]),
                "close": _safe_float(row[2]),
                "high": _safe_float(row[3]),
                "low": _safe_float(row[4]),
                "volume": _safe_float(row[5]),
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"tencent index {symbol}: {e}")
        return None


# ── 新浪财经 / AKShare ───────────────────────────────────────

def _sina_etf(code: str, start: str, end: str) -> list[dict] | None:
    try:
        import akshare as ak
        df = ak.fund_etf_hist_sina(symbol=f"sh{code}")
        if df.empty:
            return None
        df["date"] = df["date"].astype(str)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["date"]),
                "open": _safe_float(row["open"]),
                "close": _safe_float(row["close"]),
                "high": _safe_float(row["high"]),
                "low": _safe_float(row["low"]),
                "volume": _safe_float(row["volume"]),
                "amount": _safe_float(row.get("amount")),
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"sina ETF {code}: {e}")
        return None


def _akshare_index(symbol: str, start: str, end: str) -> list[dict] | None:
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol=f"sh{symbol}")
        if df.empty:
            return None
        df["date"] = df["date"].astype(str)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        records = []
        for _, row in df.iterrows():
            records.append({
                "date": str(row["date"]),
                "open": _safe_float(row["open"]),
                "close": _safe_float(row["close"]),
                "high": _safe_float(row["high"]),
                "low": _safe_float(row["low"]),
                "volume": _safe_float(row["volume"]),
            })
        return records if records else None
    except Exception as e:
        logger.warning(f"akshare index {symbol}: {e}")
        return None


# ── 分发器: 按优先级尝试，返回空列表表示全部失效 ──────────────

def fetch_etf_daily(code: str, start: str, end: str) -> list[dict]:
    sources = [
        ("mootdx", _mootdx_etf),
        ("tencent", _tencent_etf),
        ("sina", _sina_etf),
    ]
    for name, fn in sources:
        try:
            result = fn(code, start, end)
            if result is not None:
                logger.info(f"ETF {code}: {name} -> {len(result)} rows")
                return result
        except Exception as e:
            logger.warning(f"ETF {code} {name}: {e}")
    logger.error(f"ETF {code}: all sources failed")
    return []


def fetch_index_daily(symbol: str, start: str, end: str) -> list[dict]:
    sources = [
        ("mootdx", _mootdx_index),
        ("tencent", _tencent_index),
        ("akshare", _akshare_index),
    ]
    for name, fn in sources:
        try:
            result = fn(symbol, start, end)
            if result is not None:
                logger.info(f"Index {symbol}: {name} -> {len(result)} rows")
                return result
        except Exception as e:
            logger.warning(f"Index {symbol} {name}: {e}")
    logger.error(f"Index {symbol}: all sources failed")
    return []
