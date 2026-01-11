import { useState } from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { formatRelativeTime, truncateId } from "@/lib/utils"
import { Bot, Plus, Trash2, X } from "lucide-react"
import type { Agent, AgentCreate } from "@/types/api"
import * as api from "@/api/client"

interface AgentsProps {
  agents: Agent[]
  onRefresh: () => void
  isLoading: boolean
}

const getStatusBadge = (status: Agent["status"]) => {
  switch (status) {
    case "running":
      return <Badge variant="running">running</Badge>
    case "idle":
      return <Badge variant="idle">idle</Badge>
    case "error":
      return <Badge variant="error">error</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

interface CreateAgentModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: AgentCreate) => void
  isSubmitting: boolean
}

function CreateAgentModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
}: CreateAgentModalProps) {
  const [formData, setFormData] = useState<AgentCreate>({
    name: "",
    role: "",
    goal: "",
    backstory: "",
    tools: [],
  })

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    onSubmit(formData)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-md mx-4 animate-slide-in-right">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle>New Agent</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Name</label>
              <Input
                placeholder="e.g., Research Assistant"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Role</label>
              <Input
                placeholder="e.g., Researcher"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Goal</label>
              <Input
                placeholder="What should this agent accomplish?"
                value={formData.goal}
                onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Backstory (optional)</label>
              <textarea
                className="flex min-h-[80px] w-full rounded-md border border-border bg-input px-3 py-2 text-sm transition-colors duration-150 placeholder:text-muted-foreground hover:border-border-hover focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background"
                placeholder="Provide context..."
                value={formData.backstory}
                onChange={(e) => setFormData({ ...formData, backstory: e.target.value })}
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "Creating..." : "Create Agent"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export function Agents({ agents, onRefresh: _onRefresh, isLoading: _isLoading }: AgentsProps) {
  void _onRefresh
  void _isLoading
  const [showCreateModal, setShowCreateModal] = useState(false)
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: api.createAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] })
      setShowCreateModal(false)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: api.deleteAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agents"] })
    },
  })

  const handleDelete = (agentId: string) => {
    if (confirm("Delete this agent?")) {
      deleteMutation.mutate(agentId)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium">Agents</h1>
          <p className="text-sm text-muted-foreground">
            {agents.length} agent{agents.length !== 1 ? "s" : ""} configured
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} size="sm">
          <Plus className="h-4 w-4" />
          New Agent
        </Button>
      </div>

      {/* Agents List */}
      {agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Bot className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground mb-4">No agents configured</p>
            <Button onClick={() => setShowCreateModal(true)} size="sm">
              <Plus className="h-4 w-4" />
              Create Agent
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {agents.map((agent) => (
            <Card
              key={agent.agent_id}
              className="hover:bg-secondary/30 transition-colors duration-150"
            >
              <CardContent className="p-4">
                <div className="flex items-center gap-4">
                  <div className="p-2 rounded-md bg-secondary">
                    <Bot className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{agent.name}</span>
                      {getStatusBadge(agent.status)}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs text-muted-foreground">{agent.role}</span>
                      <span className="text-xs text-muted-foreground">·</span>
                      <span className="text-xs text-muted-foreground font-mono">
                        {truncateId(agent.agent_id)}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">
                      {agent.last_heartbeat
                        ? formatRelativeTime(agent.last_heartbeat)
                        : formatRelativeTime(agent.created_at)}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={() => handleDelete(agent.agent_id)}
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <CreateAgentModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isSubmitting={createMutation.isPending}
      />
    </div>
  )
}
