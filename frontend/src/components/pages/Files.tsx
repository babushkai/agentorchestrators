import { useState, useRef } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
  RefreshCw,
  Folder,
  ChevronRight,
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
    return <Image className="h-5 w-5" />
  }
  if (contentType.includes("spreadsheet") || contentType === "text/csv") {
    return <FileSpreadsheet className="h-5 w-5" />
  }
  if (
    contentType.includes("document") ||
    contentType === "application/pdf" ||
    contentType.startsWith("text/")
  ) {
    return <FileText className="h-5 w-5" />
  }
  return <File className="h-5 w-5" />
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

export function Files({ tasks, sessions, onRefresh, isLoading }: FilesProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("tasks")
  const [selectedContext, setSelectedContext] = useState<SelectedContext>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  // Query files based on selected context
  const { data: filesData, isLoading: filesLoading } = useQuery({
    queryKey: [
      "files",
      selectedContext?.type,
      selectedContext?.id,
    ],
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
    e.target.value = "" // Reset input
  }

  const handleDownload = (file: FileMetadata) => {
    const url = api.getFileDownloadUrl(file.file_id)
    const a = document.createElement("a")
    a.href = url
    a.download = file.original_filename
    a.click()
  }

  const handleDelete = (fileId: string) => {
    if (confirm("Are you sure you want to delete this file?")) {
      deleteMutation.mutate(fileId)
    }
  }

  // Render the context selector (tasks or sessions list)
  const renderContextSelector = () => {
    const items = viewMode === "tasks" ? tasks : sessions

    return (
      <div className="space-y-4">
        {/* View Mode Tabs */}
        <div className="flex gap-2">
          <Button
            variant={viewMode === "tasks" ? "default" : "outline"}
            onClick={() => {
              setViewMode("tasks")
              setSelectedContext(null)
            }}
          >
            <Folder className="h-4 w-4" />
            Tasks ({tasks.length})
          </Button>
          <Button
            variant={viewMode === "sessions" ? "default" : "outline"}
            onClick={() => {
              setViewMode("sessions")
              setSelectedContext(null)
            }}
          >
            <Folder className="h-4 w-4" />
            Conversations ({sessions.length})
          </Button>
        </div>

        {/* Items List */}
        <Card>
          <CardHeader>
            <CardTitle>
              Select {viewMode === "tasks" ? "Task" : "Conversation"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {items.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Folder className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>
                  No {viewMode === "tasks" ? "tasks" : "conversations"} yet
                </p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {viewMode === "tasks"
                  ? (items as Task[]).map((task) => (
                      <button
                        key={task.task_id}
                        className="w-full flex items-center justify-between p-3 hover:bg-accent transition-colors text-left"
                        onClick={() =>
                          setSelectedContext({
                            type: "task",
                            id: task.task_id,
                            name: task.name,
                          })
                        }
                      >
                        <div>
                          <p className="font-medium">{task.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {truncateId(task.task_id)}
                          </p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </button>
                    ))
                  : (items as Session[]).map((session) => (
                      <button
                        key={session.session_id}
                        className="w-full flex items-center justify-between p-3 hover:bg-accent transition-colors text-left"
                        onClick={() =>
                          setSelectedContext({
                            type: "session",
                            id: session.session_id,
                            name: session.title || "Untitled",
                          })
                        }
                      >
                        <div>
                          <p className="font-medium">
                            {session.title || "Untitled"}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {truncateId(session.session_id)}
                          </p>
                        </div>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </button>
                    ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  // Render the files view for selected context
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
          >
            <ChevronRight className="h-4 w-4 rotate-180" />
            Back
          </Button>
          <span className="text-muted-foreground">/</span>
          <span className="font-medium">{selectedContext.name}</span>
        </div>

        {/* Upload Area */}
        <Card>
          <CardContent className="pt-6">
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                uploadMutation.isPending
                  ? "border-primary bg-primary/5"
                  : "border-border hover:border-primary/50 hover:bg-accent/50"
              )}
              onClick={() => fileInputRef.current?.click()}
              style={{ cursor: "pointer" }}
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
                  <RefreshCw className="h-12 w-12 mx-auto mb-3 text-primary animate-spin" />
                  <p className="font-medium">Uploading...</p>
                </>
              ) : (
                <>
                  <Upload className="h-12 w-12 mx-auto mb-3 text-muted-foreground" />
                  <p className="font-medium">
                    Click to upload or drag and drop
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    PDF, Word, Excel, CSV, images, and more (max 50MB)
                  </p>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Files List */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>Files ({files.length})</span>
              {filesLoading && (
                <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {files.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <File className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>No files uploaded yet</p>
              </div>
            ) : (
              <div className="divide-y divide-border">
                {files.map((file) => (
                  <div
                    key={file.file_id}
                    className="flex items-center justify-between py-3"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-secondary">
                        {getFileIcon(file.content_type)}
                      </div>
                      <div>
                        <p className="font-medium">{file.original_filename}</p>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>{formatFileSize(file.size_bytes)}</span>
                          <span>-</span>
                          <span>{formatRelativeTime(file.created_at)}</span>
                          <Badge variant="outline" className="text-xs">
                            {file.parse_status}
                          </Badge>
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownload(file)}
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-destructive hover:text-destructive"
                        onClick={() => handleDelete(file.file_id)}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Files</h2>
          <p className="text-sm text-muted-foreground">
            Upload and manage files for tasks and conversations
          </p>
        </div>
        <Button variant="outline" onClick={onRefresh} disabled={isLoading}>
          <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
          Refresh
        </Button>
      </div>

      {/* Content */}
      {selectedContext ? renderFilesView() : renderContextSelector()}
    </div>
  )
}
