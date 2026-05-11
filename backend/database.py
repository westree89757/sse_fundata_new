import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "etf_data.db")


def get_db():
    return aiosqlite.connect(DB_PATH)


async def init_db():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        await db.execute("""
            CREATE TABLE IF NOT EXISTS etf_basic (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                total_shares REAL,
                nav REAL,
                premium REAL,
                update_date TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS etf_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                date TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                total_shares REAL,
                turnover REAL,
                UNIQUE(code, date)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS hs300_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
        """)
        # 兼容已有数据库
        for col, table in [("turnover", "etf_daily"), ("premium", "etf_basic")]:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} REAL")
            except Exception:
                pass
        await db.execute("""
            CREATE TABLE IF NOT EXISTS index_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
        """)
        await db.commit()


async def upsert_etf_basic(etfs: list[dict]):
    async with get_db() as db:
        for etf in etfs:
            await db.execute("""
                INSERT OR REPLACE INTO etf_basic (code, name, total_shares, nav, premium, update_date)
                VALUES (?, ?, ?, ?, ?, date('now'))
            """, (etf["code"], etf["name"], etf.get("total_shares"), etf.get("nav"), etf.get("premium")))
        await db.commit()


async def upsert_etf_daily(records: list[dict]):
    async with get_db() as db:
        for r in records:
            await db.execute("""
                INSERT INTO etf_daily (code, date, open, high, low, close, volume, total_shares, turnover)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    turnover = excluded.turnover
            """, (r["code"], r["date"], r.get("open"), r.get("high"),
                  r.get("low"), r.get("close"), r.get("volume"), r.get("total_shares"), r.get("turnover")))
        await db.commit()


async def get_all_etfs():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT b.code, b.name, b.total_shares, b.nav, b.premium,
                   d.volume as latest_volume, d.date as latest_date
            FROM etf_basic b
            LEFT JOIN (
                SELECT code, volume, date
                FROM etf_daily
                WHERE (code, date) IN (
                    SELECT code, MAX(date) FROM etf_daily GROUP BY code
                )
            ) d ON b.code = d.code
            ORDER BY b.total_shares DESC
            LIMIT 7
        """)
        return [dict(row) for row in await rows.fetchall()]


async def get_etf_history(code: str):
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT code, date, open, high, low, close, volume, total_shares, turnover
            FROM etf_daily
            WHERE code = ?
            ORDER BY date ASC
        """, (code,))
        return [dict(row) for row in await rows.fetchall()]


async def update_etf_shares(records: list[dict]):
    """仅更新 total_shares 列，不覆盖 OHLCV 数据"""
    async with get_db() as db:
        for r in records:
            await db.execute("""
                UPDATE etf_daily SET total_shares = ?
                WHERE code = ? AND date = ?
            """, (r["total_shares"], r["code"], r["date"]))
        await db.commit()


async def upsert_index_daily(records: list[dict]):
    async with get_db() as db:
        for r in records:
            await db.execute("""
                INSERT OR REPLACE INTO index_daily (date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (r["date"], r.get("open"), r.get("high"),
                  r.get("low"), r.get("close"), r.get("volume")))
        await db.commit()


async def get_index_history():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT date, open, high, low, close, volume
            FROM index_daily
            ORDER BY date ASC
        """)
        return [dict(row) for row in await rows.fetchall()]


async def upsert_hs300_daily(records: list[dict]):
    async with get_db() as db:
        for r in records:
            await db.execute("""
                INSERT OR REPLACE INTO hs300_daily (date, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (r["date"], r.get("open"), r.get("high"),
                  r.get("low"), r.get("close"), r.get("volume")))
        await db.commit()


async def get_hs300_history():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT date, open, high, low, close, volume
            FROM hs300_daily
            ORDER BY date ASC
        """)
        return [dict(row) for row in await rows.fetchall()]


async def auto_import_from_json():
    """如果 data/latest.json 比 DB 数据更新，自动导入"""
    import json
    json_path = os.path.join(os.path.dirname(__file__), "..", "data", "latest.json")
    if not os.path.exists(json_path):
        return

    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        row = await db.execute("SELECT MAX(date) as latest FROM etf_daily")
        db_latest = (await row.fetchone())["latest"]

    with open(json_path) as f:
        data = json.load(f)

    json_date = data.get("generated", "")
    if db_latest and json_date <= db_latest:
        return  # DB 已经是最新

    print(f"Importing data/latest.json (generated={json_date}, DB latest={db_latest})...")

    # 导入 ETF 日线
    daily_records = []
    for code, rows in data.get("etf_daily", {}).items():
        for r in rows:
            daily_records.append({
                "code": code, "date": r["date"],
                "open": r.get("open"), "high": r.get("high"),
                "low": r.get("low"), "close": r.get("close"),
                "volume": r.get("volume"), "total_shares": None,
                "turnover": r.get("amount"),
            })
    if daily_records:
        await upsert_etf_daily(daily_records)
        print(f"  Imported {len(daily_records)} ETF daily rows")

    # 导入指数
    for symbol, table_func in [("000001", upsert_index_daily), ("000300", upsert_hs300_daily)]:
        key = f"index_{symbol}"
        records = data.get(key, [])
        if records:
            await table_func(records)
            print(f"  Imported {len(records)} {symbol} index rows")

    # 导入 SSE 份额
    shares = data.get("shares", {})
    if shares:
        # 构建日期列表
        all_dates = sorted(set(r["date"] for rows in data.get("etf_daily", {}).values() for r in rows))
        for code, entries in shares.items():
            s_map = {e["date"]: e["shares"] for e in entries}
            sorted_keys = sorted(s_map.keys())
            share_recs = []
            for date_str in all_dates:
                if date_str in s_map:
                    shares_val = s_map[date_str]
                else:
                    prev_d = prev_v = next_d = next_v = None
                    for d in sorted_keys:
                        if d <= date_str: prev_d, prev_v = d, s_map[d]
                    for d in sorted_keys:
                        if d >= date_str and next_d is None: next_d, next_v = d, s_map[d]
                    if prev_v is not None and next_v is not None and prev_d != next_d:
                        try:
                            ratio = (all_dates.index(date_str) - all_dates.index(prev_d)) / max(all_dates.index(next_d) - all_dates.index(prev_d), 1)
                            shares_val = prev_v + (next_v - prev_v) * ratio
                        except ValueError: shares_val = prev_v
                    elif prev_v is not None: shares_val = prev_v
                    elif next_v is not None: shares_val = next_v
                    else: shares_val = None
                share_recs.append({"code": code, "date": date_str, "total_shares": shares_val})
            if share_recs:
                await update_etf_shares(share_recs)
        print(f"  Imported SSE shares for {len(shares)} ETFs")

    # 更新 ETF basic 信息
    etf_names = data.get("etf_names", {})
    etf_basic_list = []
    for code in data.get("etf_codes", []):
        etf_basic_list.append({
            "code": code,
            "name": etf_names.get(code, code),
            "total_shares": None,
            "nav": None,
            "premium": None,
        })
    if etf_basic_list:
        await upsert_etf_basic(etf_basic_list)

    print("Auto-import complete")
