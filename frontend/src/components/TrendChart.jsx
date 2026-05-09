import { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
  ReferenceDot,
} from "recharts";

// 周维度: 4周≈20交易日, 13周≈65, 26周≈130
const RANGE_OPTIONS = { 20: "近4周", 65: "近13周", 130: "近26周" };
const ROLLING = 10; // 2周滚动窗口判断阶段

function CompareTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0].payload;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-date">{label}</div>
      <div className="tooltip-row">
        <span className="tooltip-label">总份额</span>
        <span className="tooltip-val">{data["份额(亿份)"]?.toFixed(2)} 亿份</span>
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label">份额变化</span>
        <span className="tooltip-val" style={{ color: data["份额变化%"] >= 0 ? "#10b981" : "#ef4444" }}>
          {data["份额变化%"] > 0 ? "+" : ""}{data["份额变化%"]}%
        </span>
      </div>
      <div className="tooltip-divider" />
      <div className="tooltip-row">
        <span className="tooltip-label">上证指数</span>
        <span className="tooltip-val">{data["上证指数"]?.toFixed(0)} 点</span>
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label">指数变化</span>
        <span className="tooltip-val" style={{ color: data["指数变化%"] >= 0 ? "#ef4444" : "#10b981" }}>
          {data["指数变化%"] > 0 ? "+" : ""}{data["指数变化%"]}%
        </span>
      </div>
    </div>
  );
}

function PhaseTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;
  const data = payload[0].payload;
  return (
    <div className="custom-tooltip">
      <div className="tooltip-date">{label}</div>
      <div className="tooltip-row">
        <span className="tooltip-label">阶段</span>
        <span className="tooltip-val">{data["阶段"] || "—"}</span>
      </div>
      <div className="tooltip-divider" />
      <div className="tooltip-row">
        <span className="tooltip-label" style={{ color: "#10b981" }}>ETF涨跌</span>
        <span className="tooltip-val" style={{ color: "#10b981" }}>
          {data["ETF累计%"] > 0 ? "+" : ""}{data["ETF累计%"]}%
        </span>
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label" style={{ color: "#ef4444" }}>沪深300累计</span>
        <span className="tooltip-val" style={{ color: "#ef4444" }}>
          {data["指数累计%"] > 0 ? "+" : ""}{data["指数累计%"]}%
        </span>
      </div>
      <div className="tooltip-row">
        <span className="tooltip-label" style={{ color: "#94a3b8" }}>跟踪误差</span>
        <span className="tooltip-val" style={{ color: data["跟踪误差%"] > 0 ? "#ef4444" : "#10b981" }}>
          {data["跟踪误差%"] > 0 ? "+" : ""}{data["跟踪误差%"]}%
        </span>
      </div>
      {data["增持起点"] && (
        <>
          <div className="tooltip-divider" />
          <div className="tooltip-date" style={{ fontSize: 11, fontWeight: 400, color: "#64748b", marginBottom: 2 }}>
            自 {data["增持起点"]} 机构增持以来
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label" style={{ color: "#10b981" }}>ETF涨跌</span>
            <span className="tooltip-val" style={{ color: data["增持起点收益ETF%"] >= 0 ? "#10b981" : "#ef4444" }}>
              {data["增持起点收益ETF%"] > 0 ? "+" : ""}{data["增持起点收益ETF%"]}%
            </span>
          </div>
          <div className="tooltip-row">
            <span className="tooltip-label" style={{ color: "#ef4444" }}>沪深300收益</span>
            <span className="tooltip-val" style={{ color: data["增持起点收益指数%"] >= 0 ? "#ef4444" : "#10b981" }}>
              {data["增持起点收益指数%"] > 0 ? "+" : ""}{data["增持起点收益指数%"]}%
            </span>
          </div>
        </>
      )}
    </div>
  );
}

export default function TrendChart({ data, etfName, indexData, szIndexData }) {
  const [days, setDays] = useState(65);  // 默认近13周

  // HS300 优先, 没有则 fallback 到上证
  const activeIndex = (indexData && indexData.length > 0) ? indexData : (szIndexData || []);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    const sliced = data.slice(-days);
    return sliced.map((d, i) => {
      const avgPrice = d.open && d.close ? (d.open + d.close) / 2 : 0;
      const prevShares = i > 0 && sliced[i - 1].total_shares ? sliced[i - 1].total_shares : 0;
      const currShares = d.total_shares || 0;
      const netFlow = i > 0 && prevShares && currShares
        ? +((currShares - prevShares) * avgPrice / 1e8).toFixed(3)  // 亿元
        : 0;
      return {
        date: d.date,
        成交量: d.volume ? +(d.volume / 10000).toFixed(2) : 0,
        总份额: d.total_shares ? +(d.total_shares / 1e8).toFixed(2) : 0,
        资金净流入: netFlow,
        成交额: d.turnover != null ? +(d.turnover / 1e8).toFixed(2) : 0,
      };
    });
  }, [data, days]);

  const compareData = useMemo(() => {
    if (!data || data.length === 0 || activeIndex.length === 0) return [];

    const etfMap = new Map();
    data.forEach((d) => { if (d.total_shares) etfMap.set(d.date, d.total_shares); });

    const indexMap = new Map();
    activeIndex.forEach((d) => { if (d.close) indexMap.set(d.date, d.close); });

    const commonDates = [...etfMap.keys()]
      .filter((d) => indexMap.has(d))
      .sort();

    if (commonDates.length === 0) return [];

    const sliced = commonDates.slice(-days);

    return sliced.map((date, i) => {
      const sharesYi = etfMap.get(date) / 1e8;
      const idxPt = indexMap.get(date);
      if (i === 0) {
        return { date, "份额变化%": 0, "指数变化%": 0, "份额(亿份)": +sharesYi.toFixed(2), "上证指数": idxPt };
      }
      const prevETF = etfMap.get(sliced[i - 1]);
      const prevIdx = indexMap.get(sliced[i - 1]);
      return {
        date,
        "份额变化%": +((etfMap.get(date) / prevETF - 1) * 100).toFixed(3),
        "指数变化%": +((indexMap.get(date) / prevIdx - 1) * 100).toFixed(3),
        "份额(亿份)": +sharesYi.toFixed(2),
        "上证指数": idxPt,
      };
    });
  }, [data, activeIndex, days]);

  const correlation = useMemo(() => {
    if (compareData.length < 5) return null;
    const xs = compareData.map((d) => d["份额变化%"]);
    const ys = compareData.map((d) => d["指数变化%"]);
    const n = xs.length;
    const meanX = xs.reduce((a, b) => a + b, 0) / n;
    const meanY = ys.reduce((a, b) => a + b, 0) / n;
    const num = xs.reduce((s, x, i) => s + (x - meanX) * (ys[i] - meanY), 0);
    const den = Math.sqrt(
      xs.reduce((s, x) => s + (x - meanX) ** 2, 0) *
      ys.reduce((s, y) => s + (y - meanY) ** 2, 0)
    );
    return den ? num / den : null;
  }, [compareData]);

  // 阶段分析: 使用全部数据计算滚动份额变化，检测阶段和关键信号
  const { phaseData, phaseAreas, markers } = useMemo(() => {
    if (!data || data.length === 0 || activeIndex.length === 0)
      return { phaseData: [], phaseAreas: [], markers: [] };

    const etfMap = new Map();
    data.forEach((d) => { if (d.total_shares) etfMap.set(d.date, d.total_shares); });

    const indexMap = new Map();
    activeIndex.forEach((d) => { if (d.close) indexMap.set(d.date, d.close); });

    const allDates = [...etfMap.keys()]
      .filter((d) => indexMap.has(d))
      .sort();

    if (allDates.length < ROLLING + 5) return { phaseData: [], phaseAreas: [], markers: [] };

    // 滚动份额变化 (全量数据，不限于 selected range)
    const sharesArr = allDates.map((d) => etfMap.get(d) / 1e8);
    const rollChg = [];
    for (let i = ROLLING; i < sharesArr.length; i++) {
      rollChg.push((sharesArr[i] / sharesArr[i - ROLLING] - 1) * 100);
    }

    const hi = Math.max(...rollChg.filter((v) => v > 0).length > 0 ? [0.5] : [0.3],
      [...rollChg].sort((a, b) => a - b)[Math.floor(rollChg.length * 0.7)]);
    const lo = Math.min(
      [...rollChg].sort((a, b) => a - b)[Math.floor(rollChg.length * 0.3)], -0.3);

    // 为每个日期标注阶段 (对齐到 allDates[ROLLING:] )
    const phaseMap = new Map();
    for (let i = 0; i < rollChg.length; i++) {
      if (rollChg[i] > hi) phaseMap.set(allDates[i + ROLLING], "机构增持");
      else if (rollChg[i] < lo) phaseMap.set(allDates[i + ROLLING], "获利赎回");
      else phaseMap.set(allDates[i + ROLLING], "中性");
    }

    // 找出所有机构增持阶段的起点日期 (全量数据)
    const zengchiStarts = [];
    let inZC = false;
    for (let i = 0; i < rollChg.length; i++) {
      const ph = phaseMap.get(allDates[i + ROLLING]);
      if (ph === "机构增持" && !inZC) {
        zengchiStarts.push(allDates[i + ROLLING]);
        inZC = true;
      } else if (ph !== "机构增持") {
        inZC = false;
      }
    }

    // 构建 phaseData (仅 selected range 内的数据)
    const sliced = allDates.slice(-days);
    const pData = sliced.map((date) => {
      const baseETF = etfMap.get(sliced[0]) / 1e8;
      const baseIdx = indexMap.get(sliced[0]);
      // 找上一个机构增持起点
      let lastZC = null;
      for (const zc of zengchiStarts) {
        if (zc <= date) lastZC = zc;
      }
      const zcETF = lastZC ? etfMap.get(lastZC) / 1e8 : null;
      const zcIdx = lastZC ? indexMap.get(lastZC) : null;
      const curETF = etfMap.get(date) / 1e8;
      const curIdx = indexMap.get(date);
      return {
        date,
        "ETF累计%": +((curETF / baseETF - 1) * 100).toFixed(2),
        "指数累计%": +((curIdx / baseIdx - 1) * 100).toFixed(2),
        "跟踪误差%": +(((curETF / baseETF) - (curIdx / baseIdx)) * 100).toFixed(2),
        "增持起点收益ETF%": lastZC && zcETF ? +((curETF / zcETF - 1) * 100).toFixed(2) : null,
        "增持起点收益指数%": lastZC && zcIdx ? +((curIdx / zcIdx - 1) * 100).toFixed(2) : null,
        "增持起点": lastZC,
        "阶段": phaseMap.get(date) || "—",
      };
    });

    // 构建 ReferenceArea (连续相同阶段的区域)
    const areas = [];
    let runStart = 0;
    let runPhase = pData[0]?.["阶段"];
    for (let i = 1; i < pData.length; i++) {
      if (pData[i]["阶段"] !== runPhase) {
        if (runPhase && runPhase !== "中性" && i - runStart >= 3) {
          areas.push({
            x1: pData[runStart].date,
            x2: pData[i - 1].date,
            phase: runPhase,
          });
        }
        runStart = i;
        runPhase = pData[i]["阶段"];
      }
    }
    if (runPhase && runPhase !== "中性" && pData.length - runStart >= 3) {
      areas.push({
        x1: pData[runStart].date,
        x2: pData[pData.length - 1].date,
        phase: runPhase,
      });
    }

    // 检测连续 5+ 天极端信号 (全量数据)
    const mkrs = [];
    let streak = 0;
    let streakPhase = null;
    for (let i = 0; i < rollChg.length; i++) {
      const ph = rollChg[i] > hi ? "up" : rollChg[i] < lo ? "dn" : null;
      if (ph === streakPhase && ph) {
        streak++;
        if (streak === 5 && allDates[i + ROLLING] >= sliced[0]) {
          mkrs.push({
            date: allDates[i + ROLLING],
            y: 0,
            type: streakPhase === "up" ? "buy" : "sell",
          });
        }
      } else {
        streak = ph ? 1 : 0;
        streakPhase = ph;
      }
    }

    // 激进卖出点: 赎回阶段内指数创新高日 (分位更低=更激进)
    const aggressiveLo = [...rollChg].sort((a, b) => a - b)[Math.floor(rollChg.length * 0.15)];
    const aggressivePhase = rollChg.map((v) => v < aggressiveLo);
    const aggressiveSells = [];
    let ap = 0;
    while (ap < aggressivePhase.length) {
      if (aggressivePhase[ap]) {
        let ae = ap;
        while (ae < aggressivePhase.length && aggressivePhase[ae]) ae++;
        if (ae - ap >= 3) {
          // 找赎回区间内指数峰值日
          const segIdx = allDates.slice(ap + ROLLING, ae + ROLLING + 1)
            .map((d) => indexMap.get(d))
            .filter((v) => v != null);
          if (segIdx.length > 0) {
            const peakVal = Math.max(...segIdx);
            const peakDate = allDates.slice(ap + ROLLING, ae + ROLLING + 1)
              .find((d) => indexMap.get(d) === peakVal);
            if (peakDate && peakDate >= sliced[0]) {
              aggressiveSells.push({ date: peakDate, y: 0, type: "aggressive_sell" });
            }
          }
        }
        ap = ae;
      } else {
        ap++;
      }
    }

    // 合并所有标记
    const allMarkers = [...mkrs, ...aggressiveSells];

    return { phaseData: pData, phaseAreas: areas, markers: allMarkers };
  }, [data, activeIndex, days]);

  if (!data || data.length === 0) {
    return <div className="chart__empty">选择一只 ETF 查看趋势</div>;
  }

  return (
    <div className="charts-wrapper">
      {/* 共用时间范围按钮 */}
      <div className="chart__range-row">
        <div className="chart__range-buttons">
          {Object.entries(RANGE_OPTIONS).map(([n, label]) => (
            <button
              key={n}
              className={`range-btn${+n === days ? " active" : ""}`}
              onClick={() => setDays(+n)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* 图1: 阶段分析 — 累计涨跌幅 + 阶段标注 + 买卖信号 */}
      <div className="chart-container">
        <h3 className="chart__title">
          {etfName} — 阶段分析 (基于{ROLLING}日≈2周趋势){" "}
          {phaseData.length > 0 && (
            <span className="current-phase" style={{
              background: phaseData[phaseData.length-1]["阶段"] === "机构增持" ? "#d1fae5" :
                          phaseData[phaseData.length-1]["阶段"] === "获利赎回" ? "#fee2e2" : "#f1f5f9",
              color: phaseData[phaseData.length-1]["阶段"] === "机构增持" ? "#065f46" :
                     phaseData[phaseData.length-1]["阶段"] === "获利赎回" ? "#991b1b" : "#475569",
            }}>
              当前: {phaseData[phaseData.length-1]["阶段"]}
            </span>
          )}
          <span className="phase-legend">
            <span className="phase-dot phase-buy" /> 增持
            <span className="phase-dot phase-sell" /> 赎回
            <span className="phase-dot phase-marker-buy" /> 买入
            <span className="phase-dot phase-marker-sell" style={{background:"#f59e0b"}} /> 激进卖
          </span>
        </h3>
        {phaseData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={phaseData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={11} />
              <YAxis label={{ value: "累计涨跌 (%)", angle: -90, position: "insideLeft", fontSize: 12 }} />
              <Tooltip content={<PhaseTooltip />} />
              <Legend />
              <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="6 3" />

              {/* 阶段背景色 */}
              {phaseAreas.map((a, i) => (
                <ReferenceArea
                  key={i}
                  x1={a.x1} x2={a.x2}
                  fill={a.phase === "机构增持" ? "#10b981" : "#ef4444"}
                  fillOpacity={0.08}
                />
              ))}

              {/* 关键信号标记 */}
              {markers.map((m, i) => (
                <ReferenceDot
                  key={i}
                  x={m.date} y={0}
                  r={m.type === "aggressive_sell" ? 6 : 5}
                  fill={m.type === "buy" ? "#10b981" : m.type === "aggressive_sell" ? "#f59e0b" : "#ef4444"}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}

              <Line type="monotone" dataKey="ETF累计%" stroke="#10b981" dot={false} strokeWidth={2} name="ETF涨跌%" />
              <Line type="monotone" dataKey="指数累计%" stroke="#ef4444" dot={false} strokeWidth={2} name="沪深300累计%" />
              <Line type="monotone" dataKey="跟踪误差%" stroke="#94a3b8" dot={false} strokeWidth={1.5} strokeDasharray="5 5" name="跟踪误差" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart__empty">数据不足，需要至少 {ROLLING + 5} 个交易日</div>
        )}

        {/* 操作指引面板 */}
        {phaseData.length > 0 && (() => {
          const currentPhase = phaseData[phaseData.length - 1]["阶段"];
          const hasSignal = markers.length > 0;
          const lastMarker = markers.length > 0 ? markers[markers.length - 1] : null;
          const etfPct = phaseData[phaseData.length - 1]["ETF累计%"];
          const idxPct = phaseData[phaseData.length - 1]["指数累计%"];

          return (
            <div className="guidance-panel">
              <div className="guidance-title">操作指引</div>
              <div className="guidance-body">
                {currentPhase === "机构增持" && (
                  <p>🟢 <b>机构正在增持</b> — 大资金在抄底。此时指数 {(idxPct > 0 ? "已上涨" : "在调整")} {Math.abs(idxPct).toFixed(0)}%。<br/>
                  建议: 可分批建仓，这是中期入场窗口。规模越大 ETF 信号越可靠 (首选 510300/510310/510330)。</p>
                )}
                {currentPhase === "获利赎回" && (
                  <p>🔴 <b>获利赎回中</b> — 机构正在落袋为安，但指数仍在趋势中 ({idxPct > 0 ? "+" : ""}{idxPct.toFixed(0)}%)。<br/>
                  建议: <b>继续持有</b>，获利赎回 ≠ 卖出信号。如阶段持续超 4 周再考虑减仓。记住：减仓在历史上跑输满仓。</p>
                )}
                {currentPhase === "中性" && (
                  <p>🟡 <b>中性观望</b> — 市场无明显方向，份额在正常区间波动。<br/>
                  建议: 继续持仓，不做调整。中性可能持续数周，耐心等待下一信号。</p>
                )}
                {currentPhase === "—" && (
                  <p>⏳ <b>数据积累中</b> — 当前区间数据不足，无法判定阶段。切换更长的时间范围(近13周/26周)查看。</p>
                )}
                {hasSignal && lastMarker && (
                  <p className="guidance-signal">
                    ⚡ <b>关键信号:</b> 检测到连续极端{lastMarker.type === "buy" ? "增持" : "赎回"}信号，历史上此类信号后续{' '}
                    {lastMarker.type === "buy" ? "正收益概率 60-100%" : "需关注趋势是否衰竭"}。
                  </p>
                )}
                <div className="guidance-rules">
                  <div className="guidance-rule">🟢 增持 → 分批建仓</div>
                  <div className="guidance-rule">🟡 中性 → 持有等待</div>
                  <div className="guidance-rule">🔴 保守: 赎回&lt;2周持有</div>
                  <div className="guidance-rule">🟠 激进: 赎回区内指数新高卖</div>
                  <div className="guidance-rule">⚡ 连续5天信号 → 高可信</div>
                </div>
              </div>
            </div>
          );
        })()}
      </div>

      {/* 图2: 成交量 + 资金净流入 */}
      <div className="chart-container">
        <h3 className="chart__title">{etfName} — 成交量与资金流向</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis yAxisId="left" label={{ value: "成交量(万手)", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: "资金净流入(亿元)", angle: 90, position: "insideRight", fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="成交量" stroke="#3b82f6" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="资金净流入" stroke="#f59e0b" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 图3: 日变化 */}
      <div className="chart-container">
        <h3 className="chart__title">
          {etfName} — 份额 vs 沪深300 日变化
          {correlation !== null && (
            <span className="chart__corr" style={{ color: correlation < 0 ? "#ef4444" : "#10b981" }}>
              {" "}r = {correlation.toFixed(3)}
            </span>
          )}
        </h3>
        {compareData.length > 0 ? (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={compareData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={11} />
              <YAxis label={{ value: "日变化 (%)", angle: -90, position: "insideLeft", fontSize: 12 }} />
              <Tooltip content={<CompareTooltip />} />
              <Legend />
              <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="6 3" />
              <Line type="monotone" dataKey="份额变化%" stroke="#10b981" dot={false} strokeWidth={2} name="份额变化%" />
              <Line type="monotone" dataKey="指数变化%" stroke="#ef4444" dot={false} strokeWidth={2} name="指数变化%" />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart__empty">暂无份额数据，请先刷新数据</div>
        )}
      </div>
    </div>
  );
}
