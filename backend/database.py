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
                UNIQUE(code, date)
            )
        """)
        await db.commit()


async def upsert_etf_basic(etfs: list[dict]):
    async with get_db() as db:
        for etf in etfs:
            await db.execute("""
                INSERT OR REPLACE INTO etf_basic (code, name, total_shares, nav, update_date)
                VALUES (?, ?, ?, ?, date('now'))
            """, (etf["code"], etf["name"], etf.get("total_shares"), etf.get("nav")))
        await db.commit()


async def upsert_etf_daily(records: list[dict]):
    async with get_db() as db:
        for r in records:
            await db.execute("""
                INSERT OR REPLACE INTO etf_daily (code, date, open, high, low, close, volume, total_shares)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (r["code"], r["date"], r.get("open"), r.get("high"),
                  r.get("low"), r.get("close"), r.get("volume"), r.get("total_shares")))
        await db.commit()


async def get_all_etfs():
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        rows = await db.execute("""
            SELECT b.code, b.name, b.total_shares, b.nav,
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
            SELECT date, open, high, low, close, volume, total_shares
            FROM etf_daily
            WHERE code = ?
            ORDER BY date ASC
        """, (code,))
        return [dict(row) for row in await rows.fetchall()]
