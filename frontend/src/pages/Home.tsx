import { useEffect, useState } from "react";
import { Bot, FolderGit2, LogOut, Plus, Building2, MessageSquare, Boxes, ShieldCheck, FolderUp, FolderOpen } from "lucide-react";
import { api, type Organization, type Session, type Workspace } from "../api";
import { useAuth } from "../store/auth";
import SessionView from "./SessionView";
import OllamaView from "./OllamaView";
import AdminUsers from "./AdminUsers";

type Source = "empty" | "git" | "local";

function slugify(s: string) {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
}

export default function Home() {
  const { user, logout } = useAuth();
  const [view, setView] = useState<"main" | "ollama" | "admin">("main");
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);
  const [showWsModal, setShowWsModal] = useState(false);

  useEffect(() => {
    api.orgs().then((o) => {
      setOrgs(o);
      if (o.length) setOrgId(o[0].id);
    });
  }, []);

  useEffect(() => {
    if (!orgId) return;
    api.workspaces(orgId).then((w) => {
      setWorkspaces(w);
      setWorkspaceId("");
      setSessions([]);
    });
  }, [orgId]);

  useEffect(() => {
    if (!workspaceId) {
      setSessions([]);
      return;
    }
    api.sessions(workspaceId).then(setSessions);
  }, [workspaceId]);

  useEffect(() => {
    // Polling pendant le provisioning (status "creating")
    const creating = workspaces.some((w) => w.status === "creating");
    if (!creating || !orgId) return;
    const t = window.setInterval(() => {
      api.workspaces(orgId).then(setWorkspaces);
    }, 2000);
    return () => window.clearInterval(t);
  }, [workspaces, orgId]);

  async function createOrg() {
    const name = prompt("Nom de l'organisation");
    if (!name) return;
    const slug = slugify(name);
    try {
      const org = await api.createOrg(name, slug);
      setOrgs((o) => [...o, org]);
      setOrgId(org.id);
    } catch (err: any) {
      alert(err?.message || "Impossible de créer l'organisation");
    }
  }

  async function onWorkspaceCreated(ws: Workspace) {
    setWorkspaces((w) => [...w, ws]);
    setWorkspaceId(ws.id);
    setShowWsModal(false);
  }

  async function createSession() {
    try {
      const s = await api.createSession(workspaceId);
      setSessions((prev) => [s, ...prev]);
      setActiveSession(s);
      setView("main");
    } catch (err: any) {
      alert(err?.message || "Impossible de créer la session");
    }
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
              className={`item ${view === "admin" ? "active" : ""}`}
              onClick={() => setView("admin")}
            >
              <ShieldCheck size={15} />
              <span className="truncate">Administration</span>
            </div>
          )}

          <div className="section">Organisation</div>
          <select
            value={orgId}
            onChange={(e) => setOrgId(e.target.value)}
            style={{ width: "100%", marginBottom: 6 }}
          >
            {orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
          <button className="btn ghost sm" onClick={createOrg} style={{ width: "100%" }}>
            <Plus size={14} /> Nouvelle organisation
          </button>

          <div className="section">
            Workspaces{" "}
            <span style={{ cursor: "pointer", color: "var(--color-accent)" }} onClick={() => setShowWsModal(true)}>
              <Plus size={13} style={{ display: "inline" }} />
            </span>
          </div>
          <div className="list">
            {workspaces.map((w) => (
              <div
                key={w.id}
                className={`item ${w.id === workspaceId ? "active" : ""}`}
                onClick={() => {
                  setWorkspaceId(w.id);
                  setView("main");
                }}
              >
                <FolderGit2 size={15} />
                <span className="truncate">{w.name}</span>
                {w.status === "creating" && <span className="sub">…</span>}
                {w.status === "error" && (
                  <span title="Erreur de provisioning" style={{ color: "var(--color-danger)" }}>
                    ⚠
                  </span>
                )}
              </div>
            ))}
          </div>

          {workspaceId && (
            <>
              <div className="section">
                Sessions{" "}
                <span style={{ cursor: "pointer", color: "var(--color-accent)" }} onClick={createSession}>
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
            </>
          )}
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
        ) : view === "admin" ? (
          <AdminUsers />
        ) : activeSession ? (
          <SessionView session={activeSession} />
        ) : (
          <div className="empty">
            <div>
              <Building2 size={32} style={{ color: "var(--color-accent)" }} />
              <h2>Bienvenue, {user?.name || user?.email}</h2>
              <p>
                Sélectionnez un workspace puis créez une session pour lancer un agent.
              </p>
              {workspaceId && (
                <button className="btn" onClick={createSession}>
                  <Plus size={16} /> Nouvelle session
                </button>
              )}
            </div>
          </div>
        )}
      </main>

      {showWsModal && (
        <WorkspaceModal
          orgId={orgId}
          onCreated={onWorkspaceCreated}
          onClose={() => setShowWsModal(false)}
        />
      )}
    </div>
  );
}

function WorkspaceModal({
  orgId,
  onCreated,
  onClose,
}: {
  orgId: string;
  onCreated: (ws: Workspace) => void;
  onClose: () => void;
}) {
  const [name, setName] = useState("");
  const [source, setSource] = useState<Source>("empty");
  const [gitUrl, setGitUrl] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [current, setCurrent] = useState("");
  const [dirs, setDirs] = useState<{ name: string; path: string }[]>([]);
  const [parent, setParent] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const slug = slugify(name);

  const loadDirs = async (path: string) => {
    setError("");
    try {
      const r = await api.localDirs(orgId, path || undefined);
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
    if (source === "local") {
      setLocalPath("");
      loadDirs("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source]);

  async function submit() {
    if (!name.trim()) {
      setError("Nom requis");
      return;
    }
    const localPathFinal = source === "local" ? localPath.trim() : "";
    const gitFinal = source === "git" ? gitUrl.trim() : "";
    if (source === "git" && !gitFinal) {
      setError("URL git requise");
      return;
    }
    if (source === "local" && !localPathFinal) {
      setError("Sélectionnez un dossier local");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const ws = await api.createWorkspace(orgId, name, slug, gitFinal, localPathFinal);
      onCreated(ws);
    } catch (err: any) {
      setError(err?.message || "Impossible de créer le workspace");
      setBusy(false);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3 style={{ margin: "0 0 14px" }}>Nouveau workspace</h3>

        <label className="label">Nom</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="ex: mon-projet"
          autoFocus
        />
        {name && <div className="hint">slug: {slug || "…"}</div>}

        <div style={{ margin: "12px 0", display: "flex", gap: 10, flexWrap: "wrap" }}>
          {(
            [
              ["local", "Dossier local"],
              ["git", "Dépôt Git"],
              ["empty", "Vide"],
            ] as [Source, string][]
          ).map(([key, label]) => (
            <label key={key} className="radio">
              <input type="radio" checked={source === key} onChange={() => setSource(key)} />
              {label}
            </label>
          ))}
        </div>

        {source === "git" && (
          <>
            <label className="label">URL du dépôt</label>
            <input
              value={gitUrl}
              onChange={(e) => setGitUrl(e.target.value)}
              placeholder="https://github.com/…/repo.git"
            />
          </>
        )}

        {source === "local" && (
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
        )}

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
