# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

沪深 300ETF 持仓趋势分析网站。跟踪上交所前 7 大沪深 300ETF 的成交量、总份额，通过趋势图展示份额与上证指数的负相关关系，并提供基于阶段分析的交易操作指引。

## 启动命令

```bash
# 后端 (需要先 source venv)
source .venv/bin/activate
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 前端 (另一个终端)
cd frontend && npm run dev

# 测试 API
curl http://localhost:8000/api/etfs
curl http://localhost:8000/api/etfs/510300
curl http://localhost:8000/api/index
curl -X POST http://localhost:8000/api/refresh
```

后端运行在 `:8000`（Swagger 文档在 `/docs`），前端在 `:5173`，Vite 自动代理 `/api` 到后端。

## 架构

```
浏览器 (:5173)
    │
    ▼ Vite proxy /api → :8000
┌──────────────────────────┐
│ backend/main.py          │  FastAPI + lifespan (init DB + scheduler)
│   GET  /api/etfs         │  返回前7只ETF + 最新成交量
│   GET  /api/etfs/{code}  │  单只ETF日线 (OHLCV + 总份额)
│   GET  /api/index        │  上证指数日线
│   POST /api/refresh      │  手动触发数据拉取
└──────────┬───────────────┘
           │
    ┌──────┴──────┐
    │ database.py │  aiosqlite, 3张表: etf_basic / etf_daily / index_daily
    │ fetcher.py  │  AKShare 数据源: fund_etf_fund_daily_em + fund_etf_hist_em + fund_etf_scale_sse + index_zh_a_hist
    │ scheduler.py│  APScheduler, 交易日 15:30 自动刷新
    └─────────────┘
```

## 数据流

1. **启动时**：`lifespan` 检查 DB 是否为空，若空则调用 `fetch_and_store_etf_data()` + `fetch_and_store_index_data()`
2. **ETF 份额获取**：先通过 `fund_etf_fund_daily_em()` 获取 ETF 列表 → 过滤上交所(5开头) → 按代码排序取前7 → 用 `fund_etf_hist_em()` 拉每只日线 → 用 `fund_etf_scale_sse()` 按周抽样拉历史份额 → 线性插值填充 → `update_etf_shares()` 仅更新份额列（不覆盖 OHLCV）
3. **定时刷新**：每周一至五 15:30 自动触发，仅刷新 ETF 数据（不含指数）
4. **`update_etf_shares` 是关键**：它用 `UPDATE` 而非 `INSERT OR REPLACE`，确保拉取份额数据时不会把 OHLCV 覆盖为 NULL

## 关键细节

- **代理问题**：`fetcher.py` 启动时清除 `http_proxy`/`https_proxy` 环境变量，因为国内金融 API 走代理会超时
- **aiosqlite 版本**：0.22+ 中 `connect()` 返回的 Connection 既可 await 也是 async context manager，不能用 `async def get_db()` + `async with`，必须用 `def get_db()` + `async with`
- **row_factory**：必须在 `async with` 块内设置，因为底层 sqlite3 connection 在该块进入前不存在
- **前端阶段分析**：TrendChart 图1 的 `phaseData` 基于全部历史数据计算 10 日滚动份额变化，再截取 selected range。阶段阈值用分位数动态计算。ReferenceArea 只在连续 3+ 天同阶段时显示
- **激进卖出点**：在赎回阶段内找指数创新高的日期标记为卖出信号（分位 15%，比保守的 30% 更敏感）
- **CORS**：只允许 `localhost:5173`，多开 Vite 端口时需更新

## 分析结论（已存档）

`docs/analysis/etf-shares-vs-index.md` — 完整回测报告：
- ETF 总份额与上证指数强负相关 (r=-0.6~-0.96)，份额滞后指数约 1 个月
- 日级别份额变化是噪声，不可用于短线交易
- 连续 5+ 天极端信号有价值（正收益概率 60-100%）
- 获利赎回阶段 ≠ 卖出信号（减仓跑输满仓）
- 成交量与份额无显著相关，不纳入操作框架
