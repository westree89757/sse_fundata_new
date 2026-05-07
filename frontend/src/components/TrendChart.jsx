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

    return commonDates.slice(-days).map((date) => ({
      date,
      总份额: +(etfMap.get(date) / 1e8).toFixed(2),
      上证指数: indexMap.get(date),
    }));
  }, [data, indexData, days]);

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
        <ResponsiveContainer width="100%" height={320}>
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

      {/* 图2: ETF总份额 vs 上证指数 */}
      <div className="chart-container">
        <h3 className="chart__title">{etfName} — 总份额 vs 上证指数</h3>
        {compareData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={compareData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" fontSize={11} />
              <YAxis yAxisId="left" label={{ value: "总份额(亿份)", angle: -90, position: "insideLeft", fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" label={{ value: "上证指数", angle: 90, position: "insideRight", fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line yAxisId="left" type="monotone" dataKey="总份额" stroke="#10b981" dot={false} strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="上证指数" stroke="#ef4444" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart__empty">暂无份额数据，请先刷新数据</div>
        )}
      </div>
    </div>
  );
}
