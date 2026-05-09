from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db, get_all_etfs, get_etf_history, get_index_history, get_hs300_history
from backend.models import ETFListResponse, ETFBasicResponse, ETFDaily, IndexDaily
from backend.scheduler import setup_scheduler
from backend.fetcher import fetch_and_store_etf_data, fetch_and_store_index_data, fetch_and_store_hs300_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_scheduler()
    # 启动时尝试拉取一次数据(如果DB为空)
    try:
        etfs = await get_all_etfs()
        if not etfs:
            await fetch_and_store_etf_data()
        idx = await get_index_history()
        if not idx:
            await fetch_and_store_index_data()
        hs300 = await get_hs300_history()
        if not hs300:
            await fetch_and_store_hs300_data()
    except Exception:
        pass
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


@app.post("/api/refresh")
async def refresh_data():
    count = await fetch_and_store_etf_data()
    idx_count = await fetch_and_store_index_data()
    hs300_count = await fetch_and_store_hs300_data()
    return {"status": "ok", "etf_count": count, "index_count": idx_count, "hs300_count": hs300_count}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
