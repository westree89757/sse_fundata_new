import { useEffect, useState } from "react";
import { fetchETFHistory } from "../api";

const CSI300_KEYWORDS = ["沪深300", "沪深 300", "CSI300", "CSI 300"];

export default function OverviewPanel({ etfs, onSelect }) {
  const [etfData, setEtfData] = useState({});

  useEffect(() => {
    if (!etfs || etfs.length === 0) return;
    etfs.forEach((etf) => {
      fetchETFHistory(etf.code)
        .then((hist) => {
          if (!hist || hist.length < 20) return;
          // 最近20天滚动份额变化
          const recent20 = hist.slice(-20);
          const shareStart = recent20[0].total_shares;
          const shareEnd = recent20[recent20.length - 1].total_shares;
          const shareChg = shareStart ? ((shareEnd / shareStart - 1) * 100) : 0;

          // 最近5天净流入
          let netFlow5d = 0;
          for (let i = Math.max(1, recent20.length - 5); i < recent20.length; i++) {
            const prev = recent20[i - 1].total_shares;
            const curr = recent20[i].total_shares;
            const avgPrice = (recent20[i].open + recent20[i].close) / 2 || 0;
            if (prev && curr) netFlow5d += (curr - prev) * avgPrice / 1e8;
          }

          // 最新换手率
          const last = recent20[recent20.length - 1];
          const turnover = last.turnover || 0;

          // 阶段判断
          let phase = "中性";
          if (shareChg > 0.3) phase = "增持";
          else if (shareChg < -1.0) phase = "赎回";

          setEtfData((prev) => ({
            ...prev,
            [etf.code]: { shareChg, netFlow5d, turnover, phase, name: etf.name },
          }));
        })
        .catch(() => {});
    });
  }, [etfs]);

  if (!etfs || etfs.length === 0) return null;

  return (
    <div className="overview-panel">
      <h3 className="overview-title">全景概览</h3>
      <div className="overview-grid">
        {etfs.map((etf) => {
          const d = etfData[etf.code];
          return (
            <div
              key={etf.code}
              className={`overview-card${d?.phase === "增持" ? " ov-buy" : d?.phase === "赎回" ? " ov-sell" : ""}`}
              onClick={() => onSelect(etf.code)}
            >
              <div className="ov-name">{etf.name}</div>
              <div className="ov-code">{etf.code}</div>
              {d ? (
                <div className="ov-stats">
                  <div className="ov-stat">
                    <span className="ov-label">20日份额</span>
                    <span className="ov-val" style={{ color: d.shareChg >= 0 ? "#10b981" : "#ef4444" }}>
                      {d.shareChg > 0 ? "+" : ""}{d.shareChg.toFixed(1)}%
                    </span>
                  </div>
                  <div className="ov-stat">
                    <span className="ov-label">5日净流入</span>
                    <span className="ov-val" style={{ color: d.netFlow5d >= 0 ? "#10b981" : "#ef4444" }}>
                      {d.netFlow5d > 0 ? "+" : ""}{d.netFlow5d.toFixed(2)}亿
                    </span>
                  </div>
                  <div className="ov-stat">
                    <span className="ov-label">换手</span>
                    <span className="ov-val" style={{ color: d.turnover > 3 ? "#ef4444" : "#64748b" }}>
                      {d.turnover.toFixed(1)}%
                    </span>
                  </div>
                  <div className="ov-phase-badge" style={{
                    background: d.phase === "增持" ? "#d1fae5" : d.phase === "赎回" ? "#fee2e2" : "#f1f5f9",
                    color: d.phase === "增持" ? "#065f46" : d.phase === "赎回" ? "#991b1b" : "#475569",
                  }}>{d.phase}</div>
                </div>
              ) : (
                <div className="ov-loading">加载中...</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
