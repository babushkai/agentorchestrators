import { type Component } from 'solid-js'
import { type RouteSectionProps } from '@solidjs/router'
import { Layout } from '@/components/layout'

// App wrapper - used as Router root
const App: Component<RouteSectionProps> = (props) => {
  return <Layout>{props.children}</Layout>
}

export default App
