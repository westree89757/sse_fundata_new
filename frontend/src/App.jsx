import { useState, useEffect } from "react";
import ETFGrid from "./components/ETFGrid";
import TrendChart from "./components/TrendChart";
import OverviewPanel from "./components/OverviewPanel";
import { fetchETFList, fetchETFHistory, fetchIndexHistory, fetchHS300History, triggerRefresh } from "./api";

export default function App() {
  const [etfs, setEtfs] = useState([]);
  const [selectedCode, setSelectedCode] = useState(null);
  const [history, setHistory] = useState([]);
  const [indexData, setIndexData] = useState([]);
  const [hs300Data, setHs300Data] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alert, setAlert] = useState(null);

  const loadETFList = async () => {
    try {
      setLoading(true);
      setError(null);
      const list = await fetchETFList();
      setEtfs(list);
      if (list.length > 0 && !selectedCode) {
        setSelectedCode(list[0].code);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async (code) => {
    try {
      const data = await fetchETFHistory(code);
      setHistory(data);
    } catch (e) {
      setHistory([]);
    }
  };

  useEffect(() => {
    loadETFList();
    fetchIndexHistory()
      .then(setIndexData)
      .catch(() => setIndexData([]));
    fetchHS300History()
      .then(setHs300Data)
      .catch(() => setHs300Data([]));
  }, []);

  useEffect(() => {
    if (selectedCode) {
      loadHistory(selectedCode);
    }
  }, [selectedCode]);

  const handleRefresh = async () => {
    setLoading(true);
    await triggerRefresh();
    await loadETFList();
    setLoading(false);
  };

  const selectedETF = etfs.find((e) => e.code === selectedCode);

  if (error) {
    return (
      <div className="app">
        <div className="error-banner">
          加载失败: {error}
          <button onClick={loadETFList}>重试</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app__header">
        <h1>沪深300ETF 持仓趋势</h1>
        <button className="refresh-btn" onClick={handleRefresh} disabled={loading}>
          {loading ? "刷新中..." : "刷新数据"}
        </button>
      </header>
      {alert && (
        <div className={`alert-banner alert-${alert.type}`}>
          <span className="alert-icon">{alert.type === "buy" ? "🟢" : "🔴"}</span>
          <span className="alert-text">{alert.text}</span>
          <button className="alert-close" onClick={() => setAlert(null)}>×</button>
        </div>
      )}
      <main className="app__main">
        <OverviewPanel etfs={etfs} onSelect={setSelectedCode} />
        <ETFGrid etfs={etfs} selectedCode={selectedCode} onSelect={setSelectedCode} />
        <TrendChart data={history} etfName={selectedETF?.name || ""} indexData={hs300Data} szIndexData={indexData} onAlert={setAlert} />
      </main>
    </div>
  );
}
