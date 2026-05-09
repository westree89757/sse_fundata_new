# 沪深300ETF 持仓趋势分析

跟踪上交所前 7 大沪深 300ETF 的成交量、份额变化，通过趋势图分析机构持仓行为，提供基于阶段分析的交易操作指引。

## 功能

- **全景概览** — 7 只 ETF 成交量、总份额、折溢价、5 日净流入、20 日份额变化、成交额一目了然，含大小票轮动比
- **阶段分析** — 基于 10 日滚动份额变化自动识别"机构增持"/"获利赎回"/"中性"三阶段，标注关键买卖信号
- **成交量与资金流向** — 日成交量和资金净流入（Δ份额 × 均价）双轴对比
- **份额 vs 指数日变化** — ETF 份额日变化与沪深 300 指数日变化的相关系数，验证负相关关系
- **预警通知** — 汇总 7 只 ETF 综合信号，≥4 只同阶段触发强信号横幅
- **操作指引** — 基于历史回测的策略建议（增持→分批建仓、赎回≠卖出、连续 5 天极端信号高可信）
- **定时刷新** — 每个交易日 15:30 自动拉取最新数据

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python FastAPI + aiosqlite |
| 数据源 | AKShare (Sina 财经 / 东方财富 / 上证 API) |
| 前端 | React 18 + Vite + Recharts |
| 定时 | APScheduler |

## 快速开始

```bash
# 1. 后端
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 2. 前端 (新终端)
cd frontend
npm install
npm run dev

# 3. 初始化数据
curl -X POST http://localhost:8000/api/refresh
```

打开 `http://localhost:5173`，前端 Vite 自动代理 `/api` 到后端 `:8000`。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/etfs` | ETF 列表 + 最新成交量 |
| GET | `/api/etfs/{code}` | 单只 ETF 日线 (OHLCV + 份额 + 成交额) |
| GET | `/api/index` | 上证指数日线 |
| GET | `/api/hs300` | 沪深 300 指数日线 |
| POST | `/api/refresh` | 手动触发全量数据刷新 |

Swagger 文档：`http://localhost:8000/docs`

## 数据流

```
AKShare → fetcher.py → SQLite (etf_daily/index_daily/hs300_daily)
                         │
                    FastAPI (:8000)
                         │
                   Vite proxy /api
                         │
                    React (:5173)
```

- ETF 日线: `ak.fund_etf_hist_sina()` (新浪财经)
- ETF 列表: `ak.fund_etf_fund_daily_em()` (东方财富基金频道)
- 指数日线: `ak.stock_zh_index_daily()` (Sina)
- SSE 份额: `ak.fund_etf_scale_sse()` (上交所)
- 份额插值：按周抽样 SSE 份额，线性插值填充每日份额

## 阶段判定规则

| 信号 | 条件 | 操作建议 |
|------|------|----------|
| 机构增持 | 10 日滚动份额变化 > 70 分位 | 分批建仓 |
| 获利赎回 | 10 日滚动份额变化 < 30 分位 | 继续持有（非卖出信号） |
| 中性 | 介于两者之间 | 耐心等待 |
| 连续 5 天极端信号 | 连续 5+ 天处于极端区间 | 高可信度信号 |
| 激进卖出 | 赎回阶段内指数创新高 | 可考虑减仓 |

## 分析结论

详见 `docs/analysis/etf-shares-vs-index.md`：

- ETF 总份额与指数强负相关 (r = -0.6 ~ -0.96)，份额滞后约 1 个月
- 日级别份额变化是噪声，不可用于短线交易
- 获利赎回阶段 ≠ 卖出信号（减仓跑输满仓 +23.4% vs +18.5%）
- 成交量与份额无显著相关

## 注意事项

- **代理**：如使用系统代理（Clash/V2Ray），需确保 `127.0.0.1:7897` 可访问或调整代理配置
- **数据源**：东方财富 `push2his.eastmoney.com` 自 2025 年底加强反爬，项目已迁移至 Sina 财经 + SSE API
- **首次启动**：后端不再自动拉取数据，需手动 `POST /api/refresh`（约 1-2 分钟）
