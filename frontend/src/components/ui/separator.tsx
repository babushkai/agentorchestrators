import { type Component, splitProps } from 'solid-js'
import { Separator as KobalteSeparator } from '@kobalte/core/separator'
import { cn } from '@/lib/utils'

interface SeparatorProps {
  class?: string
  orientation?: 'horizontal' | 'vertical'
}

const Separator: Component<SeparatorProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'orientation'])

  return (
    <KobalteSeparator
      orientation={local.orientation}
      class={cn(
        'shrink-0 bg-border',
        local.orientation === 'vertical' ? 'h-full w-px' : 'h-px w-full',
        local.class
      )}
      {...others}
    />
  )
}

export { Separator }
