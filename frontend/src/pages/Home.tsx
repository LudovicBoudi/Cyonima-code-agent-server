import { useEffect, useState } from "react";
import { Bot, FolderGit2, LogOut, Plus, Building2, MessageSquare, Boxes } from "lucide-react";
import { api, type Organization, type Session, type Workspace } from "../api";
import { useAuth } from "../store/auth";
import SessionView from "./SessionView";
import OllamaView from "./OllamaView";

export default function Home() {
  const { user, logout } = useAuth();
  const [view, setView] = useState<"main" | "ollama">("main");
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [orgId, setOrgId] = useState<string>("");
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSession, setActiveSession] = useState<Session | null>(null);

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
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const org = await api.createOrg(name, slug);
    setOrgs((o) => [...o, org]);
    setOrgId(org.id);
  }

  async function createWorkspace() {
    const name = prompt("Nom du workspace");
    if (!name) return;
    const slug = name.toLowerCase().replace(/[^a-z0-9]+/g, "-");
    const git = prompt("URL git (optionnel, laisser vide pour un workspace vide)") || "";
    const ws = await api.createWorkspace(orgId, name, slug, git);
    setWorkspaces((w) => [...w, ws]);
    setWorkspaceId(ws.id);
  }

  async function createSession() {
    const s = await api.createSession(workspaceId);
    setSessions((prev) => [s, ...prev]);
    setActiveSession(s);
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
            <span style={{ cursor: "pointer", color: "var(--color-accent)" }} onClick={createWorkspace}>
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
    </div>
  );
}
