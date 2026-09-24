import { useEffect, useState } from "react";
import { Bot, LogOut, Plus, MessageSquare, Boxes, ShieldCheck, Settings, Users, FolderGit2, FolderUp, FolderOpen } from "lucide-react";
import { api, type Session } from "../api";
import { useAuth } from "../store/auth";
import SessionView from "./SessionView";
import OllamaView from "./OllamaView";
import AdminUsers from "./AdminUsers";
import AdminSettings from "./AdminSettings";

export default function Home() {
  const { user, logout } = useAuth();
  const [view, setView] = useState<"main" | "ollama" | "users" | "settings">("main");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [showSessionModal, setShowSessionModal] = useState(false);

  const refresh = () => api.sessions().then(setSessions);

  useEffect(() => {
    refresh();
  }, []);

  async function onSessionCreated(s: Session) {
    setSessions((prev) => [s, ...prev]);
    setActiveSession(s);
    setShowSessionModal(false);
    setView("main");
  }

  async function deleteSession(id: string) {
    await api.deleteSession(id);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSession?.id === id) setActiveSession(null);
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <Bot size={18} /> Cyonima
        </div>
        <nav>
          <div
            className={`item ${view === "ollama" ? "active" : ""}`}
            onClick={() => setView("ollama")}
          >
            <Boxes size={15} />
            <span className="truncate">Modèles Ollama</span>
          </div>

          {user?.is_staff && (
            <div
              className={`item ${view === "users" || view === "settings" ? "active" : ""}`}
              onClick={() => setView("users")}
            >
              <ShieldCheck size={15} />
              <span className="truncate">Administration</span>
            </div>
          )}

          <div className="section" style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <span style={{ flex: 1 }}>Mes sessions</span>
            <span
              style={{ cursor: "pointer", color: "var(--color-accent)" }}
              onClick={() => setShowSessionModal(true)}
            >
              <Plus size={13} style={{ display: "inline" }} />
            </span>
          </div>
          <div className="list">
            {sessions.map((s) => (
              <div
                key={s.id}
                className={`item ${s.id === activeSession?.id ? "active" : ""}`}
                onClick={() => {
                  setActiveSession(s);
                  setView("main");
                }}
              >
                <MessageSquare size={14} />
                <span className="truncate">{s.title || "Nouvelle session"}</span>
                <span
                  style={{ cursor: "pointer", color: "var(--color-danger)" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteSession(s.id);
                  }}
                >
                  ✕
                </span>
              </div>
            ))}
          </div>
        </nav>
        <div style={{ padding: 10, borderTop: "1px solid var(--color-border)", fontSize: 12 }}>
          <div style={{ color: "var(--color-muted)", marginBottom: 8 }}>{user?.email}</div>
          <button className="btn ghost sm" onClick={logout}>
            <LogOut size={13} /> Déconnexion
          </button>
        </div>
      </aside>

      <main className="main">
        {view === "ollama" ? (
          <OllamaView />
        ) : view === "users" || view === "settings" ? (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ display: "flex", gap: 8, marginBottom: 14, flexShrink: 0 }}>
              <button
                className={`btn ghost sm ${view === "users" ? "tab-active" : ""}`}
                onClick={() => setView("users")}
              >
                <Users size={13} /> Utilisateurs
              </button>
              <button
                className={`btn ghost sm ${view === "settings" ? "tab-active" : ""}`}
                onClick={() => setView("settings")}
              >
                <Settings size={13} /> Paramètres
              </button>
            </div>
            {view === "users" ? <AdminUsers /> : <AdminSettings />}
          </div>
        ) : activeSession ? (
          <SessionView session={activeSession} />
        ) : (
          <div className="empty">
            <div>
              <FolderGit2 size={32} style={{ color: "var(--color-accent)" }} />
              <h2>Bienvenue, {user?.name || user?.email}</h2>
              <p>Créez une session en choisissant votre dossier de travail local.</p>
              <button className="btn" onClick={() => setShowSessionModal(true)}>
                <Plus size={16} /> Nouvelle session
              </button>
            </div>
          </div>
        )}
      </main>

      {showSessionModal && (
        <NewSessionModal
          onCreated={onSessionCreated}
          onClose={() => setShowSessionModal(false)}
        />
      )}
    </div>
  );
}

function NewSessionModal({
  onCreated,
  onClose,
}: {
  onCreated: (s: Session) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [current, setCurrent] = useState("");
  const [dirs, setDirs] = useState<{ name: string; path: string }[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const loadDirs = async (path: string) => {
    setError("");
    try {
      const r = await api.localDirs(path || undefined);
      setCurrent(r.path);
      setParent(r.parent);
      setDirs(r.dirs);
    } catch (err: any) {
      setError(err?.message || "Navigation impossible");
      setDirs([]);
      setParent(null);
    }
  };

  useEffect(() => {
    setLocalPath("");
    loadDirs("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit() {
    if (!name.trim()) {
      setError("Nom requis");
      return;
    }
    if (!localPath.trim()) {
      setError("Sélectionnez un dossier de travail");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const s = await api.createSession(name.trim(), localPath.trim());
      onCreated(s);
    } catch (err: any) {
      setError(err?.message || "Impossible de créer la session");
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: "0 0 14px" }}>Nouvelle session</h3>

        <label className="label">Nom du projet</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="ex: mon-projet"
          autoFocus
        />

        <div style={{ marginTop: 14 }}>
          <label className="label">Dossier de travail</label>
          <div className="dirpicker">
            <div className="dirpicker-head">
              <button
                className="btn ghost sm"
                disabled={!parent}
                onClick={() => parent && loadDirs(parent)}
                title="Dossier parent"
              >
                <FolderUp size={14} />
              </button>
              <input
                value={localPath}
                onChange={(e) => {
                  setLocalPath(e.target.value);
                  setCurrent(e.target.value);
                }}
                onKeyDown={(e) => e.key === "Enter" && loadDirs(current)}
                placeholder="/chemin/vers/dossier"
              />
              <button className="btn ghost sm" onClick={() => loadDirs(current)} title="Aller">
                <FolderOpen size={14} />
              </button>
            </div>
            <div className="dirpicker-list">
              {dirs.length === 0 && <div className="hint">Aucun sous-dossier.</div>}
              {dirs.map((d) => (
                <div
                  key={d.path}
                  className="dirpicker-item"
                  onClick={() => {
                    setLocalPath(d.path);
                    loadDirs(d.path);
                  }}
                >
                  <FolderGit2 size={14} style={{ color: "var(--color-accent)" }} />
                  <span className="truncate">{d.name}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {error && <div className="error-text">{error}</div>}

        <div style={{ display: "flex", gap: 10, marginTop: 16, justifyContent: "flex-end" }}>
          <button className="btn ghost" onClick={onClose}>
            Annuler
          </button>
          <button className="btn" onClick={submit} disabled={busy}>
            {busy ? "Création…" : "Créer"}
          </button>
        </div>
      </div>
    </div>
  );
}