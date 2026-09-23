import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, Save, Trash2, ShieldCheck, UserRound } from "lucide-react";
import { api, type AdminUser } from "../api";

export default function AdminUsers() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState({
    email: "",
    name: "",
    password: "",
    is_staff: false,
  });
  const [error, setError] = useState("");
  const [passwordFor, setPasswordFor] = useState<AdminUser | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const u = await api.adminUsers();
      setUsers(u);
    } catch (err: any) {
      setError(err?.message || "Impossible de charger les utilisateurs");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function create() {
    if (!form.email.trim() || !form.password) {
      setError("Email et mot de passe requis");
      return;
    }
    setError("");
    try {
      await api.adminCreateUser({
        email: form.email,
        name: form.name,
        password: form.password,
        is_staff: form.is_staff,
      });
      setForm({ email: "", name: "", password: "", is_staff: false });
      await load();
    } catch (err: any) {
      setError(err?.message || "Création impossible");
    }
  }

  async function toggle(user: AdminUser, field: "is_staff" | "is_active") {
    try {
      await api.adminUpdateUser(String(user.id), {
        [field]: !user[field],
      });
      await load();
    } catch (err: any) {
      setError(err?.message || "Mise à jour impossible");
    }
  }

  async function resetPassword() {
    if (!passwordFor || !newPassword) return;
    setError("");
    try {
      await api.adminUpdateUser(String(passwordFor.id), { password: newPassword });
      setPasswordFor(null);
      setNewPassword("");
    } catch (err: any) {
      setError(err?.message || "Réinitialisation impossible");
    }
  }

  async function remove(user: AdminUser) {
    if (!confirm(`Supprimer définitivement ${user.email} ?`)) return;
    setError("");
    try {
      await api.adminDeleteUser(String(user.id));
      await load();
    } catch (err: any) {
      setError(err?.message || "Suppression impossible");
    }
  }

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
        <h2 style={{ margin: 0, fontSize: 18 }}>Utilisateurs</h2>
        <button className="btn ghost sm" onClick={load}>
          <RefreshCw size={13} /> Rafraîchir
        </button>
      </div>

      <div className="admin-card" style={{ marginBottom: 16 }}>
        <div className="admin-card-title">
          <Plus size={14} /> Nouvel utilisateur
        </div>
        <div className="admin-grid">
          <input
            value={form.email}
            onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
            placeholder="email@exemple.fr"
          />
          <input
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            placeholder="Nom complet (optionnel)"
          />
          <input
            type="password"
            value={form.password}
            onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
            placeholder="Mot de passe"
          />
          <label className="radio" style={{ whiteSpace: "nowrap" }}>
            <input
              type="checkbox"
              checked={form.is_staff}
              onChange={(e) => setForm((f) => ({ ...f, is_staff: e.target.checked }))}
            />
            Staff
          </label>
          <button className="btn" onClick={create}>
            Créer
          </button>
        </div>
      </div>

      {error && <div className="error-text" style={{ color: "var(--color-danger)", fontSize: 13, marginBottom: 10 }}>{error}</div>}

      <div className="list">
        {loading && <div className="sub">Chargement…</div>}
        {!loading && users.length === 0 && <div className="sub">Aucun utilisateur.</div>}
        {users.map((u) => (
          <div key={u.id} className="list-row" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
            <UserRound size={15} style={{ color: "var(--color-muted)" }} />
            <div style={{ flex: 1, minWidth: 180 }}>
              <div className="name">{u.email}</div>
              <div className="sub">
                {u.name || "—"}
                {u.is_superuser && " • superuser"}
              </div>
            </div>
            <label className="radio" style={{ whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={u.is_active} onChange={() => toggle(u, "is_active")} />
              actif
            </label>
            <label className="radio" style={{ whiteSpace: "nowrap" }}>
              <input type="checkbox" checked={u.is_staff} onChange={() => toggle(u, "is_staff")} />
              staff
            </label>
            <button className="btn ghost sm" onClick={() => setPasswordFor(u)} title="Réinitialiser le mot de passe">
              <Save size={13} />
            </button>
            <button className="btn ghost sm danger-ghost" onClick={() => remove(u)} title="Supprimer">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>

      {passwordFor && (
        <div className="modal-backdrop" onClick={() => setPasswordFor(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: "0 0 14px" }}>
              <ShieldCheck size={15} style={{ verticalAlign: "middle", marginRight: 6 }} />
              Nouveau mot de passe — {passwordFor.email}
            </h3>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Nouveau mot de passe"
              autoFocus
            />
            <div style={{ display: "flex", gap: 10, marginTop: 16, justifyContent: "flex-end" }}>
              <button className="btn ghost" onClick={() => setPasswordFor(null)}>
                Annuler
              </button>
              <button className="btn" onClick={resetPassword} disabled={!newPassword}>
                Enregistrer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}