import { type Component, type JSX, splitProps } from 'solid-js'
import { Tabs as KobalteTabs } from '@kobalte/core/tabs'
import { cn } from '@/lib/utils'

const Tabs = KobalteTabs

const TabsList: Component<{ class?: string; children: JSX.Element }> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <KobalteTabs.List
      class={cn(
        'inline-flex h-9 items-center justify-center rounded-lg bg-secondary p-1 text-muted-foreground',
        local.class
      )}
      {...others}
    >
      {local.children}
      <KobalteTabs.Indicator class="absolute h-full bg-card rounded-md shadow-sm transition-all duration-200" />
    </KobalteTabs.List>
  )
}

const TabsTrigger: Component<{ class?: string; value: string; children: JSX.Element }> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <KobalteTabs.Trigger
      class={cn(
        'relative z-10 inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium transition-all',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        'disabled:pointer-events-none disabled:opacity-50',
        'data-[selected]:text-foreground',
        local.class
      )}
      {...others}
    >
      {local.children}
    </KobalteTabs.Trigger>
  )
}

const TabsContent: Component<{ class?: string; value: string; children: JSX.Element }> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <KobalteTabs.Content
      class={cn(
        'mt-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        local.class
      )}
      {...others}
    >
      {local.children}
    </KobalteTabs.Content>
  )
}

export { Tabs, TabsList, TabsTrigger, TabsContent }
