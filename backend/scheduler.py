import threading
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()


def _scheduled_refresh():
    """在独立线程中运行刷新, 避免阻塞事件循环"""
    import asyncio
    from backend.fetcher import fetch_and_store_etf_data, fetch_and_store_index_data, fetch_and_store_hs300_data
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(fetch_and_store_etf_data())
        loop.run_until_complete(fetch_and_store_index_data())
        loop.run_until_complete(fetch_and_store_hs300_data())
    finally:
        loop.close()


def setup_scheduler():
    """配置定时任务：每个交易日 15:30 (收盘后) 刷新数据"""
    scheduler.add_job(
        lambda: threading.Thread(target=_scheduled_refresh, daemon=True).start(),
        trigger="cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="fetch_etf_data",
        replace_existing=True,
    )
    scheduler.start()
    print("Scheduler started: Mon-Fri 15:30")
