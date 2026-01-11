import { useState, useRef, useEffect } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn, formatRelativeTime } from "@/lib/utils"
import {
  MessageSquare,
  Plus,
  Send,
  Bot,
  User,
  Loader2,
  X,
  ChevronRight,
  Wrench,
} from "lucide-react"
import type { Agent, Session, SessionCreate } from "@/types/api"
import * as api from "@/api/client"

interface ConversationsProps {
  sessions: Session[]
  agents: Agent[]
  onRefresh: () => void
  isLoading: boolean
}

interface CreateSessionModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: SessionCreate) => void
  isSubmitting: boolean
  agents: Agent[]
}

function CreateSessionModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  agents,
}: CreateSessionModalProps) {
  const [formData, setFormData] = useState<SessionCreate>({
    name: "",
    agent_id: "",
  })

  if (!isOpen) return null

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.agent_id) return
    onSubmit(formData)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-md mx-4">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>New Conversation</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Conversation Name</label>
              <Input
                placeholder="e.g., Research project discussion"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Select Agent</label>
              {agents.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No agents available. Create an agent first.
                </p>
              ) : (
                <div className="grid gap-2">
                  {agents.map((agent) => (
                    <button
                      key={agent.agent_id}
                      type="button"
                      className={cn(
                        "flex items-center gap-3 p-3 rounded-lg border text-left transition-colors",
                        formData.agent_id === agent.agent_id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-accent"
                      )}
                      onClick={() =>
                        setFormData({ ...formData, agent_id: agent.agent_id })
                      }
                    >
                      <div className="p-2 rounded-lg bg-secondary">
                        <Bot className="h-4 w-4" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium text-sm">{agent.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {agent.role}
                        </p>
                      </div>
                      <Badge
                        variant={agent.status === "idle" ? "success" : "info"}
                      >
                        {agent.status}
                      </Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-4">
              <Button type="button" variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || !formData.agent_id}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4" />
                    Start Conversation
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

interface ChatViewProps {
  session: Session
  onClose: () => void
}

function ChatView({ session, onClose }: ChatViewProps) {
  const [inputValue, setInputValue] = useState("")
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  // Fetch message history
  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ["session-history", session.session_id],
    queryFn: () => api.getSessionHistory(session.session_id, 100),
    refetchInterval: 3000, // Poll for new messages
  })

  const messages = historyData?.messages || []

  // Send message mutation
  const sendMutation = useMutation({
    mutationFn: (content: string) =>
      api.sendMessage(session.session_id, content),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["session-history", session.session_id],
      })
      setInputValue("")
    },
  })

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || sendMutation.isPending) return
    sendMutation.mutate(inputValue.trim())
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={onClose}>
            <ChevronRight className="h-4 w-4 rotate-180" />
          </Button>
          <div>
            <h3 className="font-medium">
              {session.title || "Conversation"}
            </h3>
            <p className="text-xs text-muted-foreground">
              {session.message_count} messages
            </p>
          </div>
        </div>
        <Badge variant={session.status === "active" ? "success" : "secondary"}>
          {session.status}
        </Badge>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {historyLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
            <p>No messages yet</p>
            <p className="text-sm">Start the conversation below</p>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.message_id}
              className={cn(
                "flex gap-3",
                message.role === "user" && "flex-row-reverse"
              )}
            >
              <div
                className={cn(
                  "p-2 rounded-full shrink-0",
                  message.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary"
                )}
              >
                {message.role === "user" ? (
                  <User className="h-4 w-4" />
                ) : (
                  <Bot className="h-4 w-4" />
                )}
              </div>
              <div
                className={cn(
                  "flex flex-col max-w-[80%]",
                  message.role === "user" && "items-end"
                )}
              >
                <div
                  className={cn(
                    "rounded-lg px-4 py-2",
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary"
                  )}
                >
                  <p className="text-sm whitespace-pre-wrap">
                    {message.content}
                  </p>
                </div>
                {message.tool_calls && message.tool_calls.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {message.tool_calls.map((tc) => (
                      <div
                        key={tc.id}
                        className="flex items-center gap-2 text-xs text-muted-foreground"
                      >
                        <Wrench className="h-3 w-3" />
                        <span>
                          Called: <code>{tc.function.name}</code>
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <span className="text-xs text-muted-foreground mt-1">
                  {formatRelativeTime(message.timestamp)}
                </span>
              </div>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-border">
        <form onSubmit={handleSend} className="flex gap-2">
          <Input
            placeholder="Type your message..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={sendMutation.isPending || session.status !== "active"}
            className="flex-1"
          />
          <Button
            type="submit"
            disabled={
              !inputValue.trim() ||
              sendMutation.isPending ||
              session.status !== "active"
            }
          >
            {sendMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </form>
        {session.status !== "active" && (
          <p className="text-xs text-muted-foreground mt-2 text-center">
            This conversation is closed
          </p>
        )}
      </div>
    </div>
  )
}

export function Conversations({
  sessions,
  agents,
  onRefresh,
  isLoading,
}: ConversationsProps) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedSession, setSelectedSession] = useState<Session | null>(null)
  const queryClient = useQueryClient()

  const createMutation = useMutation({
    mutationFn: api.createSession,
    onSuccess: (newSession) => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] })
      setShowCreateModal(false)
      setSelectedSession(newSession)
    },
  })

  // If a session is selected, show the chat view
  if (selectedSession) {
    return (
      <Card className="h-[calc(100vh-8rem)]">
        <ChatView
          session={selectedSession}
          onClose={() => {
            setSelectedSession(null)
            onRefresh()
          }}
        />
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Conversations</h2>
          <p className="text-sm text-muted-foreground">
            Chat with your AI agents
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
            <Loader2
              className={cn("h-4 w-4", isLoading && "animate-spin")}
            />
            Refresh
          </Button>
          <Button onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>
      </div>

      {/* Sessions List */}
      {sessions.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <MessageSquare className="h-16 w-16 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-medium mb-2">No conversations yet</h3>
            <p className="text-muted-foreground text-center mb-4">
              Start a new conversation with an agent
            </p>
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="h-4 w-4" />
              Start Conversation
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sessions.map((session) => {
            const agent = agents.find((a) => a.agent_id === session.agent_id)
            return (
              <Card
                key={session.session_id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => setSelectedSession(session)}
              >
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10">
                        <MessageSquare className="h-5 w-5 text-primary" />
                      </div>
                      <div>
                        <CardTitle className="text-base">
                          {session.title || "Untitled"}
                        </CardTitle>
                        <p className="text-xs text-muted-foreground">
                          with {agent?.name || "Unknown Agent"}
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant={
                        session.status === "active" ? "success" : "secondary"
                      }
                    >
                      {session.status}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between text-sm text-muted-foreground">
                    <span>{session.message_count} messages</span>
                    <span>{formatRelativeTime(session.last_activity_at)}</span>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}

      {/* Create Modal */}
      <CreateSessionModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSubmit={(data) => createMutation.mutate(data)}
        isSubmitting={createMutation.isPending}
        agents={agents}
      />
    </div>
  )
}
