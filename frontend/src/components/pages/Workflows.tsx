import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { formatRelativeTime, truncateId } from "@/lib/utils"
import {
  GitBranch,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  ArrowRight,
} from "lucide-react"
import type { Workflow, Agent } from "@/types/api"

interface WorkflowsProps {
  workflows: Workflow[]
  agents: Agent[]
  onRefresh: () => void
  isLoading: boolean
}

const getStatusBadge = (status: Workflow["status"]) => {
  switch (status) {
    case "completed":
      return <Badge variant="idle">completed</Badge>
    case "active":
      return <Badge variant="running">active</Badge>
    case "draft":
      return <Badge variant="secondary">draft</Badge>
    case "failed":
      return <Badge variant="error">failed</Badge>
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

const getStatusIcon = (status: Workflow["status"]) => {
  switch (status) {
    case "completed":
      return <CheckCircle2 className="h-4 w-4 text-success" />
    case "active":
      return <Play className="h-4 w-4 text-primary" />
    case "draft":
      return <Clock className="h-4 w-4 text-muted-foreground" />
    case "failed":
      return <XCircle className="h-4 w-4 text-destructive" />
    default:
      return null
  }
}

export function Workflows({
  workflows,
  agents,
  onRefresh: _onRefresh,
  isLoading: _isLoading,
}: WorkflowsProps) {
  void _onRefresh
  void _isLoading

  const getAgentName = (agentId: string) => {
    const agent = agents.find((a) => a.agent_id === agentId)
    return agent?.name || truncateId(agentId)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium">Workflows</h1>
          <p className="text-sm text-muted-foreground">
            {workflows.length} workflow{workflows.length !== 1 ? "s" : ""} configured
          </p>
        </div>
        <Button size="sm" disabled>
          <Plus className="h-4 w-4" />
          New Workflow
        </Button>
      </div>

      {/* Workflows List */}
      {workflows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <GitBranch className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground mb-1">No workflows yet</p>
            <p className="text-xs text-muted-foreground text-center max-w-sm mb-4">
              Workflows chain multiple agents together to complete complex tasks.
            </p>
            <Button size="sm" disabled>
              <Plus className="h-4 w-4" />
              Create Workflow
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {workflows.map((workflow) => (
            <Card
              key={workflow.workflow_id}
              className="hover:bg-secondary/30 transition-colors duration-150"
            >
              <CardContent className="p-4">
                <div className="space-y-4">
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="p-2 rounded-md bg-secondary mt-0.5">
                        {getStatusIcon(workflow.status)}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm">{workflow.name}</span>
                          {getStatusBadge(workflow.status)}
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {workflow.description}
                        </p>
                      </div>
                    </div>
                    <Button variant="ghost" size="sm" className="h-8 w-8 p-0" disabled>
                      <Play className="h-4 w-4" />
                    </Button>
                  </div>

                  {/* Steps */}
                  <div className="flex items-center gap-1 flex-wrap pl-11">
                    {workflow.steps
                      .sort((a, b) => a.order - b.order)
                      .map((step, index) => (
                        <div key={step.step_id} className="flex items-center">
                          <div className="flex items-center gap-1.5 bg-secondary rounded-md px-2 py-1">
                            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-primary/20 text-primary text-[10px] font-medium">
                              {step.order}
                            </span>
                            <span className="text-xs font-medium">{step.name}</span>
                            <Badge variant="outline" className="text-[10px] px-1 py-0">
                              {getAgentName(step.agent_id)}
                            </Badge>
                          </div>
                          {index < workflow.steps.length - 1 && (
                            <ArrowRight className="h-3 w-3 mx-1 text-muted-foreground" />
                          )}
                        </div>
                      ))}
                  </div>

                  {/* Footer */}
                  <div className="flex items-center gap-2 pl-11 text-xs text-muted-foreground">
                    <span className="font-mono">{truncateId(workflow.workflow_id)}</span>
                    <span>·</span>
                    <span>{formatRelativeTime(workflow.created_at)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Coming Soon Notice */}
      <div className="text-center py-6 border-t border-border">
        <p className="text-xs text-muted-foreground">
          Visual workflow editor coming soon. Create workflows via the API.
        </p>
      </div>
    </div>
  )
}
