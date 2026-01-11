// Agent Types
export type AgentStatus = 'idle' | 'running' | 'success' | 'error' | 'pending'

export interface Agent {
  id: string
  name: string
  description: string
  status: AgentStatus
  model: string
  createdAt: string
  lastRunAt?: string
  tasksCompleted: number
  tasksTotal: number
}

// Task Types
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
export type TaskPriority = 'low' | 'medium' | 'high' | 'critical'

export interface Task {
  id: string
  title: string
  description?: string
  status: TaskStatus
  priority: TaskPriority
  agentId?: string
  agentName?: string
  createdAt: string
  startedAt?: string
  completedAt?: string
  duration?: number
  output?: string
  error?: string
}

// Workflow Types
export interface WorkflowStep {
  id: string
  name: string
  agentId: string
  status: TaskStatus
  order: number
}

export interface Workflow {
  id: string
  name: string
  description?: string
  steps: WorkflowStep[]
  status: TaskStatus
  createdAt: string
  lastRunAt?: string
}

// Conversation Types
export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  role: MessageRole
  content: string
  timestamp: string
  agentId?: string
}

export interface Conversation {
  id: string
  title: string
  agentId: string
  agentName: string
  messages: Message[]
  createdAt: string
  updatedAt: string
}

// Monitoring Types
export interface LogEntry {
  id: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  timestamp: string
  source: string
  metadata?: Record<string, unknown>
}

export interface SystemMetrics {
  cpu: number
  memory: number
  activeAgents: number
  runningTasks: number
  queuedTasks: number
  uptime: number
}

// Dashboard Stats
export interface DashboardStats {
  totalAgents: number
  activeAgents: number
  totalTasks: number
  completedTasks: number
  failedTasks: number
  totalWorkflows: number
  activeWorkflows: number
  totalConversations: number
}
