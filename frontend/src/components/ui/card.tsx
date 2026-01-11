import { type Component, type JSX, splitProps } from 'solid-js'
import { cn } from '@/lib/utils'

interface CardProps extends JSX.HTMLAttributes<HTMLDivElement> {}

const Card: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div
      class={cn('rounded-lg border border-border bg-card text-card-foreground', local.class)}
      {...others}
    >
      {local.children}
    </div>
  )
}

const CardHeader: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div class={cn('flex flex-col space-y-1 p-4', local.class)} {...others}>
      {local.children}
    </div>
  )
}

const CardTitle: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div class={cn('text-sm font-medium leading-none', local.class)} {...others}>
      {local.children}
    </div>
  )
}

const CardDescription: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div class={cn('text-xs text-muted-foreground', local.class)} {...others}>
      {local.children}
    </div>
  )
}

const CardContent: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div class={cn('p-4 pt-0', local.class)} {...others}>
      {local.children}
    </div>
  )
}

const CardFooter: Component<CardProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])
  return (
    <div class={cn('flex items-center p-4 pt-0', local.class)} {...others}>
      {local.children}
    </div>
  )
}

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
