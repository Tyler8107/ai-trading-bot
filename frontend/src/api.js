const BASE = "/api";

function headers() {
  const token = localStorage.getItem("token");
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function req(method, path, body) {
  const res = await fetch(BASE + path, {
    method,
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

export const api = {
  login: (email, password) => req("POST", "/auth/login", { email, password }),
  register: (email, password) => req("POST", "/auth/register", { email, password }),
  getSettings: () => req("GET", "/settings"),
  saveSettings: (data) => req("PUT", "/settings", data),
  getPortfolio: () => req("GET", "/portfolio"),
  getTrades: () => req("GET", "/trades"),
  startBot: () => req("POST", "/bot/start"),
  stopBot: () => req("POST", "/bot/stop"),
  botStatus: () => req("GET", "/bot/status"),
  getPriceTargets: () => req("GET", "/price-targets"),
  createPriceTarget: (data) => req("POST", "/price-targets", data),
  deletePriceTarget: (id) => req("DELETE", `/price-targets/${id}`),
};
