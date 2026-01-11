import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  ListTodo,
  Bot,
  GitBranch,
  MessageSquare,
  FolderOpen,
} from "lucide-react"

interface NavItem {
  icon: React.ElementType
  label: string
  href: string
  badge?: number
}

interface SidebarProps {
  currentPage: string
  onNavigate: (page: string) => void
  counts: {
    tasks: number
    agents: number
    workflows: number
    sessions: number
  }
}

const navItems: NavItem[] = [
  { icon: LayoutDashboard, label: "Dashboard", href: "dashboard" },
  { icon: Bot, label: "Agents", href: "agents" },
  { icon: ListTodo, label: "Tasks", href: "tasks" },
  { icon: MessageSquare, label: "Conversations", href: "conversations" },
  { icon: GitBranch, label: "Workflows", href: "workflows" },
  { icon: FolderOpen, label: "Files", href: "files" },
]

export function Sidebar({ currentPage, onNavigate, counts }: SidebarProps) {
  const getBadge = (href: string): number | undefined => {
    switch (href) {
      case "tasks": return counts.tasks || undefined
      case "agents": return counts.agents || undefined
      case "workflows": return counts.workflows || undefined
      case "conversations": return counts.sessions || undefined
      default: return undefined
    }
  }

  return (
    <aside className="w-52 border-r border-border flex-shrink-0 flex flex-col">
      <nav className="flex-1 py-3 px-2">
        <div className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon
            const badge = getBadge(item.href)
            const isActive = currentPage === item.href

            return (
              <button
                key={item.href}
                onClick={() => onNavigate(item.href)}
                className={cn(
                  "w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors duration-150",
                  isActive
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/50"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="flex-1 text-left truncate">{item.label}</span>
                {badge !== undefined && badge > 0 && (
                  <span className="text-xs text-muted-foreground font-mono">
                    {badge}
                  </span>
                )}
              </button>
            )
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <div className="text-[10px] text-muted-foreground font-mono">
          <div className="flex items-center justify-between">
            <span>API</span>
            <span className="text-success">healthy</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
