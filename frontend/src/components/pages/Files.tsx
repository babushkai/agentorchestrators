import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn, formatRelativeTime, truncateId } from "@/lib/utils"
import {
  File,
  FileText,
  Image,
  FileSpreadsheet,
  Upload,
  Download,
  Trash2,
  Loader2,
  Folder,
  ChevronLeft,
  ListTodo,
  MessageSquare,
} from "lucide-react"
import type { Task, Session, FileMetadata } from "@/types/api"
import * as api from "@/api/client"

interface FilesProps {
  tasks: Task[]
  sessions: Session[]
  onRefresh: () => void
  isLoading: boolean
}

const getFileIcon = (contentType: string) => {
  if (contentType.startsWith("image/")) {
    return <Image className="h-4 w-4" />
  }
  if (contentType.includes("spreadsheet") || contentType === "text/csv") {
    return <FileSpreadsheet className="h-4 w-4" />
  }
  if (
    contentType.includes("document") ||
    contentType === "application/pdf" ||
    contentType.startsWith("text/")
  ) {
    return <FileText className="h-4 w-4" />
  }
  return <File className="h-4 w-4" />
}

const formatFileSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

type ViewMode = "tasks" | "sessions"
type SelectedContext =
  | { type: "task"; id: string; name: string }
  | { type: "session"; id: string; name: string }
  | null

export function Files({ tasks, sessions, onRefresh: _onRefresh, isLoading: _isLoading }: FilesProps) {
  void _onRefresh
  void _isLoading
  const [viewMode, setViewMode] = useState<ViewMode>("tasks")
  const [selectedContext, setSelectedContext] = useState<SelectedContext>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  // Query files based on selected context
  const { data: filesData, isLoading: filesLoading } = useQuery({
    queryKey: ["files", selectedContext?.type, selectedContext?.id],
    queryFn: () => {
      if (!selectedContext) return Promise.resolve({ files: [], count: 0 })
      if (selectedContext.type === "task") {
        return api.getTaskFiles(selectedContext.id)
      }
      return api.getSessionFiles(selectedContext.id)
    },
    enabled: !!selectedContext,
  })

  const files = filesData?.files || []

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      if (!selectedContext) throw new Error("No context selected")
      if (selectedContext.type === "task") {
        return api.uploadTaskFile(selectedContext.id, file)
      }
      return api.uploadSessionFile(selectedContext.id, file)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["files", selectedContext?.type, selectedContext?.id],
      })
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: api.deleteFile,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["files", selectedContext?.type, selectedContext?.id],
      })
    },
  })

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      uploadMutation.mutate(file)
    }
    e.target.value = ""
  }

  const handleDownload = (file: FileMetadata) => {
    const url = api.getFileDownloadUrl(file.file_id)
    const a = document.createElement("a")
    a.href = url
    a.download = file.original_filename
    a.click()
  }

  const handleDelete = (fileId: string) => {
    if (confirm("Delete this file?")) {
      deleteMutation.mutate(fileId)
    }
  }

  // Render the context selector
  const renderContextSelector = () => {
    const items = viewMode === "tasks" ? tasks : sessions

    return (
      <div className="space-y-4">
        {/* View Mode Tabs */}
        <div className="flex gap-1">
          <Button
            variant={viewMode === "tasks" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => {
              setViewMode("tasks")
              setSelectedContext(null)
            }}
          >
            <ListTodo className="h-4 w-4" />
            Tasks
            <span className="ml-1 text-muted-foreground">({tasks.length})</span>
          </Button>
          <Button
            variant={viewMode === "sessions" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => {
              setViewMode("sessions")
              setSelectedContext(null)
            }}
          >
            <MessageSquare className="h-4 w-4" />
            Conversations
            <span className="ml-1 text-muted-foreground">({sessions.length})</span>
          </Button>
        </div>

        {/* Items List */}
        {items.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-12">
              <Folder className="h-10 w-10 text-muted-foreground/30 mb-3" />
              <p className="text-sm text-muted-foreground">
                No {viewMode === "tasks" ? "tasks" : "conversations"} yet
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {viewMode === "tasks"
              ? (items as Task[]).map((task) => (
                  <Card
                    key={task.task_id}
                    className="hover:bg-secondary/30 transition-colors duration-150 cursor-pointer"
                    onClick={() =>
                      setSelectedContext({
                        type: "task",
                        id: task.task_id,
                        name: task.name,
                      })
                    }
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        <div className="p-2 rounded-md bg-secondary">
                          <Folder className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-sm">{task.name}</span>
                          <p className="text-xs text-muted-foreground font-mono mt-0.5">
                            {truncateId(task.task_id)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              : (items as Session[]).map((session) => (
                  <Card
                    key={session.session_id}
                    className="hover:bg-secondary/30 transition-colors duration-150 cursor-pointer"
                    onClick={() =>
                      setSelectedContext({
                        type: "session",
                        id: session.session_id,
                        name: session.title || "Untitled",
                      })
                    }
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        <div className="p-2 rounded-md bg-secondary">
                          <Folder className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="font-medium text-sm">
                            {session.title || "Untitled"}
                          </span>
                          <p className="text-xs text-muted-foreground font-mono mt-0.5">
                            {truncateId(session.session_id)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
          </div>
        )}
      </div>
    )
  }

  // Render the files view
  const renderFilesView = () => {
    if (!selectedContext) return null

    return (
      <div className="space-y-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSelectedContext(null)}
            className="h-8"
          >
            <ChevronLeft className="h-4 w-4" />
            Back
          </Button>
          <span className="text-muted-foreground">/</span>
          <span className="text-sm font-medium">{selectedContext.name}</span>
        </div>

        {/* Upload Area */}
        <div
          className={cn(
            "border border-dashed rounded-md p-8 text-center transition-colors duration-150 cursor-pointer",
            uploadMutation.isPending
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50 hover:bg-secondary/30"
          )}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={handleFileUpload}
            disabled={uploadMutation.isPending}
          />
          {uploadMutation.isPending ? (
            <>
              <Loader2 className="h-8 w-8 mx-auto mb-2 text-primary animate-spin" />
              <p className="text-sm font-medium">Uploading...</p>
            </>
          ) : (
            <>
              <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
              <p className="text-sm font-medium">Click to upload</p>
              <p className="text-xs text-muted-foreground mt-1">
                PDF, Word, Excel, CSV, images (max 50MB)
              </p>
            </>
          )}
        </div>

        {/* Files List */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">
              Files
              <span className="text-muted-foreground ml-1">({files.length})</span>
            </h3>
            {filesLoading && (
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            )}
          </div>

          {files.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-8">
                <File className="h-8 w-8 text-muted-foreground/30 mb-2" />
                <p className="text-sm text-muted-foreground">No files uploaded</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {files.map((file) => (
                <Card
                  key={file.file_id}
                  className="hover:bg-secondary/30 transition-colors duration-150"
                >
                  <CardContent className="p-4">
                    <div className="flex items-center gap-4">
                      <div className="p-2 rounded-md bg-secondary">
                        {getFileIcon(file.content_type)}
                      </div>
                      <div className="flex-1 min-w-0">
                        <span className="font-medium text-sm">
                          {file.original_filename}
                        </span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground">
                            {formatFileSize(file.size_bytes)}
                          </span>
                          <span className="text-xs text-muted-foreground">·</span>
                          <span className="text-xs text-muted-foreground">
                            {formatRelativeTime(file.created_at)}
                          </span>
                          <Badge variant="outline" className="text-[10px] px-1 py-0">
                            {file.parse_status}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => handleDownload(file)}
                        >
                          <Download className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDelete(file.file_id)}
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
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-medium">Files</h1>
          <p className="text-sm text-muted-foreground">
            Upload and manage attachments
          </p>
        </div>
      </div>

      {/* Content */}
      {selectedContext ? renderFilesView() : renderContextSelector()}
    </div>
  )
}
