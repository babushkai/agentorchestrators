import { type Component, For, Show, createSignal, onMount, createEffect } from 'solid-js'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Button,
  Input,
} from '@/components/ui'
import { appStore } from '@/stores/app'
import type { Conversation, Message } from '@/types'
import { cn, formatRelativeTime } from '@/lib/utils'

const ConversationItem: Component<{
  conversation: Conversation
  isSelected: boolean
  onSelect: () => void
}> = (props) => {
  const lastMessage = () => props.conversation.messages[props.conversation.messages.length - 1]

  return (
    <div
      class={cn(
        'p-3 cursor-pointer border-b border-border transition-colors',
        props.isSelected ? 'bg-primary/10' : 'hover:bg-secondary'
      )}
      onClick={props.onSelect}
    >
      <div class="flex items-center justify-between mb-1">
        <span class="font-medium text-sm">{props.conversation.title}</span>
        <span class="text-xs text-muted-foreground">
          {formatRelativeTime(props.conversation.updatedAt)}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs px-2 py-0.5 rounded bg-secondary">{props.conversation.agentName}</span>
        <Show when={lastMessage()}>
          <span class="text-xs text-muted-foreground truncate flex-1">
            {lastMessage().content.slice(0, 50)}...
          </span>
        </Show>
      </div>
    </div>
  )
}

const MessageBubble: Component<{ message: Message }> = (props) => {
  const isUser = () => props.message.role === 'user'

  return (
    <div class={cn('flex', isUser() ? 'justify-end' : 'justify-start')}>
      <div
        class={cn(
          'max-w-[80%] rounded-lg px-4 py-2',
          isUser() ? 'bg-primary text-primary-foreground' : 'bg-secondary'
        )}
      >
        <p class="text-sm whitespace-pre-wrap">{props.message.content}</p>
        <span class="text-[10px] opacity-70 mt-1 block">
          {new Date(props.message.timestamp).toLocaleTimeString()}
        </span>
      </div>
    </div>
  )
}

const ChatPanel: Component<{ conversation: Conversation }> = (props) => {
  const [inputValue, setInputValue] = createSignal('')
  let messagesEndRef: HTMLDivElement | undefined

  createEffect(() => {
    // Scroll to bottom when messages change
    props.conversation.messages
    messagesEndRef?.scrollIntoView({ behavior: 'smooth' })
  })

  const handleSend = () => {
    if (!inputValue().trim()) return
    // TODO: API call to send message
    console.log('Sending message:', inputValue())
    setInputValue('')
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div class="flex flex-col h-full">
      {/* Header */}
      <div class="p-4 border-b border-border shrink-0">
        <h2 class="font-medium">{props.conversation.title}</h2>
        <p class="text-xs text-muted-foreground">with {props.conversation.agentName}</p>
      </div>

      {/* Messages */}
      <div class="flex-1 overflow-auto p-4 space-y-4">
        <For each={props.conversation.messages}>
          {(message) => <MessageBubble message={message} />}
        </For>
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div class="p-4 border-t border-border shrink-0">
        <div class="flex gap-2">
          <Input
            placeholder="Type your message..."
            value={inputValue()}
            onInput={(e) => setInputValue(e.currentTarget.value)}
            onKeyDown={handleKeyDown}
            class="flex-1"
          />
          <Button onClick={handleSend} disabled={!inputValue().trim()}>
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
            </svg>
          </Button>
        </div>
      </div>
    </div>
  )
}

const Conversations: Component = () => {
  const [searchQuery, setSearchQuery] = createSignal('')

  onMount(() => {
    appStore.fetchConversations()
  })

  const filteredConversations = () => {
    return appStore.conversations().filter((conv) =>
      conv.title.toLowerCase().includes(searchQuery().toLowerCase()) ||
      conv.agentName.toLowerCase().includes(searchQuery().toLowerCase())
    )
  }

  return (
    <div class="h-[calc(100vh-8rem)]">
      <div class="flex h-full gap-6">
        {/* Conversations List */}
        <Card class="w-80 shrink-0 flex flex-col">
          <CardHeader class="border-b border-border shrink-0">
            <div class="flex items-center justify-between mb-3">
              <CardTitle>Conversations</CardTitle>
              <Button size="sm">
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
              </Button>
            </div>
            <div class="relative">
              <svg
                class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
              <Input
                type="text"
                placeholder="Search..."
                class="pl-10"
                value={searchQuery()}
                onInput={(e) => setSearchQuery(e.currentTarget.value)}
              />
            </div>
          </CardHeader>
          <CardContent class="p-0 flex-1 overflow-auto">
            <Show
              when={filteredConversations().length > 0}
              fallback={
                <div class="p-4 text-center text-muted-foreground text-sm">
                  No conversations yet
                </div>
              }
            >
              <For each={filteredConversations()}>
                {(conv) => (
                  <ConversationItem
                    conversation={conv}
                    isSelected={appStore.selectedConversation()?.id === conv.id}
                    onSelect={() => appStore.setSelectedConversation(conv)}
                  />
                )}
              </For>
            </Show>
          </CardContent>
        </Card>

        {/* Chat Panel */}
        <Card class="flex-1 flex flex-col">
          <Show
            when={appStore.selectedConversation()}
            fallback={
              <div class="flex-1 flex items-center justify-center">
                <div class="text-center">
                  <svg
                    class="w-16 h-16 mx-auto text-muted-foreground mb-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    stroke-width="1"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
                  </svg>
                  <h3 class="text-lg font-medium mb-1">Select a conversation</h3>
                  <p class="text-sm text-muted-foreground">
                    Choose a conversation from the list or start a new one
                  </p>
                </div>
              </div>
            }
          >
            <ChatPanel conversation={appStore.selectedConversation()!} />
          </Show>
        </Card>
      </div>
    </div>
  )
}

export { Conversations }
