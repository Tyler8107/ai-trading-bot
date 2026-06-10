import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "../api";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const nav = useNavigate();

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    setLoading(true);
    try {
      const data = await api.register(email, password);
      localStorage.setItem("token", data.token);
      localStorage.setItem("email", data.email);
      nav("/settings");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <span className="text-4xl">🤖</span>
            <h1 className="text-3xl font-bold text-white">AI Trading Bot</h1>
          </div>
          <p className="text-slate-400">Bring your own brokerage. Claude does the rest.</p>
        </div>

        <div className="bg-slate-900 border border-slate-700 rounded-2xl p-8">
          <h2 className="text-xl font-semibold text-white mb-6">Create your account</h2>

          {error && (
            <div className="bg-red-900/30 border border-red-700 text-red-400 rounded-lg px-4 py-3 mb-4 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="block text-sm text-slate-400 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 transition"
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm text-slate-400 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 transition"
                placeholder="min 8 characters"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-teal-500 hover:bg-teal-400 disabled:opacity-50 text-black font-bold py-3 rounded-lg transition"
            >
              {loading ? "Creating account..." : "Get Started"}
            </button>
          </form>

          <div className="mt-6 bg-slate-800 rounded-lg p-4 text-xs text-slate-400 space-y-1">
            <p className="font-medium text-slate-300">What you'll need:</p>
            <p>• Alpaca API key (free at alpaca.markets) — connects any brokerage</p>
            <p>• Anthropic API key (claude.ai) — powers the AI decisions</p>
          </div>

          <p className="text-center text-slate-400 text-sm mt-6">
            Already have an account?{" "}
            <Link to="/login" className="text-teal-400 hover:underline">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  );
}
