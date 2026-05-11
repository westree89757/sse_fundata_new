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
