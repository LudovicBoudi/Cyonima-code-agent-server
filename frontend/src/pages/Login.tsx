import { useEffect, useState } from "react";
import { useAuth } from "../store/auth";
import { api } from "../api";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [providers, setProviders] = useState<
    { id: string; name: string; login_url: string }[]
  >([]);

  useEffect(() => {
    api.ssoProviders().then((r) => setProviders(r.providers)).catch(() => {});
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "Erreur d'authentification");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <form className="login-card" onSubmit={submit}>
        <h1>Cyonima Code Agent</h1>
        <p className="sub">Portail entreprise — agents de code</p>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label>Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="vous@entreprise.com"
            required
          />
        </div>
        <div className="field">
          <label>Mot de passe</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            required
          />
        </div>
        <button className="btn" style={{ width: "100%" }} disabled={busy}>
          {busy ? "…" : "Se connecter"}
        </button>

        {providers.length > 0 && (
          <>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                margin: "16px 0",
                color: "var(--color-muted)",
                fontSize: 12,
              }}
            >
              <span style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
              ou
              <span style={{ flex: 1, height: 1, background: "var(--color-border)" }} />
            </div>
            {providers.map((p) => (
              <a
                key={p.id}
                href={p.login_url}
                className="btn ghost"
                style={{ width: "100%", textDecoration: "none", justifyContent: "center" }}
              >
                Se connecter avec {p.name}
              </a>
            ))}
          </>
        )}
      </form>
    </div>
  );
}