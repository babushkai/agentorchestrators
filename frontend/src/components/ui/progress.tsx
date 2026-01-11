import { type Component, splitProps } from 'solid-js'
import { Progress as KobalteProgress } from '@kobalte/core/progress'
import { cn } from '@/lib/utils'

interface ProgressProps {
  value: number
  max?: number
  class?: string
  indicatorClass?: string
}

const Progress: Component<ProgressProps> = (props) => {
  const [local, others] = splitProps(props, ['value', 'max', 'class', 'indicatorClass'])

  return (
    <KobalteProgress value={local.value} minValue={0} maxValue={local.max ?? 100} {...others}>
      <KobalteProgress.Track
        class={cn('relative h-2 w-full overflow-hidden rounded-full bg-secondary', local.class)}
      >
        <KobalteProgress.Fill
          class={cn(
            'h-full bg-primary transition-all duration-300',
            local.indicatorClass
          )}
          style={{ width: `${(local.value / (local.max ?? 100)) * 100}%` }}
        />
      </KobalteProgress.Track>
    </KobalteProgress>
  )
}

export { Progress }
