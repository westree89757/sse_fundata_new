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
│   GET  /api/etfs/{code}  │  单只ETF日线 (OHLCV + 总份额 + 成交额)
│   GET  /api/index        │  上证指数日线
│   GET  /api/hs300        │  沪深300指数日线
│   POST /api/refresh      │  后台线程触发数据拉取 (不阻塞)
│   GET  /api/refresh/status│ 查询刷新状态
└──────────┬───────────────┘
           │
    ┌──────┴──────────┐
    │ sources.py      │  多数据源分级容错: mootdx > 腾讯财经 > 新浪
    │ database.py     │  aiosqlite, 4表: etf_basic / etf_daily / index_daily / hs300_daily
    │ fetcher.py      │  编排数据拉取 + SSE份额插值
    │ scheduler.py    │  APScheduler, 交易日 15:30 自动刷新
    └─────────────────┘
```

## 数据源优先级

| 数据需求 | 优先级 1 | 优先级 2 | 优先级 3 |
|---------|---------|---------|---------|
| ETF 日K线 | mootdx (通达信协议, TCP) | 腾讯财经 API (HTTPS) | 新浪财经 AKShare |
| 指数日K线 | mootdx `index_bars()` | 腾讯财经 API | AKShare |
| ETF 列表 | AKShare `fund_etf_fund_daily_em()` | — | — |
| SSE 份额 | AKShare `fund_etf_scale_sse()` | — | — |

- **mootdx**: 服务器 `110.41.147.114:7709`（需显式传入，bestip 配置有 bug），频率 9=日线，每次拉 320 条后按日期过滤。返回 OHLCV + amount（成交额）
- **腾讯财经**: `web.ifzq.gtimg.cn`，密钥注意 ETF 用 `qfqday`、指数用 `day`，格式 `[date, open, close, high, low, volume]` — close 在索引 2！
- **降级行为**: mootdx 不可用 → 腾讯（无成交额）→ 新浪/AKShare（可能因 Python 3.14 py-mini-racer 不兼容失败）
- **SSE 份额**: 仅 AKShare 可用，每次约 10s，采样从每 5 天改为每 20 天（14 次调用）

## 数据流

1. **启动时**：`lifespan` 初始化 DB + 启动定时器，不再自动拉取数据（避免阻塞启动）
2. **手动刷新**：`POST /api/refresh` 在独立线程执行，立即返回 `{"status": "started"}`，前端轮询 `/api/refresh/status` 完成后自动刷新页面
3. **ETF 数据拉取**：`fund_etf_fund_daily_em()` 获取列表 → 过滤上交所(5开头) → 按代码排序取前7 → mootdx `bars()` 拉每只日线 → `fund_etf_scale_sse()` 每 20 天采样份额 → 线性插值填充 → `update_etf_shares()` 仅更新份额列
4. **`upsert_etf_daily`**: 使用 `INSERT ... ON CONFLICT DO UPDATE` 仅覆盖 OHLCV + turnover，**保留已有 total_shares**，避免每次刷新清空份额
5. **定时刷新**：每周一至五 15:30

## 关键细节

- **数据刷新不阻塞**：`fetcher.py` 在独立 daemon 线程中运行，避免阻塞 FastAPI 事件循环。`_refreshing` 全局标志防止并发刷新
- **aiosqlite 版本**：0.22+ 中 `connect()` 返回的 Connection 既可 await 也是 async context manager，不能用 `async def get_db()` + `async with`，必须用 `def get_db()` + `async with`
- **row_factory**：必须在 `async with` 块内设置，因为底层 sqlite3 connection 在该块进入前不存在
- **前端阶段分析**：TrendChart 图1 的 `phaseData` 基于全部历史数据计算 10 日滚动份额变化，再截取 selected range。阶段阈值用分位数动态计算。ReferenceArea 只在连续 3+ 天同阶段时显示
- **PhaseTooltip**: 鼠标悬停显示：当前阶段、ETF涨跌%/沪深300累计%/跟踪误差%、**距最近获利赎回起点的收益**、距最近机构增持起点的收益
- **激进卖出点**：在赎回阶段内找指数创新高的日期标记为卖出信号（分位 15%，比保守的 30% 更敏感）
- **腾讯 API 密钥差异**：ETF 响应在 `qfqday` 键，指数在 `day` 键；格式 `[date, open, close, high, low, volume]` — close 在索引 2
- **mootdx 服务器**：硬编码 `110.41.147.114:7709`，`bestip` 配置为空字符串时回退逻辑有 bug，必须显式传入 server 参数
- **CORS**：只允许 `localhost:5173`，多开 Vite 端口时需更新

## 分析结论（已存档）

`docs/analysis/etf-shares-vs-index.md` — 完整回测报告：
- ETF 总份额与上证指数强负相关 (r=-0.6~-0.96)，份额滞后指数约 1 个月
- 日级别份额变化是噪声，不可用于短线交易
- 连续 5+ 天极端信号有价值（正收益概率 60-100%）
- 获利赎回阶段 ≠ 卖出信号（减仓跑输满仓）
- 成交量与份额无显著相关，不纳入操作框架
