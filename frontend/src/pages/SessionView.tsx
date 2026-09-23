import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Send, Square, Loader2 } from "lucide-react";
import { api, wsUrl, type Message, type OllamaModel, type Session } from "../api";

interface ToolCallBlock {
  id: string;
  name: string;
  arguments: any;
  output?: string;
  isError?: boolean;
  status: "pending" | "running" | "done" | "refused";
}

interface StreamState {
  content: string;
  thinking: string;
  toolCalls: ToolCallBlock[];
}

interface PermissionRequest {
  id?: string;
  call_id: string;
  tool: string;
  arguments: any;
  preview: string;
  status?: string;
}

const REASONING_OPTIONS = ["auto", "off", "low", "medium", "high"];

export default function SessionView({ session }: { session: Session }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [stream, setStream] = useState<StreamState | null>(null);
  const [models, setModels] = useState<OllamaModel[]>([]);
  const [model, setModel] = useState(session.model || "");
  const [reasoning, setReasoning] = useState(session.reasoning || "auto");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [perms, setPerms] = useState<PermissionRequest[]>([]);
  const [usage, setUsage] = useState<Record<string, number> | null>(null);
  const [files, setFiles] = useState<{ status: string; path: string }[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const thinkingRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.history(session.id).then(setMessages);
    api.ollamaModels().then((r) => {
      setModels(r.models);
      setModel((cur) => {
        const inList = r.models.some((m) => m.name === (cur || ""));
        if (inList) return cur;
        const resolved =
          r.models.find((m) => m.name === r.default_model)?.name ||
          r.models[0]?.name ||
          cur ||
          "";
        return resolved;
      });
    });
    loadGitStatus();
    loadPendingPermissions();

    const ws = new WebSocket(wsUrl(session.id));
    wsRef.current = ws;
    ws.onmessage = (ev) => {
      const event = JSON.parse(ev.data);
      handleEvent(event);
    };
    return () => ws.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.id]);

  async function loadPendingPermissions() {
    try {
      const pending = await api.permissions(session.id);
      setPerms((prev) => {
        const known = new Set(prev.map((p) => p.call_id));
        return [...prev, ...pending.filter((p) => !known.has(p.call_id))];
      });
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, stream]);

  useEffect(() => {
    thinkingRef.current?.scrollTo(0, thinkingRef.current.scrollHeight);
  }, [stream?.thinking]);

  async function loadGitStatus() {
    try {
      const data = await api.gitStatus(session.id);
      setFiles(data.changes || []);
    } catch {
      /* ignore */
    }
  }

  function handleEvent(event: any) {
    switch (event.type) {
      case "token":
        setStream((s) => ({ ...(s ?? { content: "", thinking: "", toolCalls: [] }), content: (s?.content ?? "") + event.token }));
        break;
      case "thinking":
        setStream((s) => ({ ...(s ?? { content: "", thinking: "", toolCalls: [] }), thinking: (s?.thinking ?? "") + event.token }));
        break;
      case "tool_call":
        setStream((s) => {
          const tcs = [...(s?.toolCalls ?? [])];
          tcs.push({ id: event.call_id, name: event.tool, arguments: event.arguments, status: "running" });
          return { ...(s ?? { content: "", thinking: "", toolCalls: [] }), toolCalls: tcs };
        });
        break;
      case "tool_result":
        setStream((s) => {
          const tcs = (s?.toolCalls ?? []).map((t) =>
            t.id === event.call_id
              ? { ...t, output: event.output, isError: event.is_error, status: "done" as const }
              : t,
          );
          return { ...(s ?? { content: "", thinking: "", toolCalls: [] }), toolCalls: tcs };
        });
        break;
      case "permission_request":
        setPerms((prev) => {
          if (prev.some((p) => p.call_id === event.call_id)) return prev;
          return [...prev, event];
        });
        break;
      case "done":
        setUsage(event.usage ?? null);
        setBusy(false);
        finalizeStream();
        loadGitStatus();
        break;
      case "error":
        setBusy(false);
        setStream((s) => ({ ...(s ?? { content: "", thinking: "", toolCalls: [] }), content: (s?.content ?? "") + `\n\n⚠️ ${event.error}` }));
        break;
    }
  }

  function finalizeStream() {
    setStream((s) => {
      if (!s) return null;
      const assistant: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: s.content,
        tool_calls: s.toolCalls.map((t) => ({ id: t.id, name: t.name, arguments: t.arguments })),
      };
      setMessages((m) => [...m, assistant]);
      return null;
    });
  }

  function send() {
    if (!input.trim() || busy) return;
    wsRef.current?.send(JSON.stringify({ type: "send", message: input, model, reasoning }));
    setMessages((m) => [...m, { id: crypto.randomUUID(), role: "user", content: input }]);
    setInput("");
    setBusy(true);
    setStream({ content: "", thinking: "", toolCalls: [] });
  }

  function stop() {
    wsRef.current?.send(JSON.stringify({ type: "cancel" }));
  }

  async function respondPermission(callId: string, approved: boolean) {
    setPerms((prev) => prev.filter((p) => p.call_id !== callId));
    try {
      await api.respondPermission(session.id, callId, approved);
    } catch {
      /* la demande a pu expirer */
    }
  }

  return (
    <div className="session">
      <div className="col-chat">
        <div className="messages">
          {messages.map((m) => (
            <div key={m.id} className={`msg ${m.role}`}>
              <div className="role">{m.role}</div>
              {m.role === "assistant" && m.tool_calls && m.tool_calls.length > 0 && (
                <div style={{ marginBottom: 6 }}>
                  {m.tool_calls.map((tc) => (
                    <div key={tc.id} className="mono" style={{ fontSize: 12, color: "var(--color-muted)" }}>
                      ▸ {tc.name}
                    </div>
                  ))}
                </div>
              )}
              {m.role === "tool" && (
                <ToolBlock name={m.meta?.tool || "tool"} arguments={m.meta?.tool ? {} : {}} output={m.content} />
              )}
              {m.content && m.role !== "tool" && (
                <div className="bubble">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              )}
            </div>
          ))}

          {stream && (
            <div className="msg assistant">
              <div className="role">assistant</div>
              {stream.toolCalls.map((tc) => (
                <ToolBlock key={tc.id} name={tc.name} arguments={tc.arguments} output={tc.output} status={tc.status} />
              ))}
              {stream.content && (
                <div className="bubble">
                  <ReactMarkdown>{stream.content}</ReactMarkdown>
                </div>
              )}
              {!stream.content && stream.toolCalls.length === 0 && <Loader2 className="spin" size={16} />}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {perms.map((perm) => (
          <div className="permission-bar" key={perm.call_id}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              Approbation requise — <code>{perm.tool}</code>
            </div>
            <div className="mono" style={{ fontSize: 12.5 }}>{perm.preview}</div>
            <pre className="mono" style={{ fontSize: 11, maxHeight: 100, overflow: "auto" }}>
              {JSON.stringify(perm.arguments, null, 2)}
            </pre>
            <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
              <button className="btn sm" onClick={() => respondPermission(perm.call_id, true)}>Autoriser</button>
              <button className="btn sm danger" onClick={() => respondPermission(perm.call_id, false)}>Refuser</button>
            </div>
          </div>
        ))}

        <div className="chatbox">
          <div className="controls">
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              {!models.some((m) => m.name === model) && (
                <option value={model}>{model || "Modèle"}</option>
              )}
              {models.map((m) => (
                <option key={m.name} value={m.name}>{m.name}</option>
              ))}
            </select>
            <select value={reasoning} onChange={(e) => setReasoning(e.target.value)}>
              {REASONING_OPTIONS.map((r) => (
                <option key={r} value={r}>Raisonnement: {r}</option>
              ))}
            </select>
            {usage && (
              <span className="ctx">
                ↑{usage.prompt_tokens ?? 0} ↓{usage.completion_tokens ?? 0}
              </span>
            )}
          </div>
          <div className="row">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Décrivez votre tâche… (Entrée pour envoyer)"
              rows={2}
            />
            {busy ? (
              <button className="btn" onClick={stop} title="Arrêter">
                <Square size={16} />
              </button>
            ) : (
              <button className="btn" onClick={send} disabled={!input.trim()} title="Envoyer">
                <Send size={16} />
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="col-thinking">
        <div className="panel-title">Raisonnement</div>
        <div className="panel-body" ref={thinkingRef}>
          {stream?.thinking ? (
            <pre style={{ whiteSpace: "pre-wrap", fontFamily: "monospace", fontSize: 12, margin: 0 }}>
              {stream.thinking}
            </pre>
          ) : (
            <div className="muted" style={{ color: "var(--color-muted)" }}>
              Le raisonnement s'affichera ici…
            </div>
          )}
        </div>
      </div>

      <div className="col-files">
        <div className="panel-title">Fichiers modifiés</div>
        <div className="panel-body">
          {files.length === 0 ? (
            <div style={{ color: "var(--color-muted)" }}>Aucun fichier modifié.</div>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {files.map((f, i) => (
                <li key={i} className="mono" style={{ fontSize: 12.5, marginBottom: 4 }}>
                  <span style={{ color: "var(--color-accent)" }}>{f.status}</span> {f.path}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function ToolBlock({ name, arguments: args, output, status }: { name: string; arguments: any; output?: string; status?: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="tool-block">
      <div className="tool-head" onClick={() => setOpen(!open)}>
        <span>{open ? "▾" : "▸"}</span>
        <code>{name}</code>
        {status === "running" && <Loader2 className="spin" size={13} />}
      </div>
      {open && (
        <div className="tool-result">
          <div style={{ color: "var(--color-muted)", marginBottom: 4 }}>Arguments</div>
          <pre className="mono" style={{ margin: 0, fontSize: 11 }}>{JSON.stringify(args, null, 2)}</pre>
          {output !== undefined && (
            <>
              <div style={{ color: "var(--color-muted)", margin: "6px 0 4px" }}>Résultat</div>
              <pre className="mono" style={{ margin: 0, fontSize: 11 }}>{String(output)}</pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}
