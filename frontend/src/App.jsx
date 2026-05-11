import { useState, useEffect } from "react";
import TrendChart from "./components/TrendChart";
import OverviewPanel from "./components/OverviewPanel";
import { fetchETFList, fetchETFHistory, fetchIndexHistory, fetchHS300History, triggerRefresh, fetchRefreshStatus } from "./api";

export default function App() {
  const [etfs, setEtfs] = useState([]);
  const [selectedCode, setSelectedCode] = useState(null);
  const [history, setHistory] = useState([]);
  const [indexData, setIndexData] = useState([]);
  const [hs300Data, setHs300Data] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [alert, setAlert] = useState(null);

  const handleDataChange = (allData) => {
    if (!allData || allData.length === 0) return;
    const buyCount = allData.filter((d) => d.phase === "增持").length;
    const sellCount = allData.filter((d) => d.phase === "赎回").length;
    const totalFlow = allData.reduce((s, d) => s + d.netFlow5d, 0);
    const buyNames = allData.filter((d) => d.phase === "增持").map((d) => d.name).join("、");
    const sellNames = allData.filter((d) => d.phase === "赎回").map((d) => d.name).join("、");

    if (buyCount >= 4) {
      setAlert({ type: "buy", text: `强增持信号: ${buyCount}/7 ETF处于增持阶段 (${buyNames})，合计净流入 ${totalFlow.toFixed(2)}亿 — 机构大规模抄底中` });
    } else if (sellCount >= 4) {
      setAlert({ type: "sell", text: `强赎回信号: ${sellCount}/7 ETF处于获利赎回阶段 (${sellNames})，合计净流入 ${totalFlow.toFixed(2)}亿 — 普遍获利了结，注意趋势` });
    } else if (buyCount >= 2) {
      setAlert({ type: "buy", text: `增持信号: ${buyCount}/7 ETF处于增持阶段 (${buyNames})，合计净流入 ${totalFlow.toFixed(2)}亿` });
    } else if (sellCount >= 2) {
      setAlert({ type: "sell", text: `赎回信号: ${sellCount}/7 ETF处于获利赎回阶段 (${sellNames})，合计净流入 ${totalFlow.toFixed(2)}亿` });
    } else {
      setAlert(null);
    }
  };

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
    const { status } = await triggerRefresh();
    if (status === "already_refreshing") {
      setLoading(false);
      return;
    }
    // 轮询直到刷新完成
    const poll = setInterval(async () => {
      try {
        const s = await fetchRefreshStatus();
        if (!s.refreshing) {
          clearInterval(poll);
          await loadETFList();
          // 重新加载全部数据以更新图表
          window.location.reload();
        }
      } catch {
        clearInterval(poll);
        setLoading(false);
      }
    }, 2000);
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
        <OverviewPanel etfs={etfs} selectedCode={selectedCode} onSelect={setSelectedCode} onDataChange={handleDataChange} />
        <TrendChart data={history} etfName={selectedETF?.name || ""} indexData={hs300Data} szIndexData={indexData} />
      </main>
    </div>
  );
}
