import { useState, useEffect, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api";

function StatCard({ label, value, sub, color = "text-white" }) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-5">
      <p className="text-slate-400 text-sm mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-1">{sub}</p>}
    </div>
  );
}

function BotStatusBadge({ status, running }) {
  if (running) return <span className="inline-flex items-center gap-1.5 text-teal-400 text-sm font-medium"><span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse"></span>{status}</span>;
  return <span className="inline-flex items-center gap-1.5 text-slate-500 text-sm"><span className="w-2 h-2 rounded-full bg-slate-500"></span>{status || "stopped"}</span>;
}

export default function Dashboard() {
  const [portfolio, setPortfolio] = useState(null);
  const [trades, setTrades] = useState([]);
  const [botStatus, setBotStatus] = useState({ running: false, status: "stopped", log: [] });
  const [loading, setLoading] = useState(true);
  const [botLoading, setBotLoading] = useState(false);
  const [error, setError] = useState("");
  const nav = useNavigate();

  const email = localStorage.getItem("email") || "";

  function logout() {
    localStorage.clear();
    nav("/login");
  }

  const fetchAll = useCallback(async () => {
    try {
      const [p, t, s] = await Promise.all([api.getPortfolio(), api.getTrades(), api.botStatus()]);
      setPortfolio(p);
      setTrades(t);
      setBotStatus(s);
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  async function toggleBot() {
    setBotLoading(true);
    try {
      if (botStatus.running) await api.stopBot();
      else await api.startBot();
      await fetchAll();
    } catch (e) {
      setError(e.message);
    } finally {
      setBotLoading(false);
    }
  }

  const holdings = portfolio?.holdings || {};
  const totalValue = portfolio?.portfolio_value || 0;
  const buyingPower = portfolio?.buying_power || 0;

  return (
    <div className="min-h-screen">
      {/* Nav */}
      <nav className="border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🤖</span>
          <span className="font-bold text-white text-lg">AI Trading Bot</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-slate-400 text-sm hidden sm:block">{email}</span>
          <Link to="/settings" className="text-slate-400 hover:text-white text-sm transition">Settings</Link>
          <button onClick={logout} className="text-slate-400 hover:text-white text-sm transition">Logout</button>
        </div>
      </nav>

      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-400 rounded-lg px-4 py-3 text-sm flex items-center justify-between">
            <span>{error}</span>
            {error.includes("not configured") && (
              <Link to="/settings" className="underline ml-4">Configure now</Link>
            )}
          </div>
        )}

        {/* Bot control */}
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-white font-semibold text-lg mb-1">Trading Bot</h2>
            <BotStatusBadge status={botStatus.status} running={botStatus.running} />
            {botStatus.last_run && (
              <p className="text-slate-500 text-xs mt-1">Last cycle: {botStatus.last_run}</p>
            )}
          </div>
          <button
            onClick={toggleBot}
            disabled={botLoading}
            className={`px-8 py-3 rounded-lg font-bold transition disabled:opacity-50 ${
              botStatus.running
                ? "bg-red-600 hover:bg-red-500 text-white"
                : "bg-teal-500 hover:bg-teal-400 text-black"
            }`}
          >
            {botLoading ? "..." : botStatus.running ? "Stop Bot" : "Start Bot"}
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Portfolio Value"
            value={loading ? "—" : `$${totalValue.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            sub={portfolio?.broker ? `via ${portfolio.broker}` : ""}
          />
          <StatCard
            label="Buying Power"
            value={loading ? "—" : `$${buyingPower.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
            color="text-teal-400"
          />
          <StatCard
            label="Positions"
            value={loading ? "—" : Object.keys(holdings).length}
            sub="active holdings"
          />
          <StatCard
            label="Trades Today"
            value={trades.filter(t => t.timestamp?.startsWith(new Date().toISOString().slice(0, 10))).length}
            sub={trades.some(t => t.dry_run) ? "includes dry runs" : "live trades"}
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Holdings */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
            <h3 className="text-white font-semibold mb-4">Holdings</h3>
            {loading ? (
              <p className="text-slate-500 text-sm">Loading...</p>
            ) : Object.keys(holdings).length === 0 ? (
              <p className="text-slate-500 text-sm">No positions yet. Start the bot to begin trading.</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(holdings).map(([sym, h]) => {
                  const pct = parseFloat(h.percent_change || 0) * 100;
                  const equity = parseFloat(h.equity || 0);
                  return (
                    <div key={sym} className="flex items-center justify-between py-2 border-b border-slate-800 last:border-0">
                      <div>
                        <span className="text-white font-medium">{sym}</span>
                        <span className="text-slate-500 text-xs ml-2">{parseFloat(h.quantity || 0).toFixed(4)} shares</span>
                      </div>
                      <div className="text-right">
                        <p className="text-white">${equity.toFixed(2)}</p>
                        <p className={`text-xs ${pct >= 0 ? "text-teal-400" : "text-red-400"}`}>
                          {pct >= 0 ? "+" : ""}{pct.toFixed(2)}%
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Recent trades */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
            <h3 className="text-white font-semibold mb-4">Recent Trades</h3>
            {trades.length === 0 ? (
              <p className="text-slate-500 text-sm">No trades yet.</p>
            ) : (
              <div className="space-y-3">
                {trades.slice(0, 8).map((t) => (
                  <div key={t.id} className="flex items-start justify-between py-2 border-b border-slate-800 last:border-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${t.action === "buy" ? "bg-teal-900 text-teal-400" : "bg-red-900 text-red-400"}`}>
                        {t.action.toUpperCase()}
                      </span>
                      <div>
                        <span className="text-white text-sm font-medium">{t.symbol}</span>
                        {t.dry_run && <span className="text-xs text-slate-500 ml-1">(sim)</span>}
                        <p className="text-slate-500 text-xs truncate max-w-[180px]">{t.reason}</p>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-white text-sm">${t.amount_usd.toFixed(2)}</p>
                      <p className="text-slate-500 text-xs">{new Date(t.timestamp).toLocaleTimeString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Bot log */}
        {botStatus.log?.length > 0 && (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
            <h3 className="text-white font-semibold mb-3">Bot Log</h3>
            <div className="bg-black rounded-lg p-4 font-mono text-xs text-green-400 space-y-1 max-h-48 overflow-y-auto">
              {botStatus.log.map((line, i) => <p key={i}>{line}</p>)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
