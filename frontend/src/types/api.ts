// API Types

export interface Agent {
  agent_id: string
  name: string
  role: string
  status: 'idle' | 'running' | 'error'
  capabilities: string[]
  created_at: string
  last_heartbeat: string | null
  current_task_id: string | null
}

export interface AgentCreate {
  name: string
  role: string
  goal: string
  backstory?: string
  llm_config?: {
    provider: string
    model_id: string
    temperature?: number
    max_tokens?: number
  }
  tools?: string[]
}

export interface Task {
  task_id: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  priority: number
  agent_id?: string
  created_at: string
  started_at?: string
  completed_at?: string
  result?: string
  error?: string
}

export interface TaskCreate {
  name: string
  description: string
  priority?: number
  agent_id?: string
  attachments?: string[]
}

export interface Session {
  session_id: string
  agent_id: string
  tenant_id: string
  status: 'active' | 'closed'
  title: string | null
  created_at: string
  last_activity_at: string
  message_count: number
}

export interface SessionCreate {
  name: string
  agent_id: string
}

export interface Message {
  message_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: string
  tool_calls?: ToolCall[] | null
}

export interface ToolCall {
  id: string
  type: string
  function: {
    name: string
    arguments: string
  }
}

export interface Workflow {
  workflow_id: string
  name: string
  description: string
  status: 'draft' | 'active' | 'completed' | 'failed'
  steps: WorkflowStep[]
  created_at: string
}

export interface WorkflowStep {
  step_id: string
  name: string
  agent_id: string
  order: number
}

export interface HealthStatus {
  status: string
  timestamp: string
  version: string
  environment: string
  checks: Record<string, boolean>
}

export interface FileMetadata {
  file_id: string
  task_id: string | null
  session_id: string | null
  filename: string
  original_filename: string
  content_type: string
  size_bytes: number
  storage_path: string
  checksum: string
  parse_status: string
  parsed_content: string | null
  created_at: string
}

export interface FileListResponse {
  files: FileMetadata[]
  count: number
}
