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
} from "recharts";

const RANGE_OPTIONS = { 30: "近30天", 90: "近90天", 180: "近180天" };

export default function TrendChart({ data, etfName, indexData }) {
  const [days, setDays] = useState(30);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    const sliced = data.slice(-days);
    return sliced.map((d) => ({
      date: d.date,
      成交量: d.volume ? +(d.volume / 10000).toFixed(2) : 0,
      总份额: d.total_shares ? +(d.total_shares / 1e8).toFixed(2) : 0,
    }));
  }, [data, days]);

  const compareData = useMemo(() => {
    if (!data || data.length === 0 || !indexData || indexData.length === 0) return [];

    const etfMap = new Map();
    data.forEach((d) => { if (d.total_shares) etfMap.set(d.date, d.total_shares); });

    const indexMap = new Map();
    indexData.forEach((d) => { if (d.close) indexMap.set(d.date, d.close); });

    const commonDates = [...etfMap.keys()]
      .filter((d) => indexMap.has(d))
      .sort();

    if (commonDates.length === 0) return [];

    const sliced = commonDates.slice(-days);

    return sliced.map((date, i) => {
      if (i === 0) return { date, "份额变化%": 0, "指数变化%": 0 };
      const prevETF = etfMap.get(sliced[i - 1]);
      const prevIdx = indexMap.get(sliced[i - 1]);
      return {
        date,
        "份额变化%": +((etfMap.get(date) / prevETF - 1) * 100).toFixed(3),
        "指数变化%": +((indexMap.get(date) / prevIdx - 1) * 100).toFixed(3),
      };
    });
  }, [data, indexData, days]);

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

      {/* 图1: 成交量 + 总份额 */}
      <div className="chart-container">
        <h3 className="chart__title">{etfName} — 成交量与份额</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" fontSize={11} />
            <YAxis yAxisId="left" label={{ value: "成交量(万手)", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <YAxis yAxisId="right" orientation="right" label={{ value: "总份额(亿份)", angle: 90, position: "insideRight", fontSize: 11 }} />
            <Tooltip />
            <Legend />
            <Line yAxisId="left" type="monotone" dataKey="成交量" stroke="#3b82f6" dot={false} />
            <Line yAxisId="right" type="monotone" dataKey="总份额" stroke="#10b981" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* 图2: 归一化涨跌幅对比 — 直观展示负相关 */}
      <div className="chart-container">
        <h3 className="chart__title">
          {etfName} — 份额 vs 上证指数 日变化
          {correlation !== null && (
            <span className="chart__corr" style={{ color: correlation < 0 ? "#ef4444" : "#10b981" }}>
              {" "}r = {correlation.toFixed(3)}
            </span>
          )}
        </h3>
        {compareData.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={compareData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={11} />
              <YAxis label={{ value: "日变化 (%)", angle: -90, position: "insideLeft", fontSize: 12 }} />
              <Tooltip formatter={(v) => `${v}%`} />
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
