from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.fetcher import fetch_and_store_etf_data

scheduler = AsyncIOScheduler()


def setup_scheduler():
    """配置定时任务：每个交易日 15:30 (收盘后) 刷新数据"""
    scheduler.add_job(
        lambda: fetch_and_store_etf_data(),
        trigger="cron",
        day_of_week="mon-fri",
        hour=15,
        minute=30,
        id="fetch_etf_data",
        replace_existing=True,
    )
    scheduler.start()
