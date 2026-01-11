import { createSignal } from 'solid-js'
import type { Agent, Task, Workflow, Conversation, LogEntry, DashboardStats } from '@/types'

// Connection state
const [isConnected, setIsConnected] = createSignal(false)
const [isLoading, setIsLoading] = createSignal(false)

// Dashboard stats
const [stats, setStats] = createSignal<DashboardStats>({
  totalAgents: 0,
  activeAgents: 0,
  totalTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
  totalWorkflows: 0,
  activeWorkflows: 0,
  totalConversations: 0,
})

// Agents
const [agents, setAgents] = createSignal<Agent[]>([])
const [selectedAgent, setSelectedAgent] = createSignal<Agent | null>(null)

// Tasks
const [tasks, setTasks] = createSignal<Task[]>([])
const [selectedTask, setSelectedTask] = createSignal<Task | null>(null)

// Workflows
const [workflows, setWorkflows] = createSignal<Workflow[]>([])
const [selectedWorkflow, setSelectedWorkflow] = createSignal<Workflow | null>(null)

// Conversations
const [conversations, setConversations] = createSignal<Conversation[]>([])
const [selectedConversation, setSelectedConversation] = createSignal<Conversation | null>(null)

// Logs
const [logs, setLogs] = createSignal<LogEntry[]>([])

// Command palette
const [isCommandPaletteOpen, setIsCommandPaletteOpen] = createSignal(false)

// Health check
async function checkHealth() {
  try {
    const res = await fetch('/health')
    const data = await res.json()
    setIsConnected(data.status === 'healthy')
    return data.status === 'healthy'
  } catch {
    setIsConnected(false)
    return false
  }
}

// Fetch dashboard stats
async function fetchStats() {
  try {
    const res = await fetch('/api/stats')
    if (res.ok) {
      const data = await res.json()
      setStats(data)
    }
  } catch (e) {
    console.error('Failed to fetch stats:', e)
  }
}

// Fetch agents
async function fetchAgents() {
  setIsLoading(true)
  try {
    const res = await fetch('/api/agents')
    if (res.ok) {
      const data = await res.json()
      setAgents(data)
    }
  } catch (e) {
    console.error('Failed to fetch agents:', e)
  } finally {
    setIsLoading(false)
  }
}

// Fetch tasks
async function fetchTasks() {
  setIsLoading(true)
  try {
    const res = await fetch('/api/tasks')
    if (res.ok) {
      const data = await res.json()
      setTasks(data)
    }
  } catch (e) {
    console.error('Failed to fetch tasks:', e)
  } finally {
    setIsLoading(false)
  }
}

// Fetch workflows
async function fetchWorkflows() {
  setIsLoading(true)
  try {
    const res = await fetch('/api/workflows')
    if (res.ok) {
      const data = await res.json()
      setWorkflows(data)
    }
  } catch (e) {
    console.error('Failed to fetch workflows:', e)
  } finally {
    setIsLoading(false)
  }
}

// Fetch conversations
async function fetchConversations() {
  setIsLoading(true)
  try {
    const res = await fetch('/api/conversations')
    if (res.ok) {
      const data = await res.json()
      setConversations(data)
    }
  } catch (e) {
    console.error('Failed to fetch conversations:', e)
  } finally {
    setIsLoading(false)
  }
}

// Fetch logs
async function fetchLogs() {
  try {
    const res = await fetch('/api/logs')
    if (res.ok) {
      const data = await res.json()
      setLogs(data)
    }
  } catch (e) {
    console.error('Failed to fetch logs:', e)
  }
}

export const appStore = {
  // State
  isConnected,
  isLoading,
  stats,
  agents,
  selectedAgent,
  tasks,
  selectedTask,
  workflows,
  selectedWorkflow,
  conversations,
  selectedConversation,
  logs,
  isCommandPaletteOpen,
  
  // Setters
  setIsConnected,
  setSelectedAgent,
  setSelectedTask,
  setSelectedWorkflow,
  setSelectedConversation,
  setIsCommandPaletteOpen,
  
  // Actions
  checkHealth,
  fetchStats,
  fetchAgents,
  fetchTasks,
  fetchWorkflows,
  fetchConversations,
  fetchLogs,
}
