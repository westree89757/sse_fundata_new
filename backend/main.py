import asyncio
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db, get_all_etfs, get_etf_history, get_index_history, get_hs300_history
from backend.models import ETFListResponse, ETFBasicResponse, ETFDaily, IndexDaily
from backend.scheduler import setup_scheduler
from backend.fetcher import fetch_and_store_etf_data, fetch_and_store_index_data, fetch_and_store_hs300_data

_refreshing = False
_refresh_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_scheduler()
    yield


app = FastAPI(title="沪深300ETF 持仓趋势", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/etfs", response_model=ETFListResponse)
async def list_etfs():
    etfs = await get_all_etfs()
    return ETFListResponse(etfs=[ETFBasicResponse(**e) for e in etfs])


@app.get("/api/etfs/{code}")
async def etf_history(code: str):
    records = await get_etf_history(code)
    return [ETFDaily(**r) for r in records]


@app.get("/api/index")
async def index_history():
    records = await get_index_history()
    return [IndexDaily(**r) for r in records]


@app.get("/api/hs300")
async def hs300_history():
    records = await get_hs300_history()
    return [IndexDaily(**r) for r in records]


def _run_refresh_in_thread():
    """在独立线程中运行数据刷新，避免阻塞事件循环"""
    global _refreshing
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(fetch_and_store_etf_data())
        loop.run_until_complete(fetch_and_store_index_data())
        loop.run_until_complete(fetch_and_store_hs300_data())
    finally:
        loop.close()
        _refreshing = False


@app.post("/api/refresh")
async def refresh_data():
    global _refreshing
    if _refreshing:
        return {"status": "already_refreshing"}
    _refreshing = True
    threading.Thread(target=_run_refresh_in_thread, daemon=True).start()
    return {"status": "started"}


@app.get("/api/refresh/status")
async def refresh_status():
    return {"refreshing": _refreshing}


@app.get("/api/scheduler/status")
async def scheduler_status():
    from backend.scheduler import scheduler
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({"id": job.id, "next_run": str(job.next_run_time)})
    return {"running": scheduler.running, "jobs": jobs}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
