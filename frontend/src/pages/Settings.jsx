import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">{label}</label>
      {hint && <p className="text-xs text-slate-500 mb-2">{hint}</p>}
      {children}
    </div>
  );
}

function Input({ value, onChange, type = "text", placeholder }) {
  return (
    <input
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 transition text-sm"
    />
  );
}

export default function Settings() {
  const [form, setForm] = useState({
    broker: "alpaca",
    alpaca_api_key: "",
    alpaca_secret_key: "",
    alpaca_paper: true,
    rh_username: "",
    rh_password: "",
    anthropic_api_key: "",
    max_position_usd: 100,
    max_daily_loss_usd: 50,
    run_interval_minutes: 60,
    dry_run: true,
  });
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSettings().then((s) => setForm((f) => ({ ...f, ...s }))).catch(() => {});
  }, []);

  function set(key) {
    return (val) => setForm((f) => ({ ...f, [key]: val }));
  }

  async function save(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.saveSettings(form);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <nav className="border-b border-slate-800 px-6 py-4 flex items-center gap-4">
        <Link to="/" className="text-slate-400 hover:text-white transition text-sm">← Dashboard</Link>
        <span className="text-white font-semibold">Settings</span>
      </nav>

      <div className="max-w-2xl mx-auto px-4 py-8">
        <form onSubmit={save} className="space-y-8">

          {/* Broker */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
            <h2 className="text-white font-semibold text-lg">Brokerage Connection</h2>

            <Field label="Broker">
              <div className="flex gap-3">
                {["alpaca", "robinhood"].map((b) => (
                  <button
                    key={b}
                    type="button"
                    onClick={() => set("broker")(b)}
                    className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition capitalize ${
                      form.broker === b
                        ? "bg-teal-500 border-teal-500 text-black"
                        : "bg-slate-800 border-slate-600 text-slate-300 hover:border-slate-400"
                    }`}
                  >
                    {b === "alpaca" ? "Alpaca (any broker)" : "Robinhood"}
                  </button>
                ))}
              </div>
            </Field>

            {form.broker === "alpaca" && (
              <>
                <Field label="Alpaca API Key" hint="Get free at alpaca.markets — supports paper + live trading">
                  <Input value={form.alpaca_api_key} onChange={set("alpaca_api_key")} placeholder="PKXXXXXXXX" />
                </Field>
                <Field label="Alpaca Secret Key">
                  <Input value={form.alpaca_secret_key} onChange={set("alpaca_secret_key")} type="password" placeholder="••••••••" />
                </Field>
                <Field label="Trading Mode">
                  <div className="flex gap-3">
                    {[true, false].map((paper) => (
                      <button
                        key={String(paper)}
                        type="button"
                        onClick={() => set("alpaca_paper")(paper)}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition ${
                          form.alpaca_paper === paper
                            ? "bg-teal-500 border-teal-500 text-black"
                            : "bg-slate-800 border-slate-600 text-slate-300 hover:border-slate-400"
                        }`}
                      >
                        {paper ? "Paper (Simulated)" : "Live (Real Money)"}
                      </button>
                    ))}
                  </div>
                  {!form.alpaca_paper && (
                    <p className="text-amber-400 text-xs mt-2">⚠️ Live trading uses real money. Enable dry run below to test first.</p>
                  )}
                </Field>
              </>
            )}

            {form.broker === "robinhood" && (
              <>
                <Field label="Robinhood Email">
                  <Input value={form.rh_username} onChange={set("rh_username")} type="email" placeholder="you@example.com" />
                </Field>
                <Field label="Robinhood Password">
                  <Input value={form.rh_password} onChange={set("rh_password")} type="password" placeholder="••••••••" />
                </Field>
              </>
            )}
          </div>

          {/* AI */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
            <h2 className="text-white font-semibold text-lg">AI (Claude)</h2>
            <Field label="Anthropic API Key" hint="Get at console.anthropic.com — Claude Opus makes trading decisions">
              <Input value={form.anthropic_api_key} onChange={set("anthropic_api_key")} type="password" placeholder="sk-ant-..." />
            </Field>
          </div>

          {/* Risk */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 space-y-5">
            <h2 className="text-white font-semibold text-lg">Risk Controls</h2>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Max Position Size ($)" hint="Max $ per trade">
                <Input value={form.max_position_usd} onChange={(v) => set("max_position_usd")(Number(v))} type="number" />
              </Field>
              <Field label="Max Daily Loss ($)" hint="Bot pauses if exceeded">
                <Input value={form.max_daily_loss_usd} onChange={(v) => set("max_daily_loss_usd")(Number(v))} type="number" />
              </Field>
            </div>

            <Field label="Check Interval (minutes)" hint="How often Claude analyzes your portfolio">
              <Input value={form.run_interval_minutes} onChange={(v) => set("run_interval_minutes")(Number(v))} type="number" />
            </Field>

            <Field label="Dry Run Mode">
              <div className="flex gap-3">
                {[true, false].map((dry) => (
                  <button
                    key={String(dry)}
                    type="button"
                    onClick={() => set("dry_run")(dry)}
                    className={`flex-1 py-2.5 rounded-lg text-sm font-medium border transition ${
                      form.dry_run === dry
                        ? "bg-teal-500 border-teal-500 text-black"
                        : "bg-slate-800 border-slate-600 text-slate-300 hover:border-slate-400"
                    }`}
                  >
                    {dry ? "Simulation (safe)" : "Real trades"}
                  </button>
                ))}
              </div>
            </Field>
          </div>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-400 rounded-lg px-4 py-3 text-sm">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-black font-bold py-3 rounded-lg transition"
          >
            {loading ? "Saving..." : saved ? "Saved!" : "Save Settings"}
          </button>
        </form>
      </div>
    </div>
  );
}
