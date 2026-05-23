import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Agents from './pages/Agents'
import Workflows from './pages/Workflows'
import Sessions from './pages/Sessions'
import Metrics from './pages/Metrics'
import Admin from './pages/Admin'
import { I18nProvider } from './i18n'

export default function App() {
  return (
    <I18nProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/workflows" element={<Workflows />} />
            <Route path="/sessions" element={<Sessions />} />
            <Route path="/metrics" element={<Metrics />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </I18nProvider>
  )
}
