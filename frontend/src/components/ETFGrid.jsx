import ETFCard from "./ETFCard";

export default function ETFGrid({ etfs, selectedCode, onSelect }) {
  if (!etfs || etfs.length === 0) {
    return <div className="etf-grid__empty">暂无数据，请先刷新</div>;
  }

  return (
    <div className="etf-grid">
      {etfs.map((etf) => (
        <ETFCard
          key={etf.code}
          etf={etf}
          isSelected={etf.code === selectedCode}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
