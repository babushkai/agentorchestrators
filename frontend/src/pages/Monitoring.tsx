import { type Component, For, Show, createSignal, onMount, onCleanup } from 'solid-js'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
} from '@/components/ui'
import { appStore } from '@/stores/app'
import type { LogEntry } from '@/types'
import { cn, formatDate } from '@/lib/utils'

const levelConfig: Record<LogEntry['level'], { label: string; class: string }> = {
  debug: { label: 'DEBUG', class: 'text-muted-foreground' },
  info: { label: 'INFO', class: 'text-info' },
  warn: { label: 'WARN', class: 'text-warning' },
  error: { label: 'ERROR', class: 'text-destructive' },
}

const LogRow: Component<{ log: LogEntry }> = (props) => {
  const [isExpanded, setIsExpanded] = createSignal(false)

  return (
    <div
      class="border-b border-border hover:bg-secondary/30 cursor-pointer transition-colors"
      onClick={() => setIsExpanded(!isExpanded())}
    >
      <div class="flex items-center gap-3 px-4 py-2 font-mono text-xs">
        <span class="text-muted-foreground w-40 shrink-0">
          {formatDate(props.log.timestamp)}
        </span>
        <span class={cn('w-14 shrink-0 font-bold', levelConfig[props.log.level].class)}>
          {levelConfig[props.log.level].label}
        </span>
        <span class="text-primary w-24 shrink-0">[{props.log.source}]</span>
        <span class="flex-1 truncate">{props.log.message}</span>
      </div>
      <Show when={isExpanded() && props.log.metadata}>
        <div class="px-4 py-2 bg-secondary/50">
          <pre class="text-xs text-muted-foreground overflow-auto">
            {JSON.stringify(props.log.metadata, null, 2)}
          </pre>
        </div>
      </Show>
    </div>
  )
}

const MetricCard: Component<{
  title: string
  value: string | number
  unit?: string
  trend?: number
  icon: Component<{ class?: string }>
}> = (props) => (
  <Card>
    <CardContent class="p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-xs text-muted-foreground mb-1">{props.title}</p>
          <div class="flex items-baseline gap-1">
            <span class="text-2xl font-bold">{props.value}</span>
            <Show when={props.unit}>
              <span class="text-sm text-muted-foreground">{props.unit}</span>
            </Show>
          </div>
          <Show when={props.trend !== undefined}>
            <span class={cn('text-xs', props.trend! >= 0 ? 'text-success' : 'text-destructive')}>
              {props.trend! >= 0 ? '+' : ''}{props.trend}% from last hour
            </span>
          </Show>
        </div>
        <div class="w-10 h-10 rounded-lg bg-secondary flex items-center justify-center">
          <props.icon class="w-5 h-5 text-muted-foreground" />
        </div>
      </div>
    </CardContent>
  </Card>
)

const CpuIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
    <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 3v1.5M4.5 8.25H3m18 0h-1.5M4.5 12H3m18 0h-1.5m-15 3.75H3m18 0h-1.5M8.25 19.5V21M12 3v1.5m0 15V21m3.75-18v1.5m0 15V21m-9-1.5h10.5a2.25 2.25 0 002.25-2.25V6.75a2.25 2.25 0 00-2.25-2.25H6.75A2.25 2.25 0 004.5 6.75v10.5a2.25 2.25 0 002.25 2.25zm.75-12h9v9h-9v-9z" />
  </svg>
)

const MemoryIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
    <path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.737 5.1a3.375 3.375 0 012.7-1.35h7.126c1.062 0 2.062.5 2.7 1.35l2.587 3.45a4.5 4.5 0 01.9 2.7m0 0a3 3 0 01-3 3m0 3h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008zm-3 6h.008v.008h-.008v-.008zm0-6h.008v.008h-.008v-.008z" />
  </svg>
)

const AgentIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
    <path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
  </svg>
)

const TaskIcon: Component<{ class?: string }> = (props) => (
  <svg class={props.class} fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
    <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" />
  </svg>
)

const Monitoring: Component = () => {
  const [levelFilter, setLevelFilter] = createSignal<LogEntry['level'] | 'all'>('all')
  const [searchQuery, setSearchQuery] = createSignal('')
  const [isLive, setIsLive] = createSignal(true)

  // Mock metrics
  const [metrics, setMetrics] = createSignal({
    cpu: 42,
    memory: 68,
    activeAgents: 3,
    runningTasks: 7,
    queuedTasks: 12,
    uptime: 86400,
  })

  onMount(() => {
    appStore.fetchLogs()

    // Simulate live updates
    const interval = setInterval(() => {
      if (isLive()) {
        setMetrics((m) => ({
          ...m,
          cpu: Math.min(100, Math.max(0, m.cpu + (Math.random() - 0.5) * 10)),
          memory: Math.min(100, Math.max(0, m.memory + (Math.random() - 0.5) * 5)),
        }))
      }
    }, 2000)

    onCleanup(() => clearInterval(interval))
  })

  const filteredLogs = () => {
    return appStore.logs().filter((log) => {
      const matchesLevel = levelFilter() === 'all' || log.level === levelFilter()
      const matchesSearch =
        log.message.toLowerCase().includes(searchQuery().toLowerCase()) ||
        log.source.toLowerCase().includes(searchQuery().toLowerCase())
      return matchesLevel && matchesSearch
    })
  }

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    return `${days}d ${hours}h ${mins}m`
  }

  return (
    <div class="space-y-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-semibold text-foreground">Monitoring</h1>
          <p class="text-muted-foreground text-sm mt-1">System metrics and logs</p>
        </div>
        <div class="flex items-center gap-2">
          <Button
            variant={isLive() ? 'default' : 'outline'}
            size="sm"
            onClick={() => setIsLive(!isLive())}
          >
            <div class={cn('w-2 h-2 rounded-full mr-2', isLive() ? 'bg-success animate-pulse' : 'bg-muted-foreground')} />
            {isLive() ? 'Live' : 'Paused'}
          </Button>
        </div>
      </div>

      {/* Metrics */}
      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <MetricCard
          title="CPU Usage"
          value={metrics().cpu.toFixed(1)}
          unit="%"
          icon={CpuIcon}
        />
        <MetricCard
          title="Memory"
          value={metrics().memory.toFixed(1)}
          unit="%"
          icon={MemoryIcon}
        />
        <MetricCard
          title="Active Agents"
          value={metrics().activeAgents}
          icon={AgentIcon}
        />
        <MetricCard
          title="Running Tasks"
          value={metrics().runningTasks}
          icon={TaskIcon}
        />
        <MetricCard
          title="Queued Tasks"
          value={metrics().queuedTasks}
          icon={TaskIcon}
        />
        <MetricCard
          title="Uptime"
          value={formatUptime(metrics().uptime)}
          icon={CpuIcon}
        />
      </div>

      {/* Logs */}
      <Card>
        <CardHeader class="border-b border-border">
          <div class="flex items-center justify-between">
            <CardTitle>System Logs</CardTitle>
            <div class="flex items-center gap-2">
              <div class="relative">
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
                  placeholder="Search logs..."
                  class="pl-10 w-64"
                  value={searchQuery()}
                  onInput={(e) => setSearchQuery(e.currentTarget.value)}
                />
              </div>
              <div class="flex gap-1">
                <For each={['all', 'debug', 'info', 'warn', 'error'] as const}>
                  {(level) => (
                    <Button
                      variant={levelFilter() === level ? 'default' : 'ghost'}
                      size="sm"
                      onClick={() => setLevelFilter(level)}
                      class="text-xs"
                    >
                      {level === 'all' ? 'All' : levelConfig[level].label}
                    </Button>
                  )}
                </For>
              </div>
            </div>
          </div>
        </CardHeader>
        <CardContent class="p-0 max-h-[500px] overflow-auto">
          <Show
            when={filteredLogs().length > 0}
            fallback={
              <div class="p-8 text-center text-muted-foreground">
                <p>No logs to display</p>
              </div>
            }
          >
            <For each={filteredLogs()}>
              {(log) => <LogRow log={log} />}
            </For>
          </Show>
        </CardContent>
      </Card>
    </div>
  )
}

export { Monitoring }
