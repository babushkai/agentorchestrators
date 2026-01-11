import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import { formatRelativeTime, truncateId } from "@/lib/utils"
import {
  Bot,
  ListTodo,
  GitBranch,
  MessageSquare,
  Activity,
  Clock,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react"
import type { Task, HealthStatus } from "@/types/api"

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

const getStatusIcon = (status: string) => {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-3 w-3 text-success" />
    case "running":
      return <Loader2 className="h-3 w-3 text-primary animate-spin" />
    case "pending":
      return <Clock className="h-3 w-3 text-warning" />
    case "failed":
      return <XCircle className="h-3 w-3 text-destructive" />
    default:
      return <Activity className="h-3 w-3 text-muted-foreground" />
  }
}

export function Dashboard({
  stats,
  recentTasks,
  health: _health,
  onRefresh: _onRefresh,
  isLoading: _isLoading,
}: DashboardProps) {
  void _health
  void _onRefresh
  void _isLoading

  const metrics = [
    { label: "Total Agents", value: stats.agents, icon: Bot, change: null },
    { label: "Total Tasks", value: stats.tasks, icon: ListTodo, change: null },
    { label: "Workflows", value: stats.workflows, icon: GitBranch, change: null },
    { label: "Conversations", value: stats.sessions, icon: MessageSquare, change: null },
  ]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-lg font-medium">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of your agent orchestration system
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {metrics.map(({ label, value, icon: Icon }) => (
          <Card key={label} className="bg-card hover:bg-secondary/30 transition-colors duration-150">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs text-muted-foreground">{label}</p>
                  <p className="text-2xl font-semibold mt-1 font-mono">{value}</p>
                </div>
                <div className="p-2 rounded-md bg-secondary">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Recent Tasks */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between">
              <span>Recent Tasks</span>
              <span className="text-xs text-muted-foreground font-normal font-mono">
                {recentTasks.length} total
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {recentTasks.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <ListTodo className="h-8 w-8 mx-auto mb-2 opacity-30" />
                <p className="text-sm">No tasks yet</p>
              </div>
            ) : (
              <div className="space-y-1">
                {recentTasks.slice(0, 5).map((task) => (
                  <div
                    key={task.task_id}
                    className="flex items-center gap-3 p-2 rounded-md hover:bg-secondary/50 transition-colors duration-150 cursor-pointer"
                  >
                    {getStatusIcon(task.status)}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{task.name}</p>
                      <p className="text-xs text-muted-foreground font-mono">
                        {truncateId(task.task_id)}
                      </p>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(task.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* System Status */}
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center justify-between">
              <span>System Status</span>
              <Badge variant="success" className="font-mono text-[10px]">
                operational
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { name: "API Server", status: "healthy", latency: "12ms" },
                { name: "NATS Messaging", status: "healthy", latency: "3ms" },
                { name: "Redis Cache", status: "healthy", latency: "1ms" },
                { name: "PostgreSQL", status: "healthy", latency: "5ms" },
              ].map((service) => (
                <div
                  key={service.name}
                  className="flex items-center justify-between p-2 rounded-md bg-secondary/30"
                >
                  <div className="flex items-center gap-2">
                    <div className={cn(
                      "w-1.5 h-1.5 rounded-full",
                      service.status === "healthy" ? "bg-success" : "bg-destructive"
                    )} />
                    <span className="text-sm">{service.name}</span>
                  </div>
                  <span className="text-xs text-muted-foreground font-mono">
                    {service.latency}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Activity Timeline placeholder */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Activity</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            <Activity className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p className="text-sm">Activity timeline coming soon</p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
