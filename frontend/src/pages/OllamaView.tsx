import { useCallback, useEffect, useRef, useState } from "react";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import { api, type OllamaModel } from "../api";

interface PullState {
  task_id: string;
  model: string;
  status: string;
  message: string;
  percent: number;
  completed: number;
  total: number;
}

function formatBytes(bytes: number): string {
  if (!bytes) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${units[i]}`;
}

const MESSAGE_LABELS: Record<string, string> = {
  "pulling manifest": "Récupération du manifeste",
  downloading: "Téléchargement",
  "verifying sha256 digest": "Vérification",
  "writing manifest": "Écriture du manifeste",
  "removing any unused layers": "Nettoyage",
  success: "Terminé",
  terminated: "Terminé",
};

export default function OllamaView() {
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [loading, setLoading] = useState(true);
  const [pullName, setPullName] = useState("");
  const [pulls, setPulls] = useState<PullState[]>([]);
  const timerRef = useRef<number | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.ollamaModels();
      setModels(r.models);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (pulls.some((p) => p.status === "pulling")) {
      timerRef.current = window.setInterval(() => pollAll(), 1000);
    } else if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pulls]);

  async function pollAll() {
    const active = pulls.filter((p) => p.status === "pulling");
    if (!active.length) return;
    const updated = await Promise.all(
      active.map(async (p) => {
        try {
          const s = await api.pullStatus(p.task_id);
          if (s.status !== "pulling") await load();
          return s;
        } catch {
          return p;
        }
      }),
    );
    setPulls((prev) => prev.map((p) => updated.find((u) => u.task_id === p.task_id) ?? p));
  }

  async function startPull() {
    const name = pullName.trim();
    if (!name) return;
    try {
      const res = await api.pullModel(name);
      const taskId = res.task_id;
      if (taskId) {
        setPulls((prev) => [
          ...prev,
          { task_id: taskId, model: name, status: "pulling", message: "initialisation", percent: 0, completed: 0, total: 0 },
        ]);
      } else {
        await load();
      }
      setPullName("");
    } catch (e: any) {
      alert(e.message || "Échec du pull");
    }
  }

  async function remove(name: string) {
    if (!confirm(`Supprimer le modèle ${name} ?`)) return;
    await api.deleteModel(name);
    await load();
  }

  return (
    <div className="panel-body" style={{ flex: 1, overflowY: "auto" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Modèles Ollama</h2>
        <button className="btn ghost sm" onClick={load}>
          <RefreshCw size={13} /> Rafraîchir
        </button>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          className="pull-input"
          value={pullName}
          onChange={(e) => setPullName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && startPull()}
          placeholder="Nom du modèle (ex: qwen2.5-coder:7b)"
          style={{ flex: 1 }}
        />
        <button className="btn" onClick={startPull} disabled={!pullName.trim()}>
          <Download size={15} /> Pull
        </button>
      </div>

      {pulls.length > 0 && (
        <div className="list" style={{ marginBottom: 16 }}>
          {pulls.map((p) => (
            <div key={p.task_id} className="list-row" style={{ cursor: "default" }}>
              <div className="name">{p.model}</div>
              <div className="sub" style={{ marginBottom: 6 }}>
                {MESSAGE_LABELS[p.message] ?? p.message}
                {p.status === "pulling" && ` — ${p.percent}%`}
                {p.status === "success" && " ✓"}
                {p.status === "error" && " ✗"}
              </div>
              {p.status === "pulling" && (
                <div style={{ height: 6, background: "var(--color-bg)", borderRadius: 4, overflow: "hidden" }}>
                  <div
                    style={{ height: "100%", width: `${p.percent}%`, background: "var(--color-accent)", transition: "width .3s" }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="list">
        {loading && <div className="sub">Chargement…</div>}
        {!loading && models.length === 0 && <div className="sub">Aucun modèle installé.</div>}
        {models.map((m) => (
          <div key={m.name} className="list-row" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="name mono" style={{ flex: 1, fontWeight: 500 }}>{m.name}</span>
            <span className="sub">{formatBytes(m.size)}</span>
            <button className="btn ghost sm" onClick={() => remove(m.name)} title="Désinstaller">
              <Trash2 size={13} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
