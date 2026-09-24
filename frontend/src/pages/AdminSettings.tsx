import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, Save, ShieldCheck, Server, XCircle } from "lucide-react";
import { api, type LdapType, type SystemConfig } from "../api";

const EMPTY: SystemConfig = {
  https_enabled: false,
  https_domain: "",
  has_tls_cert: false,
  is_https_ready: false,
  ldap_enabled: false,
  ldap_type: "ad",
  ldap_server_uri: "",
  ldap_bind_dn: "",
  ldap_base_dn: "",
  ldap_login_attribute: "sAMAccountName",
  ldap_user_filter: "",
  ldap_email_domain: "",
  ldap_start_tls: true,
  ldap_user_attr: "displayName",
};

export default function AdminSettings() {
  const [cfg, setCfg] = useState<SystemConfig>(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [messages, setMessages] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [ldapTest, setLdapTest] = useState<{ state: "idle" | "running" | "ok" | "ko"; text: string }>({
    state: "idle",
    text: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const c = await api.adminConfig();
      setCfg({ ...EMPTY, ...c, ldap_bind_password: "" });
    } catch (err: any) {
      setError(err?.message || "Impossible de charger la configuration");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function update<K extends keyof SystemConfig>(key: K, value: SystemConfig[K]) {
    setCfg((c) => ({ ...c, [key]: value }));
    setDirty(true);
  }

  async function save() {
    setBusy(true);
    setError("");
    setMessages([]);
    const payload: Record<string, unknown> = { ...cfg };
    // Ne pas écraser un mot de passe existant si le champ a été laissé vide.
    if (!payload.ldap_bind_password) delete payload.ldap_bind_password;
    try {
      const res = await api.adminSaveConfig(payload);
      setCfg((c) => ({ ...res, ldap_bind_password: "" }));
      setMessages(res.messages ?? []);
      setDirty(false);
    } catch (err: any) {
      setError(err?.message || "Enregistrement impossible");
    } finally {
      setBusy(false);
    }
  }

  async function generateCert() {
    if (!cfg.https_domain.trim()) {
      setError("Renseignez un domaine avant de générer le certificat.");
      return;
    }
    setBusy(true);
    setError("");
    setMessages([]);
    try {
      const res = await api.adminGenerateCert(cfg.https_domain.trim());
      setCfg((c) => ({ ...res.config, ldap_bind_password: "" }));
      setMessages(res.messages ?? []);
      setDirty(false);
    } catch (err: any) {
      setError(err?.message || "Génération impossible");
    } finally {
      setBusy(false);
    }
  }

  async function testLdap() {
    setLdapTest({ state: "running", text: "Connexion en cours…" });
    const payload: Record<string, unknown> = { ...cfg };
    if (!payload.ldap_bind_password) delete payload.ldap_bind_password;
    try {
      const res = await api.adminTestLdap(payload);
      setLdapTest({
        state: res.ok ? "ok" : "ko",
        text: res.message,
      });
    } catch (err: any) {
      setLdapTest({ state: "ko", text: err?.message || "Test impossible" });
    }
  }

  if (loading) return <div className="panel-body sub">Chargement…</div>;

  return (
    <div className="panel-body" style={{ flex: 1, overflowY: "auto" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <h2 style={{ margin: 0, fontSize: 18 }}>
          <ShieldCheck size={16} style={{ verticalAlign: "middle", marginRight: 8 }} />
          Paramètres
        </h2>
        <button className="btn ghost sm" onClick={load}>
          <RefreshCw size={13} /> Rafraîchir
        </button>
      </div>

      {error && (
        <div className="error-text" style={{ color: "var(--color-danger)", fontSize: 13, marginBottom: 10 }}>
          {error}
        </div>
      )}
      {messages.map((m) => (
        <div key={m} style={{ color: "var(--color-muted)", fontSize: 13, marginBottom: 6 }}>
          ✓ {m}
        </div>
      ))}

      {/* ------------------------------------------------------------------ */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">
          <Server size={14} /> HTTPS
        </div>
        <p className="sub" style={{ margin: "4px 0 12px" }}>
          Active la redirection HTTP → HTTPS, l'en-tête HSTS et les cookies
          <code> Secure</code> pour le domaine ci-dessous. En développement local
          (localhost), la politique HTTPS n'est pas appliquée.
        </p>

        <label className="radio" style={{ whiteSpace: "nowrap", marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={cfg.https_enabled}
            onChange={(e) => update("https_enabled", e.target.checked)}
          />
          Activer la politique HTTPS
        </label>

        <div className="admin-grid" style={{ gridTemplateColumns: "1fr 1fr auto" }}>
          <input
            value={cfg.https_domain}
            onChange={(e) => update("https_domain", e.target.value)}
            placeholder="ex: agent.example.fr"
          />
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, color: "var(--color-muted)" }}>
              {cfg.is_https_ready ? (
                <span style={{ color: "var(--color-success)" }}>
                  <CheckCircle2 size={13} style={{ verticalAlign: "middle", marginRight: 4 }} />
                  Certificat présent
                </span>
              ) : (
                <span style={{ color: "var(--color-warning)" }}>Aucun certificat</span>
              )}
            </span>
          </div>
          <button className="btn ghost sm" onClick={generateCert} disabled={busy}>
            Générer auto-signé
          </button>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">
          <Server size={14} /> Authentification LDAP / Active Directory
        </div>
        <p className="sub" style={{ margin: "4px 0 12px" }}>
          Les utilisateurs s'authentifient contre l'annuaire ; le compte local est
          créé automatiquement à la première connexion. Le mot de passe n'est jamais
          stocké.
        </p>

        <label className="radio" style={{ whiteSpace: "nowrap", marginBottom: 12 }}>
          <input
            type="checkbox"
            checked={cfg.ldap_enabled}
            onChange={(e) => update("ldap_enabled", e.target.checked)}
          />
          Activer l'authentification LDAP
        </label>

        <div className="admin-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
          <label className="label">
            Type d'annuaire
            <select
              value={cfg.ldap_type}
              onChange={(e) => update("ldap_type", e.target.value as LdapType)}
            >
              <option value="ad">Active Directory</option>
              <option value="openldap">OpenLDAP / autre LDAP</option>
            </select>
          </label>
          <label className="label">
            URI du serveur
            <input
              value={cfg.ldap_server_uri}
              onChange={(e) => update("ldap_server_uri", e.target.value)}
              placeholder="ldap://dc.exemple.fr:389 ou ldaps://..."
            />
          </label>
          <label className="label">
            Utilisateur de liaison (DN du service)
            <input
              value={cfg.ldap_bind_dn}
              onChange={(e) => update("ldap_bind_dn", e.target.value)}
              placeholder="CN=svc-agent,OU=Comptes,DC=exemple,DC=fr"
            />
          </label>
          <label className="label">
            Mot de passe du service (jamais réaffiché)
            <input
              type="password"
              value={cfg.ldap_bind_password ?? ""}
              onChange={(e) => update("ldap_bind_password", e.target.value)}
              placeholder="••••••••"
            />
          </label>
          <label className="label">
            Base DN (recherche)
            <input
              value={cfg.ldap_base_dn}
              onChange={(e) => update("ldap_base_dn", e.target.value)}
              placeholder="DC=exemple,DC=fr"
            />
          </label>
          <label className="label">
            Attribut de connexion
            <input
              value={cfg.ldap_login_attribute}
              onChange={(e) => update("ldap_login_attribute", e.target.value)}
              placeholder="sAMAccountName (AD) / uid (OpenLDAP)"
            />
          </label>
          <label className="label">
            Attribut de connexion
            <input
              value={cfg.ldap_login_attribute}
              onChange={(e) => update("ldap_login_attribute", e.target.value)}
              placeholder="sAMAccountName (AD) / uid (OpenLDAP)"
            />
          </label>
          <label className="label">
            Filtre utilisateur (le login remplace{" "}
            <code>{"%(user)s"}</code>)
            <input
              value={cfg.ldap_user_filter}
              onChange={(e) => update("ldap_user_filter", e.target.value)}
              placeholder='(&(objectClass=user)(sAMAccountName=%(user)s))'
            />
          </label>
          <label className="label">
            Domaine d'email de repli
            <input
              value={cfg.ldap_email_domain}
              onChange={(e) => update("ldap_email_domain", e.target.value)}
              placeholder="exemple.fr"
            />
          </label>
          <label className="label">
            Attribut du nom complet
            <input
              value={cfg.ldap_user_attr}
              onChange={(e) => update("ldap_user_attr", e.target.value)}
              placeholder="displayName"
            />
          </label>
          <label className="radio" style={{ whiteSpace: "nowrap", alignSelf: "center" }}>
            <input
              type="checkbox"
              checked={cfg.ldap_start_tls}
              onChange={(e) => update("ldap_start_tls", e.target.checked)}
            />
            StartTLS (ldap://)
          </label>
        </div>

        <div style={{ display: "flex", gap: 10, marginTop: 14, alignItems: "center" }}>
          <button className="btn ghost sm" onClick={testLdap} disabled={busy || ldapTest.state === "running"}>
            {ldapTest.state === "running" ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
            Tester la connexion
          </button>
          <span style={{ fontSize: 13 }}>
            {ldapTest.state === "ok" && (
              <span style={{ color: "var(--color-success)" }}>
                <CheckCircle2 size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
                {ldapTest.text}
              </span>
            )}
            {ldapTest.state === "ko" && (
              <span style={{ color: "var(--color-danger)" }}>
                <XCircle size={14} style={{ verticalAlign: "middle", marginRight: 4 }} />
                {ldapTest.text}
              </span>
            )}
          </span>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn" onClick={save} disabled={busy || !dirty}>
          {busy ? <Loader2 size={14} className="spin" /> : <Save size={14} />} Enregistrer
        </button>
      </div>
    </div>
  );
}