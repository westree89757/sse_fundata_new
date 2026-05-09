import { useEffect, useState } from "react";
import { fetchETFHistory } from "../api";

export default function OverviewPanel({ etfs, selectedCode, onSelect, onDataChange }) {
  const [etfData, setEtfData] = useState({});

  useEffect(() => {
    if (!etfs || etfs.length === 0) return;
    const results = {};
    let pending = etfs.length;

    const tryReport = () => {
      if (pending <= 0 && onDataChange) {
        onDataChange(Object.entries(results).map(([code, d]) => ({ code, ...d })));
      }
    };

    etfs.forEach((etf) => {
      fetchETFHistory(etf.code)
        .then((hist) => {
          if (!hist || hist.length < 20) { pending--; tryReport(); return; }
          const recent20 = hist.slice(-20);
          const shareStart = recent20[0].total_shares;
          const shareEnd = recent20[recent20.length - 1].total_shares;
          const shareChg = shareStart ? ((shareEnd / shareStart - 1) * 100) : 0;

          let netFlow5d = 0;
          for (let i = Math.max(1, recent20.length - 5); i < recent20.length; i++) {
            const prev = recent20[i - 1].total_shares;
            const curr = recent20[i].total_shares;
            const avgPrice = (recent20[i].open + recent20[i].close) / 2 || 0;
            if (prev && curr) netFlow5d += (curr - prev) * avgPrice / 1e8;
          }

          const last = recent20[recent20.length - 1];
          const amountYi = last.turnover ? (last.turnover / 1e8) : 0;

          let phase = "中性";
          if (shareChg > 0.3) phase = "增持";
          else if (shareChg < -1.0) phase = "赎回";

          results[etf.code] = { shareChg, netFlow5d, turnover: last.turnover, phase, name: etf.name };
          setEtfData((prev) => ({ ...prev, [etf.code]: { shareChg, netFlow5d, turnover: last.turnover, phase } }));
          pending--;
          tryReport();
        })
        .catch((err) => {
          results[etf.code] = { shareChg: 0, netFlow5d: 0, turnover: null, phase: "无数据", name: etf.name };
          setEtfData((prev) => ({ ...prev, [etf.code]: { shareChg: 0, netFlow5d: 0, turnover: null, phase: "无数据" } }));
          pending--;
          tryReport();
        });
    });
  }, [etfs]);

  if (!etfs || etfs.length === 0) {
    return <div className="etf-grid__empty">暂无数据，请先刷新</div>;
  }

  return (
    <div className="overview-panel">
      <h3 className="overview-title">全景概览</h3>
      <div className="overview-grid">
        {etfs.map((etf) => {
          const d = etfData[etf.code];
          const isSelected = etf.code === selectedCode;
          const volumeDisplay = etf.latest_volume
            ? (etf.latest_volume / 10000).toFixed(1) + " 万手"
            : "N/A";
          const sharesDisplay = etf.total_shares
            ? (etf.total_shares / 1e8).toFixed(2) + " 亿份"
            : "N/A";
          const premiumDisplay = etf.premium != null
            ? (etf.premium > 0 ? "+" : "") + etf.premium.toFixed(2) + "%"
            : "N/A";

          return (
            <div
              key={etf.code}
              className={`overview-card${isSelected ? " ov-selected" : ""}${d?.phase === "增持" ? " ov-buy" : d?.phase === "赎回" ? " ov-sell" : ""}`}
              onClick={() => onSelect(etf.code)}
            >
              <div className="ov-name">{etf.name}</div>
              <div className="ov-code">{etf.code}</div>
              <div className="ov-stats">
                <div className="ov-stat">
                  <span className="ov-label">成交量</span>
                  <span className="ov-val">{volumeDisplay}</span>
                </div>
                <div className="ov-stat">
                  <span className="ov-label">总份额</span>
                  <span className="ov-val">{sharesDisplay}</span>
                </div>
                <div className="ov-stat">
                  <span className="ov-label">折溢价</span>
                  <span className="ov-val" style={{ color: etf.premium > 0 ? "#ef4444" : etf.premium < 0 ? "#10b981" : "#64748b" }}>
                    {premiumDisplay}
                  </span>
                </div>
                {d ? (
                  <>
                    <div className="ov-stat">
                      <span className="ov-label">5日净流入</span>
                      <span className="ov-val" style={{ color: d.netFlow5d >= 0 ? "#10b981" : "#ef4444" }}>
                        {d.netFlow5d > 0 ? "+" : ""}{d.netFlow5d.toFixed(2)}亿
                      </span>
                    </div>
                    <div className="ov-stat">
                      <span className="ov-label">20日份额</span>
                      <span className="ov-val" style={{ color: d.shareChg >= 0 ? "#10b981" : "#ef4444" }}>
                        {d.shareChg > 0 ? "+" : ""}{d.shareChg.toFixed(1)}%
                      </span>
                    </div>
                    <div className="ov-stat">
                      <span className="ov-label">成交额</span>
                      <span className="ov-val" style={{ color: (d.turnover / 1e8) > 50 ? "#ef4444" : "#64748b" }}>
                        {(d.turnover / 1e8).toFixed(1)}亿
                      </span>
                    </div>
                    <div className="ov-phase-badge" style={{
                      background: d.phase === "增持" ? "#d1fae5" : d.phase === "赎回" ? "#fee2e2" : "#f1f5f9",
                      color: d.phase === "增持" ? "#065f46" : d.phase === "赎回" ? "#991b1b" : "#475569",
                    }}>{d.phase}</div>
                  </>
                ) : (
                  <div className="ov-loading">加载中...</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {/* 大小票轮动比 */}
      {etfs.length >= 7 && (() => {
        const BIG_CODES = ["510300", "510310", "510330"];
        const bigFlow = BIG_CODES.reduce((s, c) => s + ((etfData[c] && etfData[c].netFlow5d) || 0), 0);
        const smallFlow = etfs.filter((e) => !BIG_CODES.includes(e.code))
          .reduce((s, e) => s + ((etfData[e.code] && etfData[e.code].netFlow5d) || 0), 0);
        const bigCount = BIG_CODES.filter((c) => etfData[c] && etfData[c].phase === "增持").length;
        const smallCount = etfs.filter((e) => !BIG_CODES.includes(e.code) && etfData[e.code] && etfData[e.code].phase === "增持").length;
        const bias = bigFlow > 0 && smallFlow < 0 ? "机构主导" : bigFlow < 0 && smallFlow > 0 ? "散户主导" : "均衡";
        return (
          <div className="rotation-bar">
            <span className="rotation-label">轮动: 三大ETF净流入 {bigFlow > 0 ? "+" : ""}{bigFlow.toFixed(2)}亿 | 四小 {smallFlow > 0 ? "+" : ""}{smallFlow.toFixed(2)}亿</span>
            <span className={`rotation-badge ${bias === "机构主导" ? "rot-big" : bias === "散户主导" ? "rot-small" : "rot-neutral"}`}>{bias}</span>
          </div>
        );
      })()}
    </div>
  );
}
