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
  RefreshCw,
  Search,
  Filter,
  ChevronDown,
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
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Completed
        </Badge>
      )
    case "running":
      return (
        <Badge variant="info" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      )
    case "pending":
      return (
        <Badge variant="warning" className="gap-1">
          <Clock className="h-3 w-3" />
          Pending
        </Badge>
      )
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Failed
        </Badge>
      )
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

const getPriorityBadge = (priority: number) => {
  switch (priority) {
    case 3:
      return <Badge variant="destructive">Critical</Badge>
    case 2:
      return <Badge variant="warning">High</Badge>
    case 1:
      return <Badge variant="secondary">Normal</Badge>
    default:
      return <Badge variant="outline">Low</Badge>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-lg mx-4">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Create New Task</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Task Name</label>
              <Input
                placeholder="e.g., Analyze sales data"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Description</label>
              <textarea
                className="flex min-h-[100px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                placeholder="Describe what this task should accomplish..."
                value={formData.description}
                onChange={(e) =>
                  setFormData({ ...formData, description: e.target.value })
                }
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Priority</label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
              <div className="space-y-2">
                <label className="text-sm font-medium">Assign to Agent</label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
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
            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4" />
                    Create Task
                  </>
                )}
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-2xl mx-4 max-h-[80vh] overflow-auto">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{task.name}</CardTitle>
            <p className="text-xs text-muted-foreground mt-1">
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
            <h4 className="text-sm font-medium text-muted-foreground mb-1">
              Description
            </h4>
            <p className="text-sm">{task.description}</p>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <h4 className="font-medium text-muted-foreground mb-1">
                Created
              </h4>
              <p>{formatRelativeTime(task.created_at)}</p>
            </div>
            {task.started_at && (
              <div>
                <h4 className="font-medium text-muted-foreground mb-1">
                  Started
                </h4>
                <p>{formatRelativeTime(task.started_at)}</p>
              </div>
            )}
            {task.completed_at && (
              <div>
                <h4 className="font-medium text-muted-foreground mb-1">
                  Completed
                </h4>
                <p>{formatRelativeTime(task.completed_at)}</p>
              </div>
            )}
            {task.agent_id && (
              <div>
                <h4 className="font-medium text-muted-foreground mb-1">
                  Agent
                </h4>
                <p>{truncateId(task.agent_id)}</p>
              </div>
            )}
          </div>

          {task.result && (
            <div>
              <h4 className="text-sm font-medium text-muted-foreground mb-1">
                Result
              </h4>
              <pre className="text-sm bg-secondary p-3 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap">
                {task.result}
              </pre>
            </div>
          )}

          {task.error && (
            <div>
              <h4 className="text-sm font-medium text-destructive mb-1">
                Error
              </h4>
              <pre className="text-sm bg-destructive/10 text-destructive p-3 rounded-lg overflow-auto max-h-48 whitespace-pre-wrap">
                {task.error}
              </pre>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export function Tasks({ tasks, agents, onRefresh, isLoading }: TasksProps) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [searchQuery, setSearchQuery] = useState("")
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all")
  const [showFilterMenu, setShowFilterMenu] = useState(false)
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Tasks</h2>
          <p className="text-sm text-muted-foreground">
            View and manage task execution
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4" />
            New Task
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search tasks..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
            <div className="relative">
              <Button
                variant="outline"
                onClick={() => setShowFilterMenu(!showFilterMenu)}
                className="w-full sm:w-auto"
              >
                <Filter className="h-4 w-4" />
                {statusFilter === "all" ? "All Status" : statusFilter}
                <ChevronDown className="h-4 w-4 ml-1" />
              </Button>
              {showFilterMenu && (
                <div className="absolute right-0 top-full mt-1 z-10 w-48 rounded-md border bg-popover shadow-lg">
                  {(
                    ["all", "pending", "running", "completed", "failed"] as const
                  ).map((status) => (
                    <button
                      key={status}
                      className={cn(
                        "flex items-center justify-between w-full px-3 py-2 text-sm hover:bg-accent",
                        statusFilter === status && "bg-accent"
                      )}
                      onClick={() => {
                        setStatusFilter(status)
                        setShowFilterMenu(false)
                      }}
                    >
                      <span className="capitalize">{status}</span>
                      <Badge variant="secondary" className="text-xs">
                        {statusCounts[status]}
                      </Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Tasks Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              Tasks{" "}
              <span className="text-muted-foreground font-normal">
                ({filteredTasks.length})
              </span>
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredTasks.length === 0 ? (
            <div className="text-center py-12">
              <ListTodo className="h-16 w-16 mx-auto mb-4 text-muted-foreground/50" />
              <h3 className="text-lg font-medium mb-2">
                {tasks.length === 0 ? "No tasks yet" : "No matching tasks"}
              </h3>
              <p className="text-muted-foreground mb-4">
                {tasks.length === 0
                  ? "Create your first task to get started"
                  : "Try adjusting your search or filters"}
              </p>
              {tasks.length === 0 && (
                <Button onClick={() => setShowCreateModal(true)}>
                  <Plus className="h-4 w-4" />
                  Create Task
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Task
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Status
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Priority
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Agent
                    </th>
                    <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground uppercase">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTasks.map((task) => (
                    <tr
                      key={task.task_id}
                      className="border-b border-border/50 hover:bg-accent/50 transition-colors cursor-pointer"
                      onClick={() => setSelectedTask(task)}
                    >
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium">{task.name}</p>
                          <p className="text-xs text-muted-foreground line-clamp-1">
                            {task.description}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-4">{getStatusBadge(task.status)}</td>
                      <td className="py-3 px-4">{getPriorityBadge(task.priority)}</td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {task.agent_id ? truncateId(task.agent_id) : "-"}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {formatRelativeTime(task.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

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
