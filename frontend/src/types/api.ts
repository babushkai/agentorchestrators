export type AgentStatus = "idle" | "running" | "stopped" | "error" | "pending" | string;
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled" | "stopped" | string;

export interface Agent {
  agent_id: string;
  name: string;
  role: string;
  status: AgentStatus;
  capabilities: string[];
  created_at: string;
  last_heartbeat?: string | null;
  current_task_id?: string | null;
}

export interface CreateAgentRequest {
  name: string;
  role: string;
  goal: string;
  backstory?: string;
  llm_config?: {
    provider: string;
    model_id: string;
    temperature: number;
    max_tokens: number;
  };
  tools?: string[];
  capabilities?: string[];
  max_iterations?: number;
  timeout_seconds?: number;
}

export interface Task {
  task_id: string;
  name: string;
  status: TaskStatus;
  priority: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  assigned_agent_id?: string | null;
  result?: unknown;
  error?: string | null;
}

export interface CreateTaskRequest {
  name: string;
  description: string;
  input_data?: Record<string, unknown>;
  required_capabilities?: string[];
  priority?: number;
  timeout_seconds?: number;
  webhook_url?: string | null;
  idempotency_key?: string | null;
}

export interface ConversationSession {
  session_id: string;
  agent_id: string;
  tenant_id?: string;
  status: string;
  title?: string | null;
  created_at: string;
  last_activity_at: string;
  message_count: number;
}

export interface ConversationMessage {
  message_id: string;
  role: "user" | "assistant" | string;
  content: string;
  timestamp: string;
  tool_calls?: Record<string, unknown>[] | null;
}
