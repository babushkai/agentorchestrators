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

interface NavSection {
  title: string
  items: NavItem[]
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

const navigation: NavSection[] = [
  {
    title: "Overview",
    items: [
      { icon: LayoutDashboard, label: "Dashboard", href: "dashboard" },
    ],
  },
  {
    title: "Management",
    items: [
      { icon: ListTodo, label: "Tasks", href: "tasks" },
      { icon: Bot, label: "Agents", href: "agents" },
      { icon: GitBranch, label: "Workflows", href: "workflows" },
    ],
  },
  {
    title: "Communication",
    items: [
      { icon: MessageSquare, label: "Conversations", href: "conversations" },
    ],
  },
  {
    title: "Resources",
    items: [
      { icon: FolderOpen, label: "Files", href: "files" },
    ],
  },
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
    <aside className="w-60 bg-card border-r border-border flex-shrink-0">
      <nav className="p-4 space-y-6">
        {navigation.map((section) => (
          <div key={section.title}>
            <h3 className="px-3 text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              {section.title}
            </h3>
            <div className="space-y-1">
              {section.items.map((item) => {
                const Icon = item.icon
                const badge = getBadge(item.href)
                const isActive = currentPage === item.href

                return (
                  <button
                    key={item.href}
                    onClick={() => onNavigate(item.href)}
                    className={cn(
                      "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:text-foreground hover:bg-accent"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {badge !== undefined && (
                      <span
                        className={cn(
                          "px-2 py-0.5 text-xs rounded-full",
                          isActive
                            ? "bg-primary-foreground/20 text-primary-foreground"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {badge}
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  )
}
