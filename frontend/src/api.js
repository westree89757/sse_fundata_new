const BASE = "/api";

export async function fetchETFList() {
  const res = await fetch(`${BASE}/etfs`);
  if (!res.ok) throw new Error(`Failed to fetch ETF list: ${res.status}`);
  const data = await res.json();
  return data.etfs;
}

export async function fetchETFHistory(code) {
  const res = await fetch(`${BASE}/etfs/${code}`);
  if (!res.ok) throw new Error(`Failed to fetch history for ${code}: ${res.status}`);
  return res.json();
}

export async function fetchIndexHistory() {
  const res = await fetch(`${BASE}/index`);
  if (!res.ok) throw new Error(`Failed to fetch index history: ${res.status}`);
  return res.json();
}

export async function triggerRefresh() {
  const res = await fetch(`${BASE}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to refresh: ${res.status}`);
  return res.json();
}
