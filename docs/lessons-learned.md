# 项目经验积累

本文档记录沪深300ETF 持仓趋势分析项目中每个优化、每次 Bug 修复的经验总结，供后续项目参考。

---

## 数据源可靠性

### 教训 1: 不要单一依赖一个数据源

**时间**: 2026-05-10  
**问题**: push2his.eastmoney.com 自 2025 年底加强 WAF 反爬，所有非浏览器请求返回空响应（Empty reply from server）  
**表现**: 数据刷新全部失败，7 只 ETF 的 K 线数据无法获取  
**修复**: 改为 Sina 财经 API (`ak.fund_etf_hist_sina`) 和 `ak.stock_zh_index_daily`  
**经验**:
- 金融数据 API 随时可能被封禁或升级反爬
- 必须预设多个备用数据源，自动降级
- `push2his` 系列 API（东方财富）不稳定，不建议作为生产依赖

### 教训 2: 建立多源分级容错机制

**时间**: 2026-05-12  
**问题**: Sina API 依赖的 `py-mini-racer` 与 Python 3.14 不兼容，单用 Sina 仍然有风险  
**修复**: 创建 `backend/sources.py`，实现 mootdx(通达信) > 腾讯财经 > Sina/AKShare 三级降级  
**经验**:
- 优先使用协议级数据源（mootdx TCP 协议），不受 HTTP 反爬影响
- 腾讯财经 API (`web.ifzq.gtimg.cn`) 是纯 HTTPS，无需额外依赖，速度快
- 每个源函数返回 `None` 表示不可用，调用方自动尝试下一级
- 不同源的数据格式可能不同（腾讯 API 字段顺序为 [date, open, close, high, low, volume]，非标准），必须仔细验证

### 教训 3: 注意数据源字段顺序差异

**时间**: 2026-05-12  
**问题**: 腾讯财经 API 的 K 线数据字段顺序与标准不同：`[date, open, close, high, low, volume]` — `close` 在索引 2，`high` 在索引 3  
**修复**: 在 `_tencent_etf` 和 `_tencent_index` 中显式按索引映射字段  
**经验**:
- 每个新数据源必须逐字段验证映射关系
- HTTP API 的响应键名可能有差异（ETF 用 `qfqday`，指数用 `day`）

---

## 数据库设计

### 教训 4: INSERT OR REPLACE 会覆盖不需要更新的列

**时间**: 2026-05-11  
**问题**: 每次刷新数据后，ETF 日线的 `total_shares`（总份额）全部变为 NULL  
**根因**: `upsert_etf_daily` 使用 `INSERT OR REPLACE`，每次写入会把已通过插值计算好的份额数据覆盖为 NULL（写入时 `total_shares=None`）  
**修复**: 改为 `INSERT ... ON CONFLICT(code, date) DO UPDATE SET open=..., high=..., ...` 仅覆盖 OHLCV 列，保留 `total_shares`  
**经验**:
- `INSERT OR REPLACE` 是整行替换，不是字段级合并
- 如果某些字段通过不同流程异步写入（如份额通过 SSE API 单独插值），必须用 `ON CONFLICT DO UPDATE` 只覆盖相关列
- SQLite 的 `ON CONFLICT` 子句从 3.24.0 开始支持

---

## 事件循环与并发

### 教训 5: async def 内部调用同步阻塞函数会卡死事件循环

**时间**: 2026-05-11  
**问题**: 点击"刷新数据"后整个网站卡死，所有 API 无响应  
**根因**: `POST /api/refresh` 是 `async def`，但内部 AKShare 函数（`fund_etf_hist_sina` 等）是同步阻塞调用（底层用 `requests` 库），在 FastAPI 单线程事件循环中占满 60-120 秒  
**修复**: 刷新逻辑移到独立 `threading.Thread`（daemon），API 立即返回 `{"status": "started"}`，前端轮询 `/api/refresh/status`  
**经验**:
- Python async/await 是协作式调度，一个阻塞调用会卡死整个事件循环
- 任何可能超过 1 秒的同步操作（网络请求、文件 I/O）都必须放到线程/进程池
- 后台任务需要状态端点供前端轮询，不能只靠等待 HTTP 响应

### 教训 6: 定时器（APScheduler）也要避免阻塞事件循环

**时间**: 2026-05-12  
**问题**: 定时刷新（交易日 15:30）的 job 直接在 AsyncIOScheduler 中调用 `async def fetch_and_store_etf_data()`，同样会阻塞事件循环  
**修复**: 定时 job 改为启动 daemon thread，与手动刷新共用同一个线程执行逻辑  
**经验**:
- APScheduler 的 `AsyncIOScheduler` 在同一个事件循环中执行 job
- 任何可能阻塞的 job 都必须放到独立线程
- 需要添加状态端点 (`/api/scheduler/status`) 来监控定时器健康

---

## 前端状态管理

### 教训 7: 变量重命名遗漏会导致 ReferenceError

**时间**: 2026-05-10  
**问题**: 全景概览部分 ETF 卡片一直显示"加载中..."  
**根因**: 重命名 `turnover` 变量为 `amountYi` 后，`results[etf.code] = {...}` 中仍然引用了旧变量名 `turnover`，导致 `ReferenceError`，fetch 异常被 catch 捕获但 catch 没有写数据到 state  
**修复**: 修正变量引用，同时 catch 中也写入兜底状态（phase="无数据"）  
**经验**:
- JavaScript 的未声明变量引用是 `ReferenceError`，会在运行时静默失败
- 错误处理（`.catch()`）必须写入可降级展示的默认值，不能让 UI 永远停在 loading 状态
- IDE 的未使用变量警告可以帮助发现此类问题

### 教训 8: React useEffect 的依赖数组要正确

**时间**: 多次出现  
**问题**: OverviewPanel 在 `etfs` 变化时重新 fetch 所有 ETF 历史数据，但如果 `etfs` 对象引用未变（如首次加载为空数组），不会重新触发  
**修复**: 使用 `useEffect(() => {...}, [etfs])` 监听 `etfs` 变化  
**经验**:
- `useEffect` 第二个参数是浅比较引用，不是深比较值
- 数据加载的时序问题（先渲染空列表，再填充数据）需要用 loading/empty 状态区分

---

## 部署运维

### 教训 9: 本地定时器不可靠，需要外部触发

**时间**: 2026-05-12  
**问题**: 个人电脑长时间不动会进入睡眠，APScheduler 的 15:30 定时任务无法触发  
**修复**: 创建 GitHub Actions workflow，每天 UTC 08:00（CST 16:00）自动运行刷新脚本，数据以 JSON 格式提交回仓库  
**经验**:
- 本地 cron/scheduler 依赖机器持续运行，不适合个人电脑
- GitHub Actions 免费额度足够日常使用（公开仓库无限）
- 需要将数据序列化（JSON）才能在 Git 中版本控制
- `data/latest.json` 约 267KB，对于 Git 来说体积合理

### 教训 10: GitHub Personal Access Token 需要 workflow scope

**时间**: 2026-05-12  
**问题**: `git push` 被 GitHub 拒绝：`refusing to allow a Personal Access Token to create or update workflow without workflow scope`  
**修复**: 需要更新 GitHub PAT，勾选 `workflow` 权限 scope  
**经验**:
- GitHub 对 `.github/workflows/` 目录有特殊保护
- 推送 workflow 文件需要 PAT 有 `workflow` scope
- Classic token 和 Fine-grained token 的权限配置方式不同

### 教训 11: Git 推送可能因 SSL 连接失败

**时间**: 2026-05-11 ~ 05-12  
**问题**: 多次 `git push` 失败：`LibreSSL SSL_connect: SSL_ERROR_SYSCALL in connection to github.com:443`  
**原因**: 网络环境（代理/VPN）间歇性阻断到 GitHub 的 HTTPS 连接  
**应对**: 重试通常能解决；SSH 备用但需要配置 SSH key  
**经验**:
- GitHub HTTPS 在某些网络环境下不稳定
- 可以同时配置 HTTPS 和 SSH 两个 remote 互为备份
- `GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"` 可以跳过 SSH 主机验证

---

## 数据分析

### 教训 12: 日级别份额变化是噪声

**时间**: 项目初期分析阶段  
**结论**: ETF 日级别的总份额变化波动剧烈，不可用于短线交易判断  
**经验**:
- 需要滚动窗口（10 日≈2 周）平滑处理
- 连续 5+ 天极端信号才有参考价值（正收益概率 60-100%）
- 获利赎回 ≠ 卖出信号（历史回测：减仓跑输满仓 +23.4% vs +18.5%）

### 教训 13: 分位数阈值比固定阈值更鲁棒

**时间**: 阶段分析功能开发  
**结论**: 增持/赎回阶段的阈值使用滚动变化的 70/30 分位数动态计算，而非固定百分比  
**经验**:
- 不同 ETF 的份额变化幅度差异大，固定阈值不通用
- 分位数自适应各 ETF 的历史波动特征
- 极端分位（如 15% 分位卖出信号）需要比保守分位（30%）更谨慎使用

---

## 代码架构

### 教训 14: 前后端数据一致性需要端到端验证

**时间**: 多次出现  
**问题**: 后端 API 返回正常，但前端显示为空或错误  
**根因**: Vite 代理重启期间 `ECONNREFUSED`，前端缓存了错误状态  
**修复**: 硬刷新（Cmd+Shift+R），关闭浏览器缓存  
**经验**:
- 排查问题时先验证每一层：直接 curl 后端 → curl Vite 代理 → 浏览器 Network 面板
- 浏览器可能缓存失败的 API 响应，需要硬刷新
- 在开发环境勾选 DevTools Network → "Disable cache"

### 教训 15: 文件清理要彻底

**时间**: 项目演进阶段  
**问题**: 前端存在不再引用的旧组件文件（ETFCard.jsx, ETFGrid.jsx），容易误导维护者  
**经验**:
- 重构后应立即删除不再使用的文件
- `grep` 检查引用确保没有残留 import
- Git 历史可以恢复，不必保留未使用代码
