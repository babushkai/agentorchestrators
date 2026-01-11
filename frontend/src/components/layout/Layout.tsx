import { type ParentComponent, onMount, onCleanup } from 'solid-js'
import { useNavigate } from '@solidjs/router'
import { Header } from './Header'
import { Sidebar } from './Sidebar'
import { appStore } from '@/stores/app'

const Layout: ParentComponent = (props) => {
  const navigate = useNavigate()

  // Health check polling
  onMount(() => {
    appStore.checkHealth()
    const interval = setInterval(appStore.checkHealth, 10000)
    onCleanup(() => clearInterval(interval))
  })

  // Keyboard shortcuts
  onMount(() => {
    let gPressed = false
    let gTimeout: number | undefined

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

      // Command palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        appStore.setIsCommandPaletteOpen(true)
        return
      }

      // Navigation shortcuts (g + key)
      if (e.key === 'g' && !gPressed) {
        gPressed = true
        gTimeout = window.setTimeout(() => {
          gPressed = false
        }, 500)
        return
      }

      if (gPressed) {
        gPressed = false
        if (gTimeout) clearTimeout(gTimeout)

        const shortcuts: Record<string, string> = {
          d: '/',
          a: '/agents',
          t: '/tasks',
          w: '/workflows',
          c: '/conversations',
          m: '/monitoring',
          s: '/settings',
        }

        if (shortcuts[e.key]) {
          e.preventDefault()
          navigate(shortcuts[e.key])
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    onCleanup(() => window.removeEventListener('keydown', handleKeyDown))
  })

  return (
    <div class="min-h-screen bg-background flex flex-col">
      <Header />
      <div class="flex flex-1 overflow-hidden">
        <Sidebar />
        <main class="flex-1 overflow-auto p-6">
          {props.children}
        </main>
      </div>
    </div>
  )
}

export { Layout }
