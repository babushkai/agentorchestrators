import { useCallback, useEffect, useMemo, useState, type ComponentType } from "react";
import { AlertCircle, CheckCircle2, Loader2, MessageCircle, RefreshCw, Send, Users, Zap } from "lucide-react";
import { AgentService } from "@/lib/api/agents";
import { ConversationService } from "@/lib/api/conversations";
import { apiConfig } from "@/lib/api/client";
import type { Agent, ConversationMessage, ConversationSession, CreateAgentRequest } from "@/types/api";
import { cn } from "@/lib/utils";

// Provider/model choices used when auto-creating agents
const PROVIDER_OPTIONS = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
];

const MODEL_OPTIONS: Record<string, { value: string; label: string }[]> = {
  anthropic: [
    { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
    { value: "claude-3-5-sonnet-20241022", label: "Claude 3.5 Sonnet" },
    { value: "claude-3-haiku-20240307", label: "Claude 3 Haiku" },
  ],
  openai: [
    { value: "gpt-4.1", label: "GPT-4.1" },
    { value: "gpt-4o-mini", label: "GPT-4o Mini" },
    { value: "gpt-4o", label: "GPT-4o" },
  ],
};

const statusStyles: Record<string, { badge: string; dot: string }> = {
  active: { badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200", dot: "bg-emerald-400" },
  running: { badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200", dot: "bg-emerald-400" },
  idle: { badge: "border-slate-500/40 bg-slate-800 text-slate-200", dot: "bg-slate-300" },
  pending: { badge: "border-blue-500/30 bg-blue-500/10 text-blue-100", dot: "bg-blue-400" },
  completed: { badge: "border-emerald-600/50 bg-emerald-600/15 text-emerald-100", dot: "bg-emerald-400" },
  failed: { badge: "border-rose-500/40 bg-rose-500/10 text-rose-100", dot: "bg-rose-400" },
  error: { badge: "border-rose-500/40 bg-rose-500/10 text-rose-100", dot: "bg-rose-400" },
};

function StatusBadge({ status }: { status: string }) {
  const key = status?.toLowerCase() ?? "";
  const style = statusStyles[key] ?? { badge: "border-slate-600/50 bg-slate-800 text-slate-100", dot: "bg-slate-300" };
  return (
    <span className={cn("inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium capitalize", style.badge)}>
      <span className={cn("h-2 w-2 rounded-full", style.dot)} />
      {status || "unknown"}
    </span>
  );
}

function StatPill({ label, value, icon: Icon }: { label: string; value: string | number; icon: ComponentType<{ className?: string }> }) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2 text-sm text-slate-200">
      <Icon className="h-4 w-4 text-slate-400" />
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
        <div className="text-sm font-semibold text-slate-100">{value}</div>
      </div>
    </div>
  );
}

function formatDate(value: string | undefined | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

export default function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messageInput, setMessageInput] = useState("");
  const [banner, setBanner] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingSession, setCreatingSession] = useState(false);
  const [sending, setSending] = useState(false);

  const selectedAgent = useMemo(() => agents.find((a) => a.agent_id === selectedAgentId) ?? agents[0], [agents, selectedAgentId]);

  const ensureAgent = useCallback(async () => {
    try {
      const existing = await AgentService.list();
      if (existing.length > 0) {
        setAgents(existing);
        setSelectedAgentId((prev) => prev ?? existing[0].agent_id);
        return existing[0];
      }
      const provider = PROVIDER_OPTIONS[0].value;
      const model = MODEL_OPTIONS[provider]?.[0]?.value ?? "claude-sonnet-4-20250514";
      const payload: CreateAgentRequest = {
        name: "Orchestrator",
        role: "Primary orchestrator",
        goal: "Coordinate tasks and conversations",
        capabilities: ["coordination", "analysis"],
        llm_config: {
          provider,
          model_id: model,
          temperature: 0.7,
          max_tokens: 4096,
        },
      };
      const created = await AgentService.create(payload);
      setAgents([created]);
      setSelectedAgentId(created.agent_id);
      return created;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load agents";
      setBanner({ type: "error", text: message });
      throw error;
    }
  }, []);

  const loadSessions = useCallback(
    async (agentId?: string) => {
      try {
        const list = await ConversationService.list(agentId);
        setSessions(list);
        if (list.length === 0) {
          setSelectedSessionId(null);
          setMessages([]);
          return list;
        }
        setSelectedSessionId((prev) => (prev && list.find((s) => s.session_id === prev) ? prev : list[0].session_id));
        return list;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load sessions";
        setBanner({ type: "error", text: message });
        return [];
      }
    },
    [],
  );

  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const history = await ConversationService.history(sessionId);
      setMessages(history);
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Failed to load messages" });
    }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const agent = await ensureAgent();
        await loadSessions(agent.agent_id);
      } finally {
        setLoading(false);
      }
    })();
  }, [ensureAgent, loadSessions]);

  useEffect(() => {
    if (selectedSessionId) {
      loadHistory(selectedSessionId);
    }
  }, [selectedSessionId, loadHistory]);

  const handleCreateSession = async () => {
    setCreatingSession(true);
    try {
      const agent = selectedAgent || (await ensureAgent());
      const session = await ConversationService.create({
        agent_id: agent.agent_id,
        title: `Chat with ${agent.name}`,
      });
      await loadSessions(agent.agent_id);
      setSelectedSessionId(session.session_id);
      await loadHistory(session.session_id);
      setBanner({ type: "success", text: "Conversation session created" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to create session" });
    } finally {
      setCreatingSession(false);
    }
  };

  const handleSendMessage = async () => {
    if (!selectedSessionId || !messageInput.trim()) return;
    const content = messageInput.trim();
    const optimistic: ConversationMessage = {
      message_id: `local-${Date.now()}`,
      role: "user",
      content,
      timestamp: new Date().toISOString(),
      tool_calls: [],
    };
    setMessages((prev) => [...prev, optimistic]);
    setMessageInput("");
    setSending(true);
    try {
      await ConversationService.sendMessage(selectedSessionId, { content });
      await loadHistory(selectedSessionId);
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Failed to send message" });
    } finally {
      setSending(false);
    }
  };

  const stats = useMemo(() => ({
    agents: agents.length,
    sessions: sessions.length,
  }), [agents.length, sessions.length]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-900/80 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Agent Orchestrator</p>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-white">Conversation Console</h1>
              <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-400">
                {apiConfig.baseUrl}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => loadSessions(selectedAgent?.agent_id)}
              className="flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500"
              type="button"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Refresh sessions
            </button>
            <button
              onClick={handleCreateSession}
              disabled={creatingSession}
              className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/15 px-4 py-2 text-sm font-semibold text-emerald-50 hover:border-emerald-500 disabled:opacity-60"
              type="button"
            >
              {creatingSession ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
              New session
            </button>
          </div>
        </div>
        {banner && (
          <div
            className={cn(
              "mx-auto mt-1 flex max-w-6xl items-center gap-3 px-6 pb-3 text-sm",
              banner.type === "error" && "text-rose-200",
              banner.type === "success" && "text-emerald-200",
              banner.type === "info" && "text-blue-200",
            )}
          >
            {banner.type === "error" ? <AlertCircle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
            {banner.text}
          </div>
        )}
      </header>

      <main className="mx-auto max-w-6xl px-6 py-6 space-y-4">
        <div className="flex flex-wrap gap-3">
          <StatPill label="Agents" value={stats.agents} icon={Users} />
          <StatPill label="Sessions" value={stats.sessions} icon={MessageCircle} />
          <StatPill label="Status" value={selectedAgent ? selectedAgent.status : "pending"} icon={Zap} />
        </div>

        {loading && (
          <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Connecting to orchestrator...
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-3">
            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
              <div className="border-b border-slate-800 px-4 py-3 text-xs uppercase tracking-wide text-slate-500">Sessions</div>
              <div className="max-h-[60vh] divide-y divide-slate-800/80 overflow-y-auto">
                {sessions.map((session) => (
                  <button
                    key={session.session_id}
                    onClick={() => setSelectedSessionId(session.session_id)}
                    className={cn(
                      "w-full px-4 py-3 text-left hover:bg-slate-800/50",
                      selectedSessionId === session.session_id && "bg-slate-800/60",
                    )}
                    type="button"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm font-semibold text-slate-50">{session.title || "Untitled session"}</p>
                        <p className="text-[11px] text-slate-500">Messages: {session.message_count}</p>
                      </div>
                      <StatusBadge status={session.status} />
                    </div>
                    <p className="text-[11px] text-slate-500">Updated {formatDate(session.last_activity_at)}</p>
                  </button>
                ))}
                {sessions.length === 0 && (
                  <div className="px-4 py-6 text-center text-sm text-slate-500">No sessions yet. Create one to start chatting.</div>
                )}
              </div>
            </div>
          </div>

          <div className="lg:col-span-2 space-y-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Conversation</p>
                  <h3 className="text-lg font-semibold text-slate-50">
                    {selectedSessionId ? `Chatting with ${selectedAgent?.name ?? "agent"}` : "Select or create a session"}
                  </h3>
                </div>
                {selectedAgent && <StatusBadge status={selectedAgent.status} />}
              </div>

              <div className="mb-3 h-[55vh] space-y-3 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                {messages.map((msg) => {
                  const isUser = msg.role === "user";
                  return (
                    <div
                      key={msg.message_id}
                      className={cn(
                        "flex gap-3 rounded-lg border border-slate-800/80 p-3",
                        isUser ? "bg-slate-900/70" : "bg-emerald-900/10 border-emerald-800/40",
                      )}
                    >
                      <div className="mt-0.5">
                        {isUser ? <Users className="h-4 w-4 text-slate-400" /> : <Zap className="h-4 w-4 text-emerald-400" />}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-semibold text-slate-100">{isUser ? "You" : "Agent"}</p>
                          <p className="text-[11px] text-slate-500">{formatDate(msg.timestamp)}</p>
                        </div>
                        <p className="mt-1 whitespace-pre-wrap text-sm text-slate-100">{msg.content}</p>
                      </div>
                    </div>
                  );
                })}
                {messages.length === 0 && (
                  <div className="flex h-full items-center justify-center text-sm text-slate-500">
                    {selectedSessionId ? "No messages yet. Say hello to start." : "Choose a session to view messages."}
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/80 p-3">
                <input
                  value={messageInput}
                  onChange={(e) => setMessageInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={!selectedSessionId}
                  placeholder={selectedSessionId ? "Send a message to the agent" : "Create a session to start chatting"}
                  className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500 disabled:cursor-not-allowed disabled:opacity-70"
                />
                <button
                  onClick={handleSendMessage}
                  disabled={!selectedSessionId || sending}
                  className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/10 px-3 py-2 text-sm font-semibold text-emerald-50 hover:border-emerald-500 disabled:opacity-60"
                  type="button"
                >
                  {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
