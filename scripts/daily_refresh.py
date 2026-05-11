"""GitHub Actions 每日刷新脚本
复用 backend/sources.py 的多源容错分发器 (mootdx > 腾讯 > Sina/AKShare)
生成 data/latest.json 供本地导入
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.sources import fetch_etf_daily, fetch_index_daily
import akshare as ak

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"]


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    end = today

    # 1. ETF 列表
    print("Fetching ETF list...")
    df = ak.fund_etf_fund_daily_em()
    mask = df["基金简称"].apply(lambda x: any(k in str(x) for k in CSI300_KEYWORDS))
    df_csi300 = df[mask].copy()
    df_csi300 = df_csi300[df_csi300["基金代码"].astype(str).str.startswith("5")]
    df_csi300 = df_csi300.sort_values("基金代码").head(7)
    codes = [str(c) for c in df_csi300["基金代码"].tolist()]
    etf_names = {str(c): str(n) for c, n in zip(df_csi300["基金代码"], df_csi300["基金简称"])}
    print(f"  {len(codes)} ETFs: {codes}")

    # 2. ETF 日线
    print("Fetching ETF daily...")
    etf_daily = {}
    for code in codes:
        rows = fetch_etf_daily(code, start, end)
        etf_daily[code] = rows
        print(f"  {code}: {len(rows)} rows")
        if not rows:
            print(f"  WARNING: {code} has no data!")

    # 3. 指数
    print("Fetching index daily...")
    index_000001 = fetch_index_daily("000001", start, end)
    index_000300 = fetch_index_daily("000300", start, end)
    print(f"  SSE: {len(index_000001)} rows, HS300: {len(index_000300)} rows")

    # 4. SSE 份额 (采样每 20 天)
    print("Fetching SSE shares...")
    first_code = codes[0] if codes else None
    all_dates = sorted(set(r["date"] for r in etf_daily.get(first_code, [])))
    sample_dates = all_dates[::20]
    if all_dates[-1] not in sample_dates:
        sample_dates.append(all_dates[-1])
    if all_dates[0] not in sample_dates:
        sample_dates.insert(0, all_dates[0])
    print(f"  Sampling {len(sample_dates)} dates")

    shares = {}
    for d in sample_dates:
        try:
            df_s = ak.fund_etf_scale_sse(date=d.replace("-", ""))
            if df_s is None or df_s.empty:
                print(f"  SSE {d}: empty")
                continue
            for _, row in df_s.iterrows():
                c = str(row.get("基金代码", ""))
                v = float(row["基金份额"]) if row.get("基金份额") else None
                if c in codes and v:
                    shares.setdefault(c, []).append({"date": d, "shares": v})
            print(f"  SSE {d}: OK")
        except Exception as e:
            print(f"  SSE {d}: {e}")

    result = {
        "generated": today,
        "etf_codes": codes,
        "etf_names": etf_names,
        "etf_daily": etf_daily,
        "index_000001": index_000001,
        "index_000300": index_000300,
        "shares": shares,
    }

    path = os.path.join(DATA_DIR, "latest.json")
    with open(path, "w") as f:
        json.dump(result, f, ensure_ascii=False)
    size_kb = os.path.getsize(path) / 1024
    print(f"Saved {size_kb:.0f}KB to {path}")


if __name__ == "__main__":
    main()
