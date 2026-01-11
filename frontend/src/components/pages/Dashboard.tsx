import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import { formatRelativeTime, truncateId } from "@/lib/utils"
import {
  ListTodo,
  Bot,
  GitBranch,
  MessageSquare,
  RefreshCw,
  Server,
  Database,
  Radio,
  HardDrive,
} from "lucide-react"
import type { Task, HealthStatus } from "@/types/api"

interface ServiceStatus {
  name: string
  icon: React.ElementType
  status: 'online' | 'offline' | 'unknown'
}

interface DashboardProps {
  stats: {
    tasks: number
    agents: number
    workflows: number
    sessions: number
  }
  recentTasks: Task[]
  health: HealthStatus | null
  onRefresh: () => void
  isLoading: boolean
}

const services: ServiceStatus[] = [
  { name: "API Server", icon: Server, status: "online" },
  { name: "NATS", icon: Radio, status: "online" },
  { name: "Redis", icon: Database, status: "online" },
  { name: "PostgreSQL", icon: HardDrive, status: "online" },
]

const statCards = [
  { key: "tasks", label: "Total Tasks", icon: ListTodo },
  { key: "agents", label: "Active Agents", icon: Bot },
  { key: "workflows", label: "Workflows", icon: GitBranch },
  { key: "sessions", label: "Conversations", icon: MessageSquare },
] as const

const getStatusBadge = (status: string) => {
  switch (status) {
    case "completed":
      return <Badge variant="success">Completed</Badge>
    case "running":
      return <Badge variant="info">Running</Badge>
    case "pending":
      return <Badge variant="warning">Pending</Badge>
    case "failed":
      return <Badge variant="destructive">Failed</Badge>
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
    default:
      return <Badge variant="secondary">Normal</Badge>
  }
}

export function Dashboard({
  stats,
  recentTasks,
  health: _health,
  onRefresh,
  isLoading,
}: DashboardProps) {
  // TODO: Use health data to dynamically update service status
  void _health
  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ key, label, icon: Icon }) => (
          <Card key={key}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                {label}
              </CardTitle>
              <Icon className="h-5 w-5 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold">{stats[key]}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Services Status */}
      <Card>
        <CardHeader>
          <CardTitle>Services Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {services.map((service) => {
              const Icon = service.icon
              return (
                <div
                  key={service.name}
                  className="flex items-center gap-3 p-3 bg-secondary rounded-lg"
                >
                  <div
                    className={cn(
                      "w-2.5 h-2.5 rounded-full",
                      service.status === "online" && "bg-success",
                      service.status === "offline" && "bg-destructive",
                      service.status === "unknown" && "bg-muted-foreground"
                    )}
                  />
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-medium">{service.name}</span>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Recent Tasks */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Recent Tasks</CardTitle>
          <Button variant="ghost" size="sm">
            View All
          </Button>
        </CardHeader>
        <CardContent>
          {recentTasks.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <ListTodo className="h-12 w-12 mx-auto mb-3 opacity-50" />
              <p>No tasks yet</p>
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
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {recentTasks.slice(0, 5).map((task) => (
                    <tr
                      key={task.task_id}
                      className="border-b border-border/50 hover:bg-accent/50 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div>
                          <p className="font-medium">{task.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {truncateId(task.task_id)}
                          </p>
                        </div>
                      </td>
                      <td className="py-3 px-4">{getStatusBadge(task.status)}</td>
                      <td className="py-3 px-4">{getPriorityBadge(task.priority)}</td>
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
    </div>
  )
}
