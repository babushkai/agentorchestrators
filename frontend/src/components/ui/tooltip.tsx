import { type Component, type JSX, splitProps } from 'solid-js'
import { Tooltip as KobalteTooltip } from '@kobalte/core/tooltip'
import { cn } from '@/lib/utils'

const Tooltip = KobalteTooltip

const TooltipTrigger = KobalteTooltip.Trigger

interface TooltipContentProps {
  class?: string
  children: JSX.Element
}

const TooltipContent: Component<TooltipContentProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])

  return (
    <KobalteTooltip.Portal>
      <KobalteTooltip.Content
        class={cn(
          'z-50 overflow-hidden rounded-md bg-popover px-3 py-1.5 text-xs text-popover-foreground shadow-md border border-border',
          'animate-fade-in',
          local.class
        )}
        {...others}
      >
        <KobalteTooltip.Arrow />
        {local.children}
      </KobalteTooltip.Content>
    </KobalteTooltip.Portal>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent }
