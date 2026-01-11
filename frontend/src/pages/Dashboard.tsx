import { type Component, onMount, For, Show } from 'solid-js'
import { A } from '@solidjs/router'
import { Card, CardContent, CardHeader, CardTitle, Badge, Progress } from '@/components/ui'
import { appStore } from '@/stores/app'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: number | string
  description?: string
  trend?: { value: number; isPositive: boolean }
  icon: Component<{ class?: string }>
}

const StatCard: Component<StatCardProps> = (props) => (
  <Card>
    <CardHeader class="flex flex-row items-center justify-between pb-2">
      <CardTitle class="text-sm font-medium text-muted-foreground">{props.title}</CardTitle>
      <props.icon class="w-4 h-4 text-muted-foreground" />
    </CardHeader>
    <CardContent>
      <div class="text-2xl font-bold">{props.value}</div>
      <Show when={props.description}>
        <p class="text-xs text-muted-foreground mt-1">{props.description}</p>
      </Show>
      <Show when={props.trend}>
        <p class={cn('text-xs mt-1', props.trend!.isPositive ? 'text-success' : 'text-destructive')}>
          {props.trend!.isPositive ? '+' : ''}{props.trend!.value}% from last hour
        </p>
      </Show>
    </CardContent>
  </Card>
)

const AgentIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
  </svg>
)

const TaskIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
)

const WorkflowIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
)

const ChatIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
    <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
  </svg>
)

// Mock recent activity
const recentActivity = [
  { id: '1', type: 'task', message: 'Task "Generate Report" completed', time: '2m ago', status: 'success' as const },
  { id: '2', type: 'agent', message: 'Agent "ResearchBot" started', time: '5m ago', status: 'running' as const },
  { id: '3', type: 'workflow', message: 'Workflow "Data Pipeline" triggered', time: '12m ago', status: 'pending' as const },
  { id: '4', type: 'task', message: 'Task "Process Data" failed', time: '18m ago', status: 'error' as const },
  { id: '5', type: 'conversation', message: 'New conversation with "AssistantBot"', time: '25m ago', status: 'idle' as const },
]

const statusColors = {
  success: 'bg-success',
  running: 'bg-primary animate-pulse-subtle',
  pending: 'bg-warning',
  error: 'bg-destructive',
  idle: 'bg-muted-foreground',
}

const Dashboard: Component = () => {
  const stats = appStore.stats

  onMount(() => {
    appStore.fetchStats()
  })

  return (
    <div class="space-y-6">
      <div>
        <h1 class="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p class="text-muted-foreground text-sm mt-1">Overview of your agent orchestration system</p>
      </div>

      {/* Stats Grid */}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Agents"
          value={stats().totalAgents}
          description={`${stats().activeAgents} active`}
          icon={AgentIcon}
        />
        <StatCard
          title="Tasks"
          value={stats().totalTasks}
          description={`${stats().completedTasks} completed, ${stats().failedTasks} failed`}
          icon={TaskIcon}
        />
        <StatCard
          title="Workflows"
          value={stats().totalWorkflows}
          description={`${stats().activeWorkflows} active`}
          icon={WorkflowIcon}
        />
        <StatCard
          title="Conversations"
          value={stats().totalConversations}
          icon={ChatIcon}
        />
      </div>

      {/* Main Content Grid */}
      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Activity */}
        <Card class="lg:col-span-2">
          <CardHeader class="flex flex-row items-center justify-between">
            <CardTitle>Recent Activity</CardTitle>
            <A href="/monitoring" class="text-xs text-primary hover:underline">View all</A>
          </CardHeader>
          <CardContent class="space-y-3">
            <For each={recentActivity}>
              {(activity) => (
                <div class="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <div class={cn('w-2 h-2 rounded-full', statusColors[activity.status])} />
                  <span class="flex-1 text-sm">{activity.message}</span>
                  <span class="text-xs text-muted-foreground">{activity.time}</span>
                </div>
              )}
            </For>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent class="space-y-2">
            <A
              href="/agents"
              class="flex items-center gap-3 p-3 rounded-lg bg-secondary hover:bg-muted transition-colors"
            >
              <AgentIcon class="w-5 h-5 text-primary" />
              <div>
                <p class="text-sm font-medium">Create Agent</p>
                <p class="text-xs text-muted-foreground">Set up a new AI agent</p>
              </div>
            </A>
            <A
              href="/tasks"
              class="flex items-center gap-3 p-3 rounded-lg bg-secondary hover:bg-muted transition-colors"
            >
              <TaskIcon class="w-5 h-5 text-success" />
              <div>
                <p class="text-sm font-medium">Create Task</p>
                <p class="text-xs text-muted-foreground">Assign work to agents</p>
              </div>
            </A>
            <A
              href="/workflows"
              class="flex items-center gap-3 p-3 rounded-lg bg-secondary hover:bg-muted transition-colors"
            >
              <WorkflowIcon class="w-5 h-5 text-warning" />
              <div>
                <p class="text-sm font-medium">Build Workflow</p>
                <p class="text-xs text-muted-foreground">Create multi-step processes</p>
              </div>
            </A>
            <A
              href="/conversations"
              class="flex items-center gap-3 p-3 rounded-lg bg-secondary hover:bg-muted transition-colors"
            >
              <ChatIcon class="w-5 h-5 text-info" />
              <div>
                <p class="text-sm font-medium">Start Conversation</p>
                <p class="text-xs text-muted-foreground">Chat with your agents</p>
              </div>
            </A>
          </CardContent>
        </Card>
      </div>

      {/* Active Agents */}
      <Card>
        <CardHeader class="flex flex-row items-center justify-between">
          <CardTitle>Active Agents</CardTitle>
          <A href="/agents" class="text-xs text-primary hover:underline">Manage agents</A>
        </CardHeader>
        <CardContent>
          <Show
            when={appStore.agents().length > 0}
            fallback={
              <div class="text-center py-8 text-muted-foreground">
                <AgentIcon class="w-12 h-12 mx-auto mb-3 opacity-50" />
                <p class="text-sm">No agents configured yet</p>
                <A href="/agents" class="text-xs text-primary hover:underline">Create your first agent</A>
              </div>
            }
          >
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <For each={appStore.agents().slice(0, 6)}>
                {(agent) => (
                  <div class="p-4 rounded-lg border border-border bg-secondary/50">
                    <div class="flex items-center justify-between mb-2">
                      <span class="font-medium text-sm">{agent.name}</span>
                      <Badge variant={agent.status}>{agent.status}</Badge>
                    </div>
                    <p class="text-xs text-muted-foreground mb-3">{agent.model}</p>
                    <div class="space-y-1">
                      <div class="flex justify-between text-xs">
                        <span class="text-muted-foreground">Progress</span>
                        <span>{agent.tasksCompleted}/{agent.tasksTotal}</span>
                      </div>
                      <Progress value={agent.tasksCompleted} max={agent.tasksTotal || 1} />
                    </div>
                  </div>
                )}
              </For>
            </div>
          </Show>
        </CardContent>
      </Card>
    </div>
  )
}

export { Dashboard }
