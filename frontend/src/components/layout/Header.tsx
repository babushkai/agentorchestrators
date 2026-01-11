import { type Component } from 'solid-js'
import { Button } from '@/components/ui'
import { appStore } from '@/stores/app'

const Header: Component = () => {
  return (
    <header class="h-14 border-b border-border bg-card flex items-center justify-between px-4 shrink-0">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
            <svg class="w-5 h-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
            </svg>
          </div>
          <span class="text-base font-semibold text-foreground">Agent Orchestrator</span>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <Button
          variant="outline"
          size="sm"
          onClick={() => appStore.setIsCommandPaletteOpen(true)}
          class="hidden sm:flex items-center gap-2 text-muted-foreground"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
          <span class="text-xs">Search</span>
          <kbd class="ml-2 px-1.5 py-0.5 text-[10px] bg-muted rounded font-mono">⌘K</kbd>
        </Button>

        <div class="flex items-center gap-2 px-3 py-1.5 rounded-md bg-secondary">
          <div
            class={`w-2 h-2 rounded-full transition-colors ${
              appStore.isConnected() ? 'bg-success' : 'bg-destructive'
            }`}
          />
          <span class="text-xs text-muted-foreground">
            {appStore.isConnected() ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>
    </header>
  )
}

export { Header }
