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

export default function TrendChart({ data, etfName }) {
  const [days, setDays] = useState(30);

  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];
    const sliced = data.slice(-days);
    return sliced.map((d) => ({
      date: d.date,
      成交量: d.volume ? +(d.volume / 10000).toFixed(2) : 0,
      总份额: d.total_shares ? +(d.total_shares / 10000).toFixed(2) : 0,
    }));
  }, [data, days]);

  if (!data || data.length === 0) {
    return <div className="chart__empty">选择一只 ETF 查看趋势</div>;
  }

  return (
    <div className="chart-container">
      <div className="chart__header">
        <h2>{etfName} — 持仓趋势</h2>
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
      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={12} />
          <YAxis yAxisId="left" label={{ value: "成交量(万手)", angle: -90, position: "insideLeft" }} />
          <YAxis yAxisId="right" orientation="right" label={{ value: "总份额(亿份)", angle: 90, position: "insideRight" }} />
          <Tooltip />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="成交量" stroke="#3b82f6" dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="总份额" stroke="#ef4444" dot={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
