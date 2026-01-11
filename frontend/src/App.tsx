import { useState, useEffect, useCallback } from "react"
import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query"
import { Header } from "@/components/layout/Header"
import { Sidebar } from "@/components/layout/Sidebar"
import { Dashboard } from "@/components/pages/Dashboard"
import * as api from "@/api/client"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      retry: 1,
    },
  },
})

function AppContent() {
  const [currentPage, setCurrentPage] = useState("dashboard")
  const [isConnected, setIsConnected] = useState(false)

  // Queries
  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 10000,
  })

  const { data: agents = [] } = useQuery({
    queryKey: ["agents"],
    queryFn: api.getAgents,
  })

  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ["tasks"],
    queryFn: api.getTasks,
  })

  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.getSessions,
  })

  const { data: workflows = [] } = useQuery({
    queryKey: ["workflows"],
    queryFn: api.getWorkflows,
  })

  // Update connection status based on health check
  useEffect(() => {
    setIsConnected(health?.status === "healthy")
  }, [health])

  // Counts for sidebar badges
  const counts = {
    tasks: tasks.length,
    agents: agents.length,
    workflows: workflows.length,
    sessions: sessions.length,
  }

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries()
  }, [])

  const renderPage = () => {
    switch (currentPage) {
      case "dashboard":
        return (
          <Dashboard
            stats={counts}
            recentTasks={tasks}
            health={health || null}
            onRefresh={handleRefresh}
            isLoading={tasksLoading}
          />
        )
      case "tasks":
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Tasks</h2>
            <p className="text-muted-foreground">Task management coming soon...</p>
          </div>
        )
      case "agents":
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Agents</h2>
            <p className="text-muted-foreground">Agent management coming soon...</p>
          </div>
        )
      case "workflows":
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Workflows</h2>
            <p className="text-muted-foreground">Workflow management coming soon...</p>
          </div>
        )
      case "conversations":
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Conversations</h2>
            <p className="text-muted-foreground">Chat interface coming soon...</p>
          </div>
        )
      case "files":
        return (
          <div className="space-y-6">
            <h2 className="text-2xl font-bold">Files</h2>
            <p className="text-muted-foreground">File management coming soon...</p>
          </div>
        )
      default:
        return null
    }
  }

  return (
    <div className="min-h-screen bg-background">
      <Header isConnected={isConnected} />
      <div className="flex h-[calc(100vh-3.5rem)]">
        <Sidebar
          currentPage={currentPage}
          onNavigate={setCurrentPage}
          counts={counts}
        />
        <main className="flex-1 overflow-auto p-6">
          {renderPage()}
        </main>
      </div>
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  )
}

export default App
