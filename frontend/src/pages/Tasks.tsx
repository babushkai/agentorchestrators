import { type Component, For, Show, createSignal, onMount } from 'solid-js'
import {
  Card,
  CardContent,
  CardHeader,
  Button,
  Badge,
  Input,
} from '@/components/ui'
import { appStore } from '@/stores/app'
import type { Task, TaskStatus, TaskPriority } from '@/types'
import { cn, formatRelativeTime, truncateId } from '@/lib/utils'

const statusConfig: Record<TaskStatus, { label: string; variant: TaskStatus }> = {
  pending: { label: 'Pending', variant: 'pending' },
  running: { label: 'Running', variant: 'running' },
  completed: { label: 'Completed', variant: 'success' as TaskStatus },
  failed: { label: 'Failed', variant: 'error' as TaskStatus },
  cancelled: { label: 'Cancelled', variant: 'idle' as TaskStatus },
}

const priorityConfig: Record<TaskPriority, { label: string; class: string }> = {
  low: { label: 'Low', class: 'text-muted-foreground' },
  medium: { label: 'Medium', class: 'text-foreground' },
  high: { label: 'High', class: 'text-warning' },
  critical: { label: 'Critical', class: 'text-destructive' },
}

const TaskRow: Component<{ task: Task; onSelect: () => void }> = (props) => {
  return (
    <div
      class="flex items-center gap-4 p-4 border-b border-border hover:bg-secondary/50 cursor-pointer transition-colors"
      onClick={props.onSelect}
    >
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 mb-1">
          <span class="font-medium text-sm truncate">{props.task.title}</span>
          <span class="text-xs text-muted-foreground font-mono">#{truncateId(props.task.id)}</span>
        </div>
        <Show when={props.task.description}>
          <p class="text-xs text-muted-foreground truncate">{props.task.description}</p>
        </Show>
      </div>

      <div class="flex items-center gap-2">
        <Show when={props.task.agentName}>
          <span class="text-xs px-2 py-1 rounded bg-secondary">{props.task.agentName}</span>
        </Show>
      </div>

      <div class={cn('text-xs font-medium', priorityConfig[props.task.priority].class)}>
        {priorityConfig[props.task.priority].label}
      </div>

      <Badge variant={
        props.task.status === 'completed' ? 'success' :
        props.task.status === 'failed' ? 'error' :
        props.task.status === 'cancelled' ? 'secondary' :
        props.task.status
      }>
        {statusConfig[props.task.status].label}
      </Badge>

      <span class="text-xs text-muted-foreground w-20 text-right">
        {formatRelativeTime(props.task.createdAt)}
      </span>
    </div>
  )
}

const Tasks: Component = () => {
  const [searchQuery, setSearchQuery] = createSignal('')
  const [statusFilter, setStatusFilter] = createSignal<TaskStatus | 'all'>('all')

  onMount(() => {
    appStore.fetchTasks()
  })

  const filteredTasks = () => {
    return appStore.tasks().filter((task) => {
      const matchesSearch =
        task.title.toLowerCase().includes(searchQuery().toLowerCase()) ||
        task.id.toLowerCase().includes(searchQuery().toLowerCase())
      const matchesStatus = statusFilter() === 'all' || task.status === statusFilter()
      return matchesSearch && matchesStatus
    })
  }

  const taskCounts = () => {
    const tasks = appStore.tasks()
    return {
      total: tasks.length,
      pending: tasks.filter((t) => t.status === 'pending').length,
      running: tasks.filter((t) => t.status === 'running').length,
      completed: tasks.filter((t) => t.status === 'completed').length,
      failed: tasks.filter((t) => t.status === 'failed').length,
    }
  }

  return (
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-foreground">Tasks</h1>
          <p class="text-muted-foreground text-sm mt-1">View and manage agent tasks</p>
        </div>
        <Button>
          <svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Create Task
        </Button>
      </div>

      {/* Stats */}
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
        <Card class="p-4">
          <div class="text-2xl font-bold">{taskCounts().total}</div>
          <div class="text-xs text-muted-foreground">Total Tasks</div>
        </Card>
        <Card class="p-4">
          <div class="text-2xl font-bold text-warning">{taskCounts().pending}</div>
          <div class="text-xs text-muted-foreground">Pending</div>
        </Card>
        <Card class="p-4">
          <div class="text-2xl font-bold text-primary">{taskCounts().running}</div>
          <div class="text-xs text-muted-foreground">Running</div>
        </Card>
        <Card class="p-4">
          <div class="text-2xl font-bold text-success">{taskCounts().completed}</div>
          <div class="text-xs text-muted-foreground">Completed</div>
        </Card>
        <Card class="p-4">
          <div class="text-2xl font-bold text-destructive">{taskCounts().failed}</div>
          <div class="text-xs text-muted-foreground">Failed</div>
        </Card>
      </div>

      {/* Filters */}
      <div class="flex flex-col sm:flex-row gap-4">
        <div class="relative flex-1 max-w-sm">
          <svg
            class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <Input
            type="text"
            placeholder="Search tasks..."
            class="pl-10"
            value={searchQuery()}
            onInput={(e) => setSearchQuery(e.currentTarget.value)}
          />
        </div>
        <div class="flex gap-2 flex-wrap">
          <For each={['all', 'pending', 'running', 'completed', 'failed', 'cancelled'] as const}>
            {(status) => (
              <Button
                variant={statusFilter() === status ? 'default' : 'outline'}
                size="sm"
                onClick={() => setStatusFilter(status)}
              >
                {status === 'all' ? 'All' : statusConfig[status].label}
              </Button>
            )}
          </For>
        </div>
      </div>

      {/* Tasks List */}
      <Card>
        <CardHeader class="border-b border-border py-3">
          <div class="flex items-center gap-4 text-xs text-muted-foreground font-medium px-4">
            <div class="flex-1">Task</div>
            <div class="w-24">Agent</div>
            <div class="w-16">Priority</div>
            <div class="w-24">Status</div>
            <div class="w-20 text-right">Created</div>
          </div>
        </CardHeader>
        <CardContent class="p-0">
          <Show
            when={filteredTasks().length > 0}
            fallback={
              <div class="text-center py-12">
                <svg
                  class="w-12 h-12 mx-auto text-muted-foreground mb-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  stroke-width="1.5"
                >
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <h3 class="text-lg font-medium mb-1">No tasks found</h3>
                <p class="text-sm text-muted-foreground">
                  {searchQuery() || statusFilter() !== 'all'
                    ? 'Try adjusting your search or filters'
                    : 'Create a task to get started'}
                </p>
              </div>
            }
          >
            <For each={filteredTasks()}>
              {(task) => (
                <TaskRow
                  task={task}
                  onSelect={() => appStore.setSelectedTask(task)}
                />
              )}
            </For>
          </Show>
        </CardContent>
      </Card>
    </div>
  )
}

export { Tasks }
