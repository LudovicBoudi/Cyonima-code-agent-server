import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import { api, type CatalogModel, type OllamaModel } from "../api";

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
  const [catalog, setCatalog] = useState<CatalogModel[]>([]);
  const [catalogFilter, setCatalogFilter] = useState("");
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

  const loadCatalog = useCallback(async () => {
    try {
      const r = await api.ollamaCatalog();
      setCatalog(r.catalog);
    } catch {
      /* Ollama injoignable : catalogue vide */
    }
  }, []);

  useEffect(() => {
    load();
    loadCatalog();
  }, [load, loadCatalog]);

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
    let finished = false;
    const updated = await Promise.all(
      active.map(async (p) => {
        try {
          const s = await api.pullStatus(p.task_id);
          if (s.status !== "pulling") finished = true;
          return s;
        } catch {
          return p;
        }
      }),
    );
    if (finished) {
      await Promise.all([load(), loadCatalog()]);
    }
    setPulls((prev) => prev.map((p) => updated.find((u) => u.task_id === p.task_id) ?? p));
  }

  async function startPull(name: string) {
    if (!name.trim()) return;
    try {
      const res = await api.pullModel(name);
      const taskId = res.task_id;
      if (taskId) {
        setPulls((prev) => [
          ...prev,
          { task_id: taskId, model: name, status: "pulling", message: "initialisation", percent: 0, completed: 0, total: 0 },
        ]);
      } else {
        await Promise.all([load(), loadCatalog()]);
      }
    } catch (e: any) {
      alert(e.message || "Échec du pull");
    }
    setPullName("");
  }

  async function remove(name: string) {
    if (!confirm(`Supprimer le modèle ${name} ?`)) return;
    await api.deleteModel(name);
    await Promise.all([load(), loadCatalog()]);
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
          onKeyDown={(e) => e.key === "Enter" && startPull(pullName)}
          placeholder="Nom du modèle (ex: qwen2.5-coder:7b)"
          style={{ flex: 1 }}
        />
        <button className="btn" onClick={() => startPull(pullName)} disabled={!pullName.trim()}>
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

      <CatalogSection
        catalog={catalog}
        pulls={pulls}
        filter={catalogFilter}
        onFilterChange={setCatalogFilter}
        onPull={startPull}
      />
    </div>
  );
}

function CatalogSection({
  catalog,
  pulls,
  filter,
  onFilterChange,
  onPull,
}: {
  catalog: CatalogModel[];
  pulls: PullState[];
  filter: string;
  onFilterChange: (v: string) => void;
  onPull: (name: string) => void;
}) {
  const lower = filter.trim().toLowerCase();
  const filtered = useMemo(
    () =>
      lower
        ? catalog.filter(
            (m) =>
              m.name.toLowerCase().includes(lower) ||
              m.ollama_tag.toLowerCase().includes(lower) ||
              m.license.toLowerCase().includes(lower),
          )
        : catalog,
    [catalog, lower],
  );
  const installed = filtered.filter((m) => m.installed);
  const available = filtered.filter((m) => !m.installed);

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>Catalogue</h3>
        <span className="sub">
          {available.length + installed.length} / {catalog.length} modèles recommandés
        </span>
        <input
          className="pull-input"
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          placeholder="Filtrer le catalogue…"
          style={{ marginLeft: "auto", width: 220 }}
        />
      </div>

      <CatalogList items={installed} pulls={pulls} onPull={onPull} title="Modèles installés" empty="Aucun modèle du catalogue installé." />
      <CatalogList items={available} pulls={pulls} onPull={onPull} title="Autres modèles disponibles" empty="Aucun autre modèle à afficher." />
    </div>
  );
}

function CatalogList({
  items,
  pulls,
  onPull,
  title,
  empty,
}: {
  items: CatalogModel[];
  pulls: PullState[];
  onPull: (name: string) => void;
  title: string;
  empty: string;
}) {
  const pullingTag = (tag: string) => pulls.some((p) => p.model.trim() === tag && p.status === "pulling");
  return (
    <div style={{ marginBottom: 12 }}>
      <div className="panel-title" style={{ fontSize: 12, textTransform: "none", marginBottom: 6 }}>
        {title} ({items.length})
      </div>
      {items.length === 0 && <div className="sub">{empty}</div>}
      {items.map((m) => (
        <div key={m.id} className="list-row" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="name" style={{ whiteSpace: "normal", lineHeight: 1.35 }}>{m.name}</div>
            <div className="sub mono" style={{ fontSize: 11.5 }}>
              <code>{m.ollama_tag}</code>
              <span style={{ margin: "0 6px" }}>·</span>
              {m.model_type === "coding" ? "Code" : "Général"}
              <span style={{ margin: "0 6px" }}>·</span>
              Q{m.quantization}
              <span style={{ margin: "0 6px" }}>·</span>
              RAM min {m.ram_min_gb} Go
              <span style={{ margin: "0 6px" }}>·</span>
              {m.license}
            </div>
          </div>
          {m.installed ? (
            <button className="btn ghost sm" onClick={() => onPull(m.ollama_tag)} disabled={false} title="Re-pull">
              <RefreshCw size={13} /> Pull
            </button>
          ) : (
            <button className="btn sm" onClick={() => onPull(m.ollama_tag)} disabled={pullingTag(m.ollama_tag)}>
              <Download size={13} /> {pullingTag(m.ollama_tag) ? "En cours…" : "Installer"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
