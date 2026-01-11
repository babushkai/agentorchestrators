import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn, formatRelativeTime, truncateId } from "@/lib/utils"
import {
  ListTodo,
  Plus,
  Search,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
  X,
} from "lucide-react"
import type { Agent, Task, TaskCreate } from "@/types/api"
import * as api from "@/api/client"

interface TasksProps {
  tasks: Task[]
  agents: Agent[]
  onRefresh: () => void
  isLoading: boolean
}

type StatusFilter = "all" | "pending" | "running" | "completed" | "failed"

const getStatusBadge = (status: Task["status"]) => {
  switch (status) {
    case "completed":
      return <Badge variant="idle">completed</Badge>
    case "running":
      return <Badge variant="running">running</Badge>
    case "pending":
      return <Badge variant="pending">pending</Badge>
    case "failed":
      return <Badge variant="error">failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

const getPriorityBadge = (priority: number) => {
  switch (priority) {
    case 3:
      return <Badge variant="error">critical</Badge>
    case 2:
      return <Badge variant="pending">high</Badge>
    case 1:
      return <Badge variant="secondary">normal</Badge>
    default:
      return <Badge variant="outline">low</Badge>
  }
}

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: TaskCreate) => void
  isSubmitting: boolean
  agents: Agent[]
}

function CreateTaskModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  agents,
}: CreateTaskModalProps) {
  const [formData, setFormData] = useState<TaskCreate>({
    name: "",
    description: "",
    priority: 1,
    agent_id: "",
  })

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit({
      ...formData,
      agent_id: formData.agent_id || undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-md mx-4 animate-slide-in-right">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle>New Task</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Name</label>
              <Input
                placeholder="e.g., Analyze sales data"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Description</label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-border bg-input px-3 py-2 text-sm transition-colors duration-150 placeholder:text-muted-foreground hover:border-border-hover focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                placeholder="Describe what this task should accomplish..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Priority</label>
                <select
                  className="flex h-9 w-full rounded-md border border-border bg-input px-3 py-1 text-sm transition-colors duration-150 hover:border-border-hover focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                  value={formData.priority}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      priority: Number(e.target.value),
                    })
                  }
                >
                  <option value={0}>Low</option>
                  <option value={1}>Normal</option>
                  <option value={2}>High</option>
                  <option value={3}>Critical</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="text-xs text-muted-foreground">Assign to Agent</label>
                <select
                  className="flex h-9 w-full rounded-md border border-border bg-input px-3 py-1 text-sm transition-colors duration-150 hover:border-border-hover focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                  value={formData.agent_id}
                  onChange={(e) =>
                    setFormData({ ...formData, agent_id: e.target.value })
                  }
                >
                  <option value="">Auto-assign</option>
                  {agents.map((agent) => (
                    <option key={agent.agent_id} value={agent.agent_id}>
                      {agent.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating..." : "Create Task"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

interface TaskDetailModalProps {
  task: Task | null
  onClose: () => void
}

function TaskDetailModal({ task, onClose }: TaskDetailModalProps) {
  if (!task) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-lg mx-4 max-h-[80vh] overflow-auto animate-slide-in-right">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div>
            <CardTitle>{task.name}</CardTitle>
            <p className="text-xs text-muted-foreground mt-1 font-mono">
              {task.task_id}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex gap-2">
            {getStatusBadge(task.status)}
            {getPriorityBadge(task.priority)}
          </div>

          <div>
            <h4 className="text-xs text-muted-foreground mb-1">Description</h4>
            <p className="text-sm">{task.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="text-xs text-muted-foreground mb-1">Created</h4>
              <p>{formatRelativeTime(task.created_at)}</p>
            </div>
            {task.started_at && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Started</h4>
                <p>{formatRelativeTime(task.started_at)}</p>
              </div>
            )}
            {task.completed_at && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Completed</h4>
                <p>{formatRelativeTime(task.completed_at)}</p>
              </div>
            )}
            {task.agent_id && (
              <div>
                <h4 className="text-xs text-muted-foreground mb-1">Agent</h4>
                <p className="font-mono">{truncateId(task.agent_id)}</p>
              </div>
            )}
          </div>

          {task.result && (
            <div>
              <h4 className="text-xs text-muted-foreground mb-1">Result</h4>
              <pre className="text-sm bg-secondary p-3 rounded-md overflow-auto max-h-48 whitespace-pre-wrap font-mono text-xs">
                {task.result}
              </pre>
            </div>
          )}

          {task.error && (
            <div>
              <h4 className="text-xs text-destructive mb-1">Error</h4>
              <pre className="text-sm bg-destructive/10 text-destructive p-3 rounded-md overflow-auto max-h-48 whitespace-pre-wrap font-mono text-xs">
                {task.error}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export function Tasks({ tasks, agents, onRefresh: _onRefresh, isLoading: _isLoading }: TasksProps) {
  void _onRefresh
  void _isLoading
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: api.createTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setShowCreateModal(false)
    },
  })

  // Filter tasks
  const filteredTasks = tasks.filter((task) => {
    const matchesSearch =
      task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      task.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus =
      statusFilter === "all" || task.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const statusCounts = {
    all: tasks.length,
    pending: tasks.filter((t) => t.status === "pending").length,
    running: tasks.filter((t) => t.status === "running").length,
    completed: tasks.filter((t) => t.status === "completed").length,
    failed: tasks.filter((t) => t.status === "failed").length,
  }

  const statusIcons = {
    all: null,
    pending: Clock,
    running: Loader2,
    completed: CheckCircle2,
    failed: XCircle,
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium">Tasks</h1>
          <p className="text-sm text-muted-foreground">
            {tasks.length} task{tasks.length !== 1 ? "s" : ""} total
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} size="sm">
          <Plus className="h-4 w-4" />
          New Task
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search tasks..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex gap-1">
          {(["all", "pending", "running", "completed", "failed"] as const).map((status) => {
            const Icon = statusIcons[status]
            return (
              <Button
                key={status}
                variant={statusFilter === status ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setStatusFilter(status)}
                className="capitalize"
              >
                {Icon && <Icon className={cn("h-3 w-3", status === "running" && statusFilter === status && "animate-spin")} />}
                {status}
                <span className="ml-1 text-muted-foreground">({statusCounts[status]})</span>
              </Button>
            )
          })}
        </div>
      </div>

      {/* Tasks List */}
      {filteredTasks.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <ListTodo className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground mb-4">
              {tasks.length === 0 ? "No tasks yet" : "No matching tasks"}
            </p>
            {tasks.length === 0 && (
              <Button onClick={() => setShowCreateModal(true)} size="sm">
                <Plus className="h-4 w-4" />
                Create Task
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {filteredTasks.map((task) => (
            <Card
              key={task.task_id}
              className="hover:bg-secondary/30 transition-colors duration-150 cursor-pointer"
              onClick={() => setSelectedTask(task)}
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-md bg-secondary">
                    <ListTodo className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{task.name}</span>
                      {getStatusBadge(task.status)}
                      {getPriorityBadge(task.priority)}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground truncate max-w-[300px]">
                        {task.description}
                      </span>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {truncateId(task.task_id)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(task.created_at)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Modals */}
      <CreateTaskModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isSubmitting={createMutation.isPending}
        agents={agents}
      />

      <TaskDetailModal
        task={selectedTask}
        onClose={() => setSelectedTask(null)}
      />
    </div>
  )
}
