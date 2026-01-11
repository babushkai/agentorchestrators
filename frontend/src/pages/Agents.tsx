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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  Progress,
} from '@/components/ui'
import { appStore } from '@/stores/app'
import type { Agent, AgentStatus } from '@/types'
import { formatRelativeTime } from '@/lib/utils'

const statusConfig: Record<AgentStatus, { label: string; color: string }> = {
  idle: { label: 'Idle', color: 'bg-muted-foreground' },
  running: { label: 'Running', color: 'bg-primary animate-pulse-subtle' },
  success: { label: 'Success', color: 'bg-success' },
  error: { label: 'Error', color: 'bg-destructive' },
  pending: { label: 'Pending', color: 'bg-warning' },
}

const AgentCard: Component<{ agent: Agent; onSelect: () => void }> = (props) => {
  const status = () => statusConfig[props.agent.status]

  return (
    <Card
      class="cursor-pointer hover:border-border-hover transition-colors"
      onClick={props.onSelect}
    >
      <CardHeader class="pb-3">
        <div class="flex items-start justify-between">
          <div>
            <CardTitle class="text-base">{props.agent.name}</CardTitle>
            <CardDescription class="mt-1">{props.agent.description}</CardDescription>
          </div>
          <Badge variant={props.agent.status}>{status().label}</Badge>
        </div>
      </CardHeader>
      <CardContent class="space-y-3">
        <div class="flex items-center gap-2 text-xs text-muted-foreground">
          <span class="px-2 py-1 rounded bg-secondary">{props.agent.model}</span>
          <Show when={props.agent.lastRunAt}>
            <span>Last run: {formatRelativeTime(props.agent.lastRunAt!)}</span>
          </Show>
        </div>
        <div class="space-y-1">
          <div class="flex justify-between text-xs">
            <span class="text-muted-foreground">Tasks Completed</span>
            <span>{props.agent.tasksCompleted}/{props.agent.tasksTotal}</span>
          </div>
          <Progress value={props.agent.tasksCompleted} max={props.agent.tasksTotal || 1} />
        </div>
      </CardContent>
    </Card>
  )
}

const Agents: Component = () => {
  const [searchQuery, setSearchQuery] = createSignal('')
  const [statusFilter, setStatusFilter] = createSignal<AgentStatus | 'all'>('all')
  const [isCreateDialogOpen, setIsCreateDialogOpen] = createSignal(false)
  const [newAgentName, setNewAgentName] = createSignal('')
  const [newAgentDescription, setNewAgentDescription] = createSignal('')
  const [newAgentModel, setNewAgentModel] = createSignal('gpt-4')

  onMount(() => {
    appStore.fetchAgents()
  })

  const filteredAgents = () => {
    return appStore.agents().filter((agent) => {
      const matchesSearch =
        agent.name.toLowerCase().includes(searchQuery().toLowerCase()) ||
        agent.description.toLowerCase().includes(searchQuery().toLowerCase())
      const matchesStatus = statusFilter() === 'all' || agent.status === statusFilter()
      return matchesSearch && matchesStatus
    })
  }

  const handleCreateAgent = () => {
    // TODO: API call to create agent
    console.log('Creating agent:', {
      name: newAgentName(),
      description: newAgentDescription(),
      model: newAgentModel(),
    })
    setIsCreateDialogOpen(false)
    setNewAgentName('')
    setNewAgentDescription('')
    setNewAgentModel('gpt-4')
  }

  return (
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-foreground">Agents</h1>
          <p class="text-muted-foreground text-sm mt-1">Manage and monitor your AI agents</p>
        </div>
        <Button onClick={() => setIsCreateDialogOpen(true)}>
          <svg class="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Create Agent
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
            placeholder="Search agents..."
            class="pl-10"
            value={searchQuery()}
            onInput={(e) => setSearchQuery(e.currentTarget.value)}
          />
        </div>
        <div class="flex gap-2">
          <For each={['all', 'idle', 'running', 'success', 'error', 'pending'] as const}>
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

      {/* Agents Grid */}
      <Show
        when={filteredAgents().length > 0}
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
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
              <h3 class="text-lg font-medium mb-1">No agents found</h3>
              <p class="text-sm text-muted-foreground mb-4">
                {searchQuery() || statusFilter() !== 'all'
                  ? 'Try adjusting your search or filters'
                  : 'Get started by creating your first agent'}
              </p>
              <Show when={!searchQuery() && statusFilter() === 'all'}>
                <Button onClick={() => setIsCreateDialogOpen(true)}>Create Agent</Button>
              </Show>
            </div>
          </Card>
        }
      >
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <For each={filteredAgents()}>
            {(agent) => (
              <AgentCard
                agent={agent}
                onSelect={() => appStore.setSelectedAgent(agent)}
              />
            )}
          </For>
        </div>
      </Show>

      {/* Create Agent Dialog */}
      <Dialog open={isCreateDialogOpen()} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Agent</DialogTitle>
            <DialogDescription>
              Configure your AI agent with a name, description, and model.
            </DialogDescription>
          </DialogHeader>
          <div class="space-y-4 py-4">
            <div class="space-y-2">
              <label class="text-sm font-medium">Name</label>
              <Input
                placeholder="Agent name"
                value={newAgentName()}
                onInput={(e) => setNewAgentName(e.currentTarget.value)}
              />
            </div>
            <div class="space-y-2">
              <label class="text-sm font-medium">Description</label>
              <Input
                placeholder="What does this agent do?"
                value={newAgentDescription()}
                onInput={(e) => setNewAgentDescription(e.currentTarget.value)}
              />
            </div>
            <div class="space-y-2">
              <label class="text-sm font-medium">Model</label>
              <select
                class="flex h-9 w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                value={newAgentModel()}
                onChange={(e) => setNewAgentModel(e.currentTarget.value)}
              >
                <option value="gpt-4">GPT-4</option>
                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                <option value="claude-3-opus">Claude 3 Opus</option>
                <option value="claude-3-sonnet">Claude 3 Sonnet</option>
              </select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateAgent} disabled={!newAgentName()}>
              Create Agent
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export { Agents }
