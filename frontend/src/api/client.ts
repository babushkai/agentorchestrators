import type {
  Agent,
  AgentCreate,
  Task,
  TaskCreate,
  Session,
  SessionCreate,
  Message,
  Workflow,
  HealthStatus,
  FileMetadata,
  FileListResponse,
} from '@/types/api'

const API_BASE = '/api/v1'

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Health
export async function getHealth(): Promise<HealthStatus> {
  const response = await fetch('/health')
  return response.json()
}

// Helper for paginated responses
interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// Agents
export async function getAgents(): Promise<Agent[]> {
  const response = await fetchApi<PaginatedResponse<Agent>>('/agents')
  return response.items
}

export async function getAgent(agentId: string): Promise<Agent> {
  return fetchApi<Agent>(`/agents/${agentId}`)
}

export async function createAgent(data: AgentCreate): Promise<Agent> {
  return fetchApi<Agent>('/agents', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function deleteAgent(agentId: string): Promise<void> {
  await fetchApi<void>(`/agents/${agentId}`, { method: 'DELETE' })
}

// Tasks
export async function getTasks(): Promise<Task[]> {
  const response = await fetchApi<PaginatedResponse<Task>>('/tasks')
  return response.items
}

export async function getTask(taskId: string): Promise<Task> {
  return fetchApi<Task>(`/tasks/${taskId}`)
}

export async function createTask(data: TaskCreate): Promise<Task> {
  return fetchApi<Task>('/tasks', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// Sessions
export async function getSessions(): Promise<Session[]> {
  return fetchApi<Session[]>('/sessions')
}

export async function getSession(sessionId: string): Promise<Session> {
  return fetchApi<Session>(`/sessions/${sessionId}`)
}

export async function createSession(data: SessionCreate): Promise<Session> {
  return fetchApi<Session>('/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getSessionHistory(
  sessionId: string,
  limit = 50
): Promise<{ messages: Message[]; total_count: number }> {
  return fetchApi(`/sessions/${sessionId}/history?limit=${limit}`)
}

export async function sendMessage(
  sessionId: string,
  content: string
): Promise<Message> {
  return fetchApi<Message>(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

// Workflows
export async function getWorkflows(): Promise<Workflow[]> {
  const response = await fetchApi<PaginatedResponse<Workflow>>('/workflows')
  return response.items
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  return fetchApi<Workflow>(`/workflows/${workflowId}`)
}

// Files
export async function getTaskFiles(taskId: string): Promise<FileListResponse> {
  return fetchApi<FileListResponse>(`/tasks/${taskId}/files`)
}

export async function getSessionFiles(sessionId: string): Promise<FileListResponse> {
  return fetchApi<FileListResponse>(`/sessions/${sessionId}/files`)
}

export async function getFile(fileId: string): Promise<FileMetadata> {
  return fetchApi<FileMetadata>(`/files/${fileId}`)
}

export async function uploadTaskFile(taskId: string, file: File): Promise<FileMetadata> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_BASE}/tasks/${taskId}/files`, {
    method: 'POST',
    body: formData,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  
  return response.json()
}

export async function uploadSessionFile(sessionId: string, file: File): Promise<FileMetadata> {
  const formData = new FormData()
  formData.append('file', file)
  
  const response = await fetch(`${API_BASE}/sessions/${sessionId}/files`, {
    method: 'POST',
    body: formData,
  })
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }
  
  return response.json()
}

export async function deleteFile(fileId: string): Promise<void> {
  await fetchApi<void>(`/files/${fileId}`, { method: 'DELETE' })
}

export function getFileDownloadUrl(fileId: string): string {
  return `${API_BASE}/files/${fileId}/download`
}
