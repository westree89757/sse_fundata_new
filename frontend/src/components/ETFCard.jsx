export default function ETFCard({ etf, isSelected, onSelect }) {
  const volumeDisplay = etf.latest_volume
    ? (etf.latest_volume / 10000).toFixed(2) + " 万手"
    : "N/A";

  const sharesDisplay = etf.total_shares
    ? (etf.total_shares / 10000).toFixed(2) + " 亿份"
    : "N/A";

  return (
    <div
      className={`etf-card${isSelected ? " selected" : ""}`}
      onClick={() => onSelect(etf.code)}
    >
      <div className="etf-card__name">{etf.name}</div>
      <div className="etf-card__code">{etf.code}</div>
      <div className="etf-card__stat">
        <span className="label">成交量</span>
        <span className="value">{volumeDisplay}</span>
      </div>
      <div className="etf-card__stat">
        <span className="label">总份额</span>
        <span className="value">{sharesDisplay}</span>
      </div>
    </div>
  );
}
