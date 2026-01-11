import { cn } from "@/lib/utils"

interface HeaderProps {
  isConnected: boolean
}

export function Header({ isConnected }: HeaderProps) {
  return (
    <header className="h-12 border-b border-border bg-background/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="flex h-full items-center justify-between px-4">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-primary flex items-center justify-center">
              <span className="text-xs font-bold text-primary-foreground">A</span>
            </div>
            <span className="text-sm font-medium">Agent Orchestrator</span>
          </div>
          <span className="text-xs text-muted-foreground font-mono">v0.1.0</span>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-4">
          {/* Command palette hint */}
          <div className="hidden md:flex items-center gap-1.5 text-xs text-muted-foreground">
            <kbd className="px-1.5 py-0.5 rounded bg-secondary border border-border font-mono text-[10px]">⌘</kbd>
            <kbd className="px-1.5 py-0.5 rounded bg-secondary border border-border font-mono text-[10px]">K</kbd>
          </div>

          {/* Connection status */}
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "w-1.5 h-1.5 rounded-full",
                isConnected ? "bg-success" : "bg-destructive"
              )}
            />
            <span className="text-xs text-muted-foreground">
              {isConnected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}
