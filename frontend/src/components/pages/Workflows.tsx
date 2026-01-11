import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn, formatRelativeTime, truncateId } from "@/lib/utils"
import {
  GitBranch,
  Plus,
  RefreshCw,
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
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          Completed
        </Badge>
      )
    case "active":
      return (
        <Badge variant="info" className="gap-1">
          <Play className="h-3 w-3" />
          Active
        </Badge>
      )
    case "draft":
      return (
        <Badge variant="secondary" className="gap-1">
          <Clock className="h-3 w-3" />
          Draft
        </Badge>
      )
    case "failed":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          Failed
        </Badge>
      )
    default:
      return <Badge variant="secondary">{status}</Badge>
  }
}

export function Workflows({
  workflows,
  agents,
  onRefresh,
  isLoading,
}: WorkflowsProps) {
  const getAgentName = (agentId: string) => {
    const agent = agents.find((a) => a.agent_id === agentId)
    return agent?.name || truncateId(agentId)
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Workflows</h2>
          <p className="text-sm text-muted-foreground">
            Create and manage multi-step agent workflows
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
            <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            Refresh
          </Button>
          <Button disabled>
            <Plus className="h-4 w-4" />
            New Workflow
          </Button>
        </div>
      </div>

      {/* Workflows List */}
      {workflows.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <GitBranch className="h-16 w-16 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No workflows yet</h3>
            <p className="text-muted-foreground text-center mb-4 max-w-md">
              Workflows allow you to chain multiple agents together to complete
              complex tasks. Create your first workflow to get started.
            </p>
            <Button disabled>
              <Plus className="h-4 w-4" />
              Create Workflow
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {workflows.map((workflow) => (
            <Card key={workflow.workflow_id}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle className="text-lg">{workflow.name}</CardTitle>
                    <p className="text-sm text-muted-foreground mt-1">
                      {workflow.description}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {getStatusBadge(workflow.status)}
                    <Button variant="ghost" size="sm">
                      <Play className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Workflow Steps */}
                <div>
                  <h4 className="text-sm font-medium text-muted-foreground mb-3">
                    Steps ({workflow.steps.length})
                  </h4>
                  <div className="flex items-center gap-2 flex-wrap">
                    {workflow.steps
                      .sort((a, b) => a.order - b.order)
                      .map((step, index) => (
                        <div key={step.step_id} className="flex items-center">
                          <div className="flex items-center gap-2 bg-secondary rounded-lg px-3 py-2">
                            <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/20 text-primary text-xs font-medium">
                              {step.order}
                            </div>
                            <span className="text-sm font-medium">
                              {step.name}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {getAgentName(step.agent_id)}
                            </Badge>
                          </div>
                          {index < workflow.steps.length - 1 && (
                            <ArrowRight className="h-4 w-4 mx-2 text-muted-foreground" />
                          )}
                        </div>
                      ))}
                  </div>
                </div>

                {/* Footer */}
                <div className="flex items-center justify-between pt-3 border-t border-border text-sm text-muted-foreground">
                  <span>ID: {truncateId(workflow.workflow_id)}</span>
                  <span>Created {formatRelativeTime(workflow.created_at)}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Coming Soon Notice */}
      <Card className="bg-muted/50">
        <CardContent className="flex items-center justify-center py-8">
          <div className="text-center">
            <p className="text-muted-foreground">
              Workflow editor coming soon. For now, workflows can be created via
              the API.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
