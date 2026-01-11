import { type Component, createSignal } from 'solid-js'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
  Button,
  Input,
  Separator,
} from '@/components/ui'

const Settings: Component = () => {
  const [apiEndpoint, setApiEndpoint] = createSignal('http://localhost:8000')
  const [apiKey, setApiKey] = createSignal('')
  const [defaultModel, setDefaultModel] = createSignal('gpt-4')
  const [maxConcurrentTasks, setMaxConcurrentTasks] = createSignal(5)

  const handleSave = () => {
    // TODO: Save settings
    console.log('Saving settings:', {
      apiEndpoint: apiEndpoint(),
      apiKey: apiKey(),
      defaultModel: defaultModel(),
      maxConcurrentTasks: maxConcurrentTasks(),
    })
  }

  return (
    <div class="space-y-6 max-w-2xl">
      <div>
        <h1 class="text-2xl font-semibold text-foreground">Settings</h1>
        <p class="text-muted-foreground text-sm mt-1">Configure your agent orchestration system</p>
      </div>

      {/* API Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>API Configuration</CardTitle>
          <CardDescription>Configure the backend API connection</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <label class="text-sm font-medium">API Endpoint</label>
            <Input
              placeholder="http://localhost:8000"
              value={apiEndpoint()}
              onInput={(e) => setApiEndpoint(e.currentTarget.value)}
            />
            <p class="text-xs text-muted-foreground">The base URL for the orchestrator API</p>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium">API Key</label>
            <Input
              type="password"
              placeholder="Enter your API key"
              value={apiKey()}
              onInput={(e) => setApiKey(e.currentTarget.value)}
            />
            <p class="text-xs text-muted-foreground">Optional authentication key for the API</p>
          </div>
        </CardContent>
      </Card>

      {/* Agent Defaults */}
      <Card>
        <CardHeader>
          <CardTitle>Agent Defaults</CardTitle>
          <CardDescription>Default settings for new agents</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-2">
            <label class="text-sm font-medium">Default Model</label>
            <select
              class="flex h-9 w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              value={defaultModel()}
              onChange={(e) => setDefaultModel(e.currentTarget.value)}
            >
              <option value="gpt-4">GPT-4</option>
              <option value="gpt-4-turbo">GPT-4 Turbo</option>
              <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
              <option value="claude-3-opus">Claude 3 Opus</option>
              <option value="claude-3-sonnet">Claude 3 Sonnet</option>
              <option value="claude-3-haiku">Claude 3 Haiku</option>
            </select>
            <p class="text-xs text-muted-foreground">The default LLM model for new agents</p>
          </div>
          <div class="space-y-2">
            <label class="text-sm font-medium">Max Concurrent Tasks</label>
            <Input
              type="number"
              min="1"
              max="50"
              value={maxConcurrentTasks()}
              onInput={(e) => setMaxConcurrentTasks(parseInt(e.currentTarget.value) || 1)}
            />
            <p class="text-xs text-muted-foreground">Maximum number of tasks that can run simultaneously</p>
          </div>
        </CardContent>
      </Card>

      {/* Appearance */}
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Customize the interface appearance</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium">Theme</p>
              <p class="text-xs text-muted-foreground">Currently using dark theme</p>
            </div>
            <Button variant="outline" size="sm" disabled>
              Dark (Default)
            </Button>
          </div>
          <Separator />
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium">Compact Mode</p>
              <p class="text-xs text-muted-foreground">Reduce padding and spacing</p>
            </div>
            <Button variant="outline" size="sm">
              Disabled
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card class="border-destructive/50">
        <CardHeader>
          <CardTitle class="text-destructive">Danger Zone</CardTitle>
          <CardDescription>Irreversible actions</CardDescription>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="flex items-center justify-between">
            <div>
              <p class="text-sm font-medium">Clear All Data</p>
              <p class="text-xs text-muted-foreground">Delete all agents, tasks, and conversations</p>
            </div>
            <Button variant="destructive" size="sm">
              Clear Data
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Save Button */}
      <div class="flex justify-end">
        <Button onClick={handleSave}>Save Settings</Button>
      </div>
    </div>
  )
}

export { Settings }
