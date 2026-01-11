/* @refresh reload */
import { render } from 'solid-js/web'
import { Router, Route } from '@solidjs/router'
import './index.css'
import App from './App'
import {
  Dashboard,
  Agents,
  Tasks,
  Workflows,
  Conversations,
  Monitoring,
  Settings,
} from './pages'

const root = document.getElementById('root')

if (!root) {
  throw new Error('Root element not found')
}

render(
  () => (
    <Router root={App}>
      <Route path="/" component={Dashboard} />
      <Route path="/agents" component={Agents} />
      <Route path="/tasks" component={Tasks} />
      <Route path="/workflows" component={Workflows} />
      <Route path="/conversations" component={Conversations} />
      <Route path="/monitoring" component={Monitoring} />
      <Route path="/settings" component={Settings} />
    </Router>
  ),
  root
)
