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
  ChevronLeft,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center animate-fade-in">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <Card className="relative z-10 w-full max-w-md mx-4 animate-slide-in-right">
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <CardTitle>New Conversation</CardTitle>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Name</label>
              <Input
                placeholder="e.g., Research project discussion"
                value={formData.name}
                onChange={(e) =>
                  setFormData({ ...formData, name: e.target.value })
                }
                required
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground">Select Agent</label>
              {agents.length === 0 ? (
                <p className="text-sm text-muted-foreground py-4 text-center">
                  No agents available. Create an agent first.
                </p>
              ) : (
                <div className="space-y-2 max-h-[240px] overflow-y-auto">
                  {agents.map((agent) => (
                    <button
                      key={agent.agent_id}
                      type="button"
                      className={cn(
                        "flex items-center gap-3 w-full p-3 rounded-md border text-left transition-colors duration-150",
                        formData.agent_id === agent.agent_id
                          ? "border-primary bg-primary/5"
                          : "border-border hover:bg-secondary/50"
                      )}
                      onClick={() =>
                        setFormData({ ...formData, agent_id: agent.agent_id })
                      }
                    >
                      <div className="p-2 rounded-md bg-secondary">
                        <Bot className="h-4 w-4 text-muted-foreground" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-sm">{agent.name}</p>
                        <p className="text-xs text-muted-foreground truncate">
                          {agent.role}
                        </p>
                      </div>
                      <Badge
                        variant={agent.status === "idle" ? "idle" : agent.status === "running" ? "running" : "secondary"}
                      >
                        {agent.status}
                      </Badge>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={isSubmitting || !formData.agent_id}
              >
                {isSubmitting ? "Starting..." : "Start Chat"}
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
    refetchInterval: 3000,
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
      <div className="flex items-center gap-3 p-4 border-b border-border">
        <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8">
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-sm truncate">
            {session.title || "Conversation"}
          </h3>
          <p className="text-xs text-muted-foreground">
            {session.message_count} messages
          </p>
        </div>
        <Badge variant={session.status === "active" ? "idle" : "secondary"}>
          {session.status}
        </Badge>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {historyLoading ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
            <MessageSquare className="h-10 w-10 mb-3 opacity-30" />
            <p className="text-sm">No messages yet</p>
            <p className="text-xs mt-1">Start the conversation below</p>
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
                  "p-2 rounded-md shrink-0",
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
                  "flex flex-col max-w-[75%]",
                  message.role === "user" && "items-end"
                )}
              >
                <div
                  className={cn(
                    "rounded-md px-3 py-2",
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
                        className="flex items-center gap-1.5 text-xs text-muted-foreground"
                      >
                        <Wrench className="h-3 w-3" />
                        <span className="font-mono">{tc.function.name}</span>
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
            placeholder="Type a message..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={sendMutation.isPending || session.status !== "active"}
            className="flex-1"
          />
          <Button
            type="submit"
            size="icon"
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
  isLoading: _isLoading,
}: ConversationsProps) {
  void _isLoading
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
      <Card className="h-[calc(100vh-8rem)] animate-fade-in">
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
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium">Conversations</h1>
          <p className="text-sm text-muted-foreground">
            {sessions.length} conversation{sessions.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} size="sm">
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      {/* Sessions List */}
      {sessions.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <MessageSquare className="h-10 w-10 text-muted-foreground/30 mb-3" />
            <p className="text-sm text-muted-foreground mb-4">No conversations yet</p>
            <Button onClick={() => setShowCreateModal(true)} size="sm">
              <Plus className="h-4 w-4" />
              Start Chat
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {sessions.map((session) => {
            const agent = agents.find((a) => a.agent_id === session.agent_id)
            return (
              <Card
                key={session.session_id}
                className="hover:bg-secondary/30 transition-colors duration-150 cursor-pointer"
                onClick={() => setSelectedSession(session)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <div className="p-2 rounded-md bg-secondary">
                      <MessageSquare className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">
                          {session.title || "Untitled"}
                        </span>
                        <Badge
                          variant={session.status === "active" ? "idle" : "secondary"}
                        >
                          {session.status}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="text-xs text-muted-foreground">
                          with {agent?.name || "Unknown Agent"}
                        </span>
                        <span className="text-xs text-muted-foreground">·</span>
                        <span className="text-xs text-muted-foreground">
                          {session.message_count} messages
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatRelativeTime(session.last_activity_at)}
                    </span>
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
