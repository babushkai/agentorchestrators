import { useCallback, useEffect, useMemo, useState, type ComponentType, type FormEvent } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Clock3,
   Loader2,
   MessageCircle,
   Play,
   Plus,
   RefreshCw,
   Send,
   ShieldHalf,
   Square,
   Users,
   Zap,
 } from "lucide-react";
import { AgentService } from "@/lib/api/agents";
import { TaskService } from "@/lib/api/tasks";
import { ConversationService } from "@/lib/api/conversations";
import { apiConfig } from "@/lib/api/client";
import type {
  Agent,
  ConversationMessage,
  ConversationSession,
  CreateAgentRequest,
  CreateTaskRequest,
  Task,
} from "@/types/api";
import { cn } from "@/lib/utils";


type Banner = { type: "success" | "error" | "info"; text: string };

type StatusStyle = {
  badge: string;
  dot: string;
};

const statusStyles: Record<string, StatusStyle> = {
  running: { badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-200", dot: "bg-emerald-400" },
  idle: { badge: "border-slate-500/40 bg-slate-800 text-slate-200", dot: "bg-slate-300" },
  stopped: { badge: "border-amber-500/30 bg-amber-500/10 text-amber-100", dot: "bg-amber-400" },
  pending: { badge: "border-blue-500/30 bg-blue-500/10 text-blue-100", dot: "bg-blue-400" },
  completed: { badge: "border-emerald-600/50 bg-emerald-600/15 text-emerald-100", dot: "bg-emerald-400" },
  failed: { badge: "border-rose-500/40 bg-rose-500/10 text-rose-100", dot: "bg-rose-400" },
  cancelled: { badge: "border-slate-600/50 bg-slate-700 text-slate-200", dot: "bg-slate-300" },
  error: { badge: "border-rose-500/40 bg-rose-500/10 text-rose-100", dot: "bg-rose-400" },
};

const priorityLabels: Record<number, string> = {
  0: "Low",
  1: "Normal",
  2: "High",
  3: "Urgent",
};

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

function StatusBadge({ status }: { status: string }) {
  const key = status?.toLowerCase() ?? "";
  const style = statusStyles[key] ?? {
    badge: "border-slate-600/50 bg-slate-800 text-slate-100",
    dot: "bg-slate-300",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium capitalize",
        style.badge,
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", style.dot)} />
      {status || "unknown"}
    </span>
  );
}

function StatCard({
  label,
  value,
  icon: Icon,
  tone,
  hint,
}: {
  label: string;
  value: string | number;
  icon: ComponentType<{ className?: string }>;
  tone?: "emerald" | "blue" | "amber" | "violet";
  hint?: string;
}) {
  const toneClasses: Record<string, string> = {
    emerald: "bg-emerald-500/10 text-emerald-100 border-emerald-500/30",
    blue: "bg-blue-500/10 text-blue-100 border-blue-500/30",
    amber: "bg-amber-500/10 text-amber-100 border-amber-500/30",
    violet: "bg-violet-500/10 text-violet-100 border-violet-500/30",
  };

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/30">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-slate-400">{label}</p>
          <p className="text-2xl font-semibold text-slate-50">{value}</p>
          {hint && <p className="text-xs text-slate-500 mt-1">{hint}</p>}
        </div>
        <div className={cn("rounded-full p-3 border", tone ? toneClasses[tone] : "border-slate-800 bg-slate-800")}>
          <Icon className="h-5 w-5" />
        </div>
      </div>
    </div>
  );
}

function Modal({
  open,
  title,
  onClose,
  children,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 px-4 py-12 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
          <div>
            <p className="text-sm uppercase tracking-wide text-slate-500">Dialog</p>
            <h2 className="text-xl font-semibold text-slate-50">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg border border-slate-700 px-3 py-2 text-slate-300 hover:border-slate-500 hover:text-white"
            type="button"
          >
            Close
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function AgentDetail({ agent, tasks }: { agent: Agent | undefined; tasks: Task[] }) {
  if (!agent) {
    return (
      <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-6 text-center text-slate-500">
        Select an agent to see details.
      </div>
    );
  }

  const assignedTasks = tasks.filter((task) => task.assigned_agent_id === agent.agent_id);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Agent</p>
          <h3 className="text-lg font-semibold text-slate-50">{agent.name}</h3>
          <p className="text-sm text-slate-400">{agent.role}</p>
        </div>
        <StatusBadge status={agent.status} />
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-4 text-sm text-slate-300">
        <div>
          <dt className="text-slate-500">Created</dt>
          <dd>{formatDate(agent.created_at)}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Last heartbeat</dt>
          <dd>{agent.last_heartbeat ? formatDate(agent.last_heartbeat) : "—"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Current task</dt>
          <dd>{agent.current_task_id ? agent.current_task_id : "None"}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Capabilities</dt>
          <dd className="flex flex-wrap gap-2">
            {agent.capabilities.length === 0 && <span className="text-slate-500">None</span>}
            {agent.capabilities.map((capability) => (
              <span
                key={capability}
                className="rounded-full border border-slate-700 bg-slate-800 px-2 py-1 text-xs text-slate-200"
              >
                {capability}
              </span>
            ))}
          </dd>
        </div>
      </dl>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-medium text-slate-200">Assigned tasks</p>
          <span className="text-xs text-slate-500">{assignedTasks.length} tracked</span>
        </div>
        <div className="space-y-2">
          {assignedTasks.length === 0 && <p className="text-sm text-slate-500">No tasks assigned yet.</p>}
          {assignedTasks.map((task) => (
            <div
              key={task.task_id}
              className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-900/80 px-3 py-2"
            >
              <div>
                <p className="text-sm text-slate-100">{task.name}</p>
                <p className="text-xs text-slate-500">Priority {priorityLabels[task.priority] ?? task.priority}</p>
              </div>
              <StatusBadge status={task.status} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AgentTable({
  agents,
  selectedId,
  onSelect,
  onStart,
  onStop,
  busyId,
}: {
  agents: Agent[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onStart: (id: string) => void;
  onStop: (id: string) => void;
  busyId: string | null;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
      <div className="grid grid-cols-[1.3fr_1fr_1fr_auto] items-center gap-3 border-b border-slate-800 px-4 py-3 text-xs uppercase tracking-wide text-slate-500">
        <span>Agent</span>
        <span>Status</span>
        <span>Capabilities</span>
        <span className="text-right">Actions</span>
      </div>
      <div className="divide-y divide-slate-800/80">
        {agents.map((agent) => {
          const isSelected = agent.agent_id === selectedId;
          const isRunning = agent.status.toLowerCase() === "running";
          const isBusy = busyId === agent.agent_id;

          return (
            <div
              key={agent.agent_id}
              className={cn(
                "grid grid-cols-[1.3fr_1fr_1fr_auto] items-center gap-3 px-4 py-4 hover:bg-slate-800/40",
                isSelected && "bg-slate-800/60",
              )}
            >
              <button
                className="flex items-start gap-3 text-left"
                onClick={() => onSelect(agent.agent_id)}
                type="button"
              >
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-800/80 text-slate-100">
                  <Users className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-50">{agent.name}</p>
                  <p className="text-xs text-slate-500">{agent.role}</p>
                  <p className="text-[11px] text-slate-600">Created {formatDate(agent.created_at)}</p>
                </div>
              </button>

              <div>
                <StatusBadge status={agent.status} />
              </div>

              <div className="flex flex-wrap gap-2 text-xs text-slate-200">
                {agent.capabilities.length === 0 && <span className="text-slate-500">None</span>}
                {agent.capabilities.map((capability) => (
                  <span
                    key={capability}
                    className="rounded-full border border-slate-700 bg-slate-800 px-2 py-1"
                  >
                    {capability}
                  </span>
                ))}
              </div>

              <div className="flex justify-end gap-2">
                {isRunning ? (
                  <button
                    onClick={() => onStop(agent.agent_id)}
                    disabled={isBusy}
                    className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:border-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                    type="button"
                  >
                    {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />}
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => onStart(agent.agent_id)}
                    disabled={isBusy}
                    className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/10 px-3 py-2 text-sm text-emerald-50 hover:border-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                    type="button"
                  >
                    {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                    Start
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {agents.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">No agents registered yet.</div>
        )}
      </div>
    </div>
  );
}

function TaskList({ tasks, agents, onCancel, busyId }: { tasks: Task[]; agents: Agent[]; onCancel: (id: string) => void; busyId: string | null }) {
  return (
    <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
      <div className="grid grid-cols-[1.3fr_1fr_auto_auto] items-center gap-3 border-b border-slate-800 px-4 py-3 text-xs uppercase tracking-wide text-slate-500">
        <span>Task</span>
        <span>Status</span>
        <span>Assignee</span>
        <span className="text-right">Actions</span>
      </div>
      <div className="divide-y divide-slate-800/80">
        {tasks.map((task) => {
          const assignee = agents.find((agent) => agent.agent_id === task.assigned_agent_id);
          const isCancelable = ["pending", "running"].includes((task.status || "").toLowerCase());
          const isBusy = busyId === task.task_id;

          return (
            <div
              key={task.task_id}
              className="grid grid-cols-[1.3fr_1fr_auto_auto] items-center gap-3 px-4 py-4 hover:bg-slate-800/40"
            >
              <div>
                <p className="text-sm font-semibold text-slate-50">{task.name}</p>
                <p className="text-xs text-slate-500">Created {formatDate(task.created_at)}</p>
                <p className="text-[11px] text-slate-400">Priority {priorityLabels[task.priority] ?? task.priority}</p>
              </div>
              <StatusBadge status={task.status} />
              <div className="text-sm text-slate-200">
                {assignee ? (
                  <div className="flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
                    {assignee.name}
                  </div>
                ) : (
                  <span className="text-slate-500">Unassigned</span>
                )}
              </div>
              <div className="flex justify-end">
                <button
                  onClick={() => onCancel(task.task_id)}
                  disabled={!isCancelable || isBusy}
                  className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-200 hover:border-rose-500 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                  type="button"
                >
                  {isBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Square className="h-4 w-4" />} Cancel
                </button>
              </div>
            </div>
          );
        })}
        {tasks.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-slate-500">No tasks created yet.</div>
        )}
      </div>
    </div>
  );
}

function ActivityTimeline({ tasks }: { tasks: Task[] }) {
  const ordered = [...tasks].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()).slice(0, 12);

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Activity</p>
          <h3 className="text-lg font-semibold text-slate-50">Recent events</h3>
        </div>
        <Activity className="h-5 w-5 text-slate-400" />
      </div>
      <div className="space-y-3">
        {ordered.map((task) => (
          <div key={task.task_id} className="flex items-center gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-800/60">
              <CheckCircle2 className="h-5 w-5 text-emerald-300" />
            </div>
            <div className="flex-1">
              <p className="text-sm font-medium text-slate-100">{task.name}</p>
              <p className="text-xs text-slate-500">{formatDate(task.created_at)}</p>
            </div>
            <StatusBadge status={task.status} />
          </div>
        ))}
        {ordered.length === 0 && <p className="text-sm text-slate-500">Nothing to show yet.</p>}
      </div>
    </div>
  );
}

function CreateAgentForm({ onSubmit, submitting }: { onSubmit: (payload: CreateAgentRequest) => void; submitting: boolean }) {
  const [form, setForm] = useState({
    name: "",
    role: "",
    goal: "",
    capabilities: "research,analysis",
    tools: "",
    provider: "anthropic",
    modelId: MODEL_OPTIONS.anthropic?.[0]?.value || "claude-sonnet-4-20250514",
    temperature: "0.7",
    maxTokens: "4096",
  });

  const modelOptions = MODEL_OPTIONS[form.provider] ?? [];

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const capabilities = form.capabilities
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const tools = form.tools
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    const payload: CreateAgentRequest = {
      name: form.name,
      role: form.role,
      goal: form.goal,
      tools,
      capabilities,
      llm_config: {
        provider: form.provider || "anthropic",
        model_id: form.modelId || MODEL_OPTIONS[form.provider]?.[0]?.value || "claude-sonnet-4-20250514",
        temperature: Number(form.temperature) || 0.7,
        max_tokens: Number(form.maxTokens) || 4096,
      },
    };

    onSubmit(payload);
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-slate-200">
          Name
          <input
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            placeholder="Research Orchestrator"
          />
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Role
          <input
            value={form.role}
            onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
            required
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            placeholder="Coordinator"
          />
        </label>
      </div>

      <label className="space-y-1 text-sm text-slate-200">
        Goal
        <textarea
          value={form.goal}
          onChange={(e) => setForm((prev) => ({ ...prev, goal: e.target.value }))}
          required
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          rows={3}
          placeholder="Coordinate specialists to deliver reliable outputs"
        />
      </label>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-slate-200">
          Capabilities (comma separated)
          <input
            value={form.capabilities}
            onChange={(e) => setForm((prev) => ({ ...prev, capabilities: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          />
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Tools (comma separated)
          <input
            value={form.tools}
            onChange={(e) => setForm((prev) => ({ ...prev, tools: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <label className="space-y-1 text-sm text-slate-200">
          Provider
          <select
            value={form.provider}
            onChange={(e) => {
              const nextProvider = e.target.value;
              const nextModel = MODEL_OPTIONS[nextProvider]?.[0]?.value || "";
              setForm((prev) => ({ ...prev, provider: nextProvider, modelId: nextModel || prev.modelId }));
            }}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          >
            {PROVIDER_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Model
          {modelOptions.length > 0 ? (
            <select
              value={form.modelId}
              onChange={(e) => setForm((prev) => ({ ...prev, modelId: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            >
              {modelOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={form.modelId}
              onChange={(e) => setForm((prev) => ({ ...prev, modelId: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
              placeholder="Model ID"
            />
          )}
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Temperature
          <input
            value={form.temperature}
            onChange={(e) => setForm((prev) => ({ ...prev, temperature: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          />
        </label>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-slate-200">
          Max tokens
          <input
            value={form.maxTokens}
            onChange={(e) => setForm((prev) => ({ ...prev, maxTokens: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          />
        </label>
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Create agent
        </button>
      </div>
    </form>
  );
}

function CreateTaskForm({ onSubmit, submitting }: { onSubmit: (payload: CreateTaskRequest) => void; submitting: boolean }) {
  const [form, setForm] = useState({
    name: "",
    description: "",
    requiredCapabilities: "",
    priority: "1",
    webhook: "",
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload: CreateTaskRequest = {
      name: form.name,
      description: form.description,
      required_capabilities: form.requiredCapabilities
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      priority: Number(form.priority) || 1,
      webhook_url: form.webhook || undefined,
    };
    onSubmit(payload);
  };

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-slate-200">
          Name
          <input
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            placeholder="Summarize research"
          />
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Priority (0-3)
          <input
            value={form.priority}
            onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value }))}
            min={0}
            max={3}
            type="number"
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          />
        </label>
      </div>

      <label className="space-y-1 text-sm text-slate-200">
        Description
        <textarea
          value={form.description}
          onChange={(e) => setForm((prev) => ({ ...prev, description: e.target.value }))}
          required
          className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
          rows={3}
        />
      </label>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <label className="space-y-1 text-sm text-slate-200">
          Required capabilities
          <input
            value={form.requiredCapabilities}
            onChange={(e) => setForm((prev) => ({ ...prev, requiredCapabilities: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            placeholder="analysis, python"
          />
        </label>
        <label className="space-y-1 text-sm text-slate-200">
          Webhook (optional)
          <input
            value={form.webhook}
            onChange={(e) => setForm((prev) => ({ ...prev, webhook: e.target.value }))}
            className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
            placeholder="https://..."
          />
        </label>
      </div>

      <div className="flex items-center justify-end gap-3 pt-2">
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Create task
        </button>
      </div>
    </form>
  );
}

function formatDate(value: string | undefined | null) {
  if (!value) return "—";
  return new Date(value).toLocaleString();
}

function App() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionAgentId, setActionAgentId] = useState<string | null>(null);
  const [actionTaskId, setActionTaskId] = useState<string | null>(null);
  const [banner, setBanner] = useState<Banner | null>(null);
  const [agentModalOpen, setAgentModalOpen] = useState(false);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sessions, setSessions] = useState<ConversationSession[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [creatingSession, setCreatingSession] = useState(false);
  const [subagentSubmitting, setSubagentSubmitting] = useState(false);
  const [subagentForm, setSubagentForm] = useState({
    name: "",
    role: "",
    goal: "Assist the current conversation and delegate tasks when needed.",
  });

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [agentData, taskData] = await Promise.all([AgentService.list(), TaskService.list()]);
      setAgents(agentData);
      setTasks(taskData);

      let nextSelected = selectedAgentId;
      if (agentData.length > 0 && (!nextSelected || !agentData.find((agent) => agent.agent_id === nextSelected))) {
        nextSelected = agentData[0].agent_id;
      }
      setSelectedAgentId(nextSelected ?? null);
      setBanner(null);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to load data";
      setBanner({ type: "error", text: message });
    } finally {
      setLoading(false);
    }
  }, [selectedAgentId]);

  const loadSessions = useCallback(
    async (agentFilter?: string) => {
      try {
        const sessionList = await ConversationService.list(agentFilter);
        setSessions(sessionList);

        if (sessionList.length === 0) {
          setSelectedSessionId(null);
          setMessages([]);
          return sessionList;
        }

        const exists = selectedSessionId && sessionList.find((s) => s.session_id === selectedSessionId);
        setSelectedSessionId(exists ? selectedSessionId : sessionList[0].session_id);
        return sessionList;
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to load sessions";
        setBanner({ type: "error", text: message });
        return [];
      }
    },
    [selectedSessionId],
  );

  const loadHistory = useCallback(
    async (sessionId: string) => {
      setChatLoading(true);
      try {
        const history = await ConversationService.history(sessionId);
        setMessages(history);
      } catch (error) {
        setBanner({ type: "error", text: error instanceof Error ? error.message : "Failed to load messages" });
      } finally {
        setChatLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, 12000);
    return () => clearInterval(id);
  }, [loadData]);

  useEffect(() => {
    loadSessions(selectedAgentId ?? undefined);
  }, [selectedAgentId, loadSessions]);

  useEffect(() => {
    if (selectedSessionId) {
      loadHistory(selectedSessionId);
    } else {
      setMessages([]);
    }
  }, [selectedSessionId, loadHistory]);

  const stats = useMemo(() => {
    const runningAgents = agents.filter((agent) => agent.status.toLowerCase() === "running").length;
    const pendingTasks = tasks.filter((task) => task.status.toLowerCase() === "pending").length;
    const activeTasks = tasks.filter((task) => task.status.toLowerCase() === "running").length;
    const completedTasks = tasks.filter((task) => task.status.toLowerCase() === "completed").length;
    return { runningAgents, pendingTasks, activeTasks, completedTasks };
  }, [agents, tasks]);

  const selectedAgent = useMemo(() => agents.find((agent) => agent.agent_id === selectedAgentId), [agents, selectedAgentId]);

  const handleStartAgent = async (id: string) => {
    setActionAgentId(id);
    try {
      await AgentService.start(id);
      await loadData();
      setBanner({ type: "success", text: "Agent started" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to start agent" });
    } finally {
      setActionAgentId(null);
    }
  };

  const handleStopAgent = async (id: string) => {
    setActionAgentId(id);
    try {
      await AgentService.stop(id);
      await loadData();
      setBanner({ type: "success", text: "Agent stopped" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to stop agent" });
    } finally {
      setActionAgentId(null);
    }
  };

  const handleCancelTask = async (id: string) => {
    setActionTaskId(id);
    try {
      await TaskService.cancel(id);
      await loadData();
      setBanner({ type: "success", text: "Task cancelled" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to cancel task" });
    } finally {
      setActionTaskId(null);
    }
  };

  const handleCreateAgent = async (payload: CreateAgentRequest) => {
    setSubmitting(true);
    try {
      await AgentService.create(payload);
      await loadData();
      setAgentModalOpen(false);
      setBanner({ type: "success", text: "Agent created" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to create agent" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateTask = async (payload: CreateTaskRequest) => {
    setSubmitting(true);
    try {
      await TaskService.create(payload);
      await loadData();
      setTaskModalOpen(false);
      setBanner({ type: "success", text: "Task created" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to create task" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateSession = async () => {
    if (!selectedAgentId) {
      setBanner({ type: "error", text: "Select an agent to start a session" });
      return;
    }
    setCreatingSession(true);
    try {
      const agentName = agents.find((a) => a.agent_id === selectedAgentId)?.name ?? "agent";
      const session = await ConversationService.create({
        agent_id: selectedAgentId,
        title: `Chat with ${agentName}`,
      });
      await loadSessions(selectedAgentId);
      setSelectedSessionId(session.session_id);
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
    setChatLoading(true);
    try {
      await ConversationService.sendMessage(selectedSessionId, { content });
      await loadHistory(selectedSessionId);
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Failed to send message" });
    } finally {
      setChatLoading(false);
    }
  };

  const handleCreateSubagent = async () => {
    if (!selectedAgentId) {
      setBanner({ type: "error", text: "Select a primary agent first" });
      return;
    }
    setSubagentSubmitting(true);
    try {
      const name = subagentForm.name || `Subagent ${agents.length + 1}`;
      const role = subagentForm.role || "Specialist";
      await AgentService.create({
        name,
        role,
        goal: subagentForm.goal || "Assist primary agent",
        capabilities: ["assistant"],
      });
      await loadData();
      setSubagentForm((prev) => ({ ...prev, name: "", role: "" }));
      setBanner({ type: "success", text: "Subagent created" });
    } catch (error) {
      setBanner({ type: "error", text: error instanceof Error ? error.message : "Unable to create subagent" });
    } finally {
      setSubagentSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-900/80 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div>
            <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Agent Orchestrator</p>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-semibold text-white">Control Plane</h1>
              <span className="rounded-full border border-slate-800 bg-slate-900 px-3 py-1 text-xs text-slate-400">
                {apiConfig.baseUrl}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => loadData()}
              className="flex items-center gap-2 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:border-slate-500"
              type="button"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
              Refresh
            </button>
            <button
              onClick={() => setTaskModalOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-blue-600/70 bg-blue-600/15 px-4 py-2 text-sm font-semibold text-blue-50 hover:border-blue-500"
              type="button"
            >
              <Plus className="h-4 w-4" /> New task
            </button>
            <button
              onClick={() => setAgentModalOpen(true)}
              className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/15 px-4 py-2 text-sm font-semibold text-emerald-50 hover:border-emerald-500"
              type="button"
            >
              <Plus className="h-4 w-4" /> New agent
            </button>
          </div>
        </div>
        {banner && (
          <div
            className={cn(
              "mx-auto mt-2 flex max-w-7xl items-center gap-3 px-6 pb-3 text-sm",
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

      <main className="mx-auto max-w-7xl px-6 py-6 space-y-6">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Agents" value={agents.length} icon={Users} tone="violet" hint="Registered" />
          <StatCard label="Running" value={stats.runningAgents} icon={Zap} tone="emerald" hint="Live capacity" />
          <StatCard label="Pending tasks" value={stats.pendingTasks} icon={Clock3} tone="amber" />
          <StatCard label="Completed tasks" value={stats.completedTasks} icon={CheckCircle2} tone="blue" hint="Recently finished" />
        </div>

        {loading && (
          <div className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-900/60 px-4 py-3 text-sm text-slate-300">
            <Loader2 className="h-4 w-4 animate-spin" /> Syncing orchestrator state...
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Agents</p>
                <h2 className="text-lg font-semibold text-slate-50">Execution layer</h2>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <ShieldHalf className="h-4 w-4" />
                Auto-refreshes every 12s
              </div>
            </div>
            <AgentTable
              agents={agents}
              selectedId={selectedAgentId}
              onSelect={setSelectedAgentId}
              onStart={handleStartAgent}
              onStop={handleStopAgent}
              busyId={actionAgentId}
            />
          </div>
          <AgentDetail agent={selectedAgent} tasks={tasks} />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Tasks</p>
                <h2 className="text-lg font-semibold text-slate-50">Workflow queue</h2>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Clock3 className="h-4 w-4" />
                {tasks.length} total
              </div>
            </div>
            <TaskList tasks={tasks} agents={agents} onCancel={handleCancelTask} busyId={actionTaskId} />
          </div>
          <ActivityTimeline tasks={tasks} />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Conversations</p>
                <h2 className="text-lg font-semibold text-slate-50">Chat with agents</h2>
                <p className="text-xs text-slate-500">Filtering by selected agent.</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => loadSessions(selectedAgentId ?? undefined)}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-slate-500"
                  type="button"
                >
                  <RefreshCw className={cn("h-4 w-4", chatLoading && "animate-spin")} />
                </button>
                <button
                  onClick={handleCreateSession}
                  disabled={creatingSession}
                  className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/10 px-3 py-2 text-xs font-semibold text-emerald-50 hover:border-emerald-500 disabled:opacity-60"
                  type="button"
                >
                  {creatingSession ? <Loader2 className="h-4 w-4 animate-spin" /> : <MessageCircle className="h-4 w-4" />}
                  New session
                </button>
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-900/70">
              <div className="border-b border-slate-800 px-4 py-3 text-xs uppercase tracking-wide text-slate-500">Sessions</div>
              <div className="max-h-72 divide-y divide-slate-800/80 overflow-y-auto">
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

            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Subagent</p>
                  <h3 className="text-sm font-semibold text-slate-50">Spawn specialist</h3>
                </div>
              </div>
              <div className="mt-3 space-y-2">
                <input
                  value={subagentForm.name}
                  onChange={(e) => setSubagentForm((prev) => ({ ...prev, name: e.target.value }))}
                  placeholder="Name (optional)"
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
                />
                <input
                  value={subagentForm.role}
                  onChange={(e) => setSubagentForm((prev) => ({ ...prev, role: e.target.value }))}
                  placeholder="Role (optional)"
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
                />
                <textarea
                  value={subagentForm.goal}
                  onChange={(e) => setSubagentForm((prev) => ({ ...prev, goal: e.target.value }))}
                  className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-emerald-500"
                  rows={2}
                />
                <button
                  onClick={handleCreateSubagent}
                  disabled={subagentSubmitting}
                  className="flex w-full items-center justify-center gap-2 rounded-lg border border-blue-600/70 bg-blue-600/10 px-3 py-2 text-sm font-semibold text-blue-50 hover:border-blue-500 disabled:opacity-60"
                  type="button"
                >
                  {subagentSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  Create subagent
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-2 space-y-3">
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="mb-3 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Conversation</p>
                  <h3 className="text-lg font-semibold text-slate-50">
                    {selectedSessionId ? "Live chat" : "Select or create a session"}
                  </h3>
                </div>
                {selectedSessionId && <StatusBadge status={sessions.find((s) => s.session_id === selectedSessionId)?.status || "active"} />}
              </div>

              <div className="mb-3 h-96 space-y-3 overflow-y-auto rounded-lg border border-slate-800 bg-slate-950/60 p-3">
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
                        <p className="mt-1 text-sm text-slate-100 whitespace-pre-wrap">{msg.content}</p>
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
                  disabled={!selectedSessionId || chatLoading}
                  className="flex items-center gap-2 rounded-lg border border-emerald-600/70 bg-emerald-600/10 px-3 py-2 text-sm font-semibold text-emerald-50 hover:border-emerald-500 disabled:opacity-60"
                  type="button"
                >
                  {chatLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      <Modal open={agentModalOpen} title="Register a new agent" onClose={() => setAgentModalOpen(false)}>
        <CreateAgentForm onSubmit={handleCreateAgent} submitting={submitting} />
      </Modal>

      <Modal open={taskModalOpen} title="Create a task" onClose={() => setTaskModalOpen(false)}>
        <CreateTaskForm onSubmit={handleCreateTask} submitting={submitting} />
      </Modal>
    </div>
  );
}

export default App;
