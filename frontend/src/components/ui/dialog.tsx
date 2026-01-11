import { type Component, type JSX, splitProps } from 'solid-js'
import { Dialog as KobalteDialog } from '@kobalte/core/dialog'
import { cn } from '@/lib/utils'

const Dialog = KobalteDialog

const DialogTrigger = KobalteDialog.Trigger

const DialogPortal = KobalteDialog.Portal

const DialogOverlay: Component<{ class?: string }> = (props) => {
  return (
    <KobalteDialog.Overlay
      class={cn(
        'fixed inset-0 z-50 bg-black/60 backdrop-blur-sm',
        'data-[expanded]:animate-fade-in',
        props.class
      )}
    />
  )
}

interface DialogContentProps {
  class?: string
  children: JSX.Element
}

const DialogContent: Component<DialogContentProps> = (props) => {
  const [local, others] = splitProps(props, ['class', 'children'])

  return (
    <DialogPortal>
      <DialogOverlay />
      <KobalteDialog.Content
        class={cn(
          'fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2',
          'rounded-lg border border-border bg-card p-6 shadow-xl',
          'data-[expanded]:animate-fade-in',
          local.class
        )}
        {...others}
      >
        {local.children}
      </KobalteDialog.Content>
    </DialogPortal>
  )
}

const DialogHeader: Component<{ class?: string; children: JSX.Element }> = (props) => {
  return (
    <div class={cn('flex flex-col space-y-1.5 text-left', props.class)}>
      {props.children}
    </div>
  )
}

const DialogFooter: Component<{ class?: string; children: JSX.Element }> = (props) => {
  return (
    <div class={cn('flex flex-col-reverse gap-2 sm:flex-row sm:justify-end', props.class)}>
      {props.children}
    </div>
  )
}

const DialogTitle: Component<{ class?: string; children: JSX.Element }> = (props) => {
  return (
    <KobalteDialog.Title
      class={cn('text-lg font-semibold leading-none tracking-tight', props.class)}
    >
      {props.children}
    </KobalteDialog.Title>
  )
}

const DialogDescription: Component<{ class?: string; children: JSX.Element }> = (props) => {
  return (
    <KobalteDialog.Description class={cn('text-sm text-muted-foreground', props.class)}>
      {props.children}
    </KobalteDialog.Description>
  )
}

const DialogCloseButton = KobalteDialog.CloseButton

export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogCloseButton,
}
