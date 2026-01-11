import { type Component, type JSX, splitProps } from 'solid-js'
import { cn } from '@/lib/utils'

interface InputProps extends JSX.InputHTMLAttributes<HTMLInputElement> {}

const Input: Component<InputProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'type'])

  return (
    <input
      type={local.type}
      class={cn(
        'flex h-9 w-full rounded-md border border-border bg-input px-3 py-2 text-sm text-foreground transition-colors duration-150',
        'placeholder:text-muted-foreground',
        'hover:border-border-hover',
        'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background focus:border-transparent',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'file:border-0 file:bg-transparent file:text-sm file:font-medium',
        local.class
      )}
      {...others}
    />
  )
}

export { Input }
