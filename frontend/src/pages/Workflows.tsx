import { type Component, For, Show, createSignal, onMount } from 'solid-js'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Button,
  Badge,
  Input,
} from '@/components/ui'
import { appStore } from '@/stores/app'
import type { Workflow, TaskStatus } from '@/types'
import { formatRelativeTime, truncateId } from '@/lib/utils'

const statusConfig: Record<TaskStatus, { label: string }> = {
  pending: { label: 'Pending' },
  running: { label: 'Running' },
  completed: { label: 'Completed' },
  failed: { label: 'Failed' },
  cancelled: { label: 'Cancelled' },
}

const WorkflowCard: Component<{ workflow: Workflow; onSelect: () => void }> = (props) => {
  const completedSteps = () => props.workflow.steps.filter((s) => s.status === 'completed').length
  const totalSteps = () => props.workflow.steps.length

  return (
    <Card class="cursor-pointer hover:border-border-hover transition-colors" onClick={props.onSelect}>
      <CardHeader class="pb-3">
        <div class="flex items-start justify-between">
          <div>
            <CardTitle class="text-base">{props.workflow.name}</CardTitle>
            <CardDescription class="mt-1 text-xs font-mono">
              #{truncateId(props.workflow.id)}
            </CardDescription>
          </div>
          <Badge
            variant={
              props.workflow.status === 'completed'
                ? 'success'
                : props.workflow.status === 'failed'
                ? 'error'
                : props.workflow.status === 'cancelled'
                ? 'secondary'
                : props.workflow.status
            }
          >
            {statusConfig[props.workflow.status].label}
          </Badge>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <Show when={props.workflow.description}>
          <p class="text-sm text-muted-foreground">{props.workflow.description}</p>
        </Show>

        {/* Steps visualization */}
        <div class="space-y-2">
          <div class="flex items-center justify-between text-xs">
            <span class="text-muted-foreground">Steps</span>
            <span>
              {completedSteps()}/{totalSteps()}
            </span>
          </div>
          <div class="flex gap-1">
            <For each={props.workflow.steps}>
              {(step) => (
                <div
                  class={`h-2 flex-1 rounded-full ${
                    step.status === 'completed'
                      ? 'bg-success'
                      : step.status === 'running'
                      ? 'bg-primary animate-pulse-subtle'
                      : step.status === 'failed'
                      ? 'bg-destructive'
                      : 'bg-muted'
                  }`}
                  title={`${step.name}: ${step.status}`}
                />
              )}
            </For>
          </div>
        </div>

        <div class="flex items-center justify-between text-xs text-muted-foreground">
          <span>Created {formatRelativeTime(props.workflow.createdAt)}</span>
          <Show when={props.workflow.lastRunAt}>
            <span>Last run {formatRelativeTime(props.workflow.lastRunAt!)}</span>
          </Show>
        </div>
      </CardContent>
    </Card>
  )
}

const Workflows: Component = () => {
  const [searchQuery, setSearchQuery] = createSignal('')
  const [statusFilter, setStatusFilter] = createSignal<TaskStatus | 'all'>('all')

  onMount(() => {
    appStore.fetchWorkflows()
  })

  const filteredWorkflows = () => {
    return appStore.workflows().filter((workflow) => {
      const matchesSearch =
        workflow.name.toLowerCase().includes(searchQuery().toLowerCase()) ||
        workflow.id.toLowerCase().includes(searchQuery().toLowerCase())
      const matchesStatus = statusFilter() === 'all' || workflow.status === statusFilter()
      return matchesSearch && matchesStatus
    })
  }

  return (
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-foreground">Workflows</h1>
          <p class="text-muted-foreground text-sm mt-1">Create and manage multi-step agent processes</p>
        </div>
        <Button>
          <svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Create Workflow
        </Button>
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
            placeholder="Search workflows..."
            class="pl-10"
            value={searchQuery()}
            onInput={(e) => setSearchQuery(e.currentTarget.value)}
          />
        </div>
        <div class="flex gap-2 flex-wrap">
          <For each={['all', 'pending', 'running', 'completed', 'failed'] as const}>
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

      {/* Workflows Grid */}
      <Show
        when={filteredWorkflows().length > 0}
        fallback={
          <Card class="py-12">
            <div class="text-center">
              <svg
                class="w-12 h-12 mx-auto text-muted-foreground mb-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="1.5"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
              </svg>
              <h3 class="text-lg font-medium mb-1">No workflows found</h3>
              <p class="text-sm text-muted-foreground mb-4">
                {searchQuery() || statusFilter() !== 'all'
                  ? 'Try adjusting your search or filters'
                  : 'Create a workflow to orchestrate multi-step processes'}
              </p>
              <Show when={!searchQuery() && statusFilter() === 'all'}>
                <Button>Create Workflow</Button>
              </Show>
            </div>
          </Card>
        }
      >
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <For each={filteredWorkflows()}>
            {(workflow) => (
              <WorkflowCard
                workflow={workflow}
                onSelect={() => appStore.setSelectedWorkflow(workflow)}
              />
            )}
          </For>
        </div>
      </Show>
    </div>
  )
}

export { Workflows }
