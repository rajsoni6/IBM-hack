import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Cases from './pages/Cases'
import Entities from './pages/Entities'
import Graph from './pages/Graph'
import Transactions from './pages/Transactions'
import Settings from './pages/Settings'
import Timeline from './pages/Timeline'
import Evidence from './pages/Evidence'
import Patterns from './pages/Patterns'
import Roles from './pages/Roles'
import MLPrediction from './pages/MLPrediction'
import AIBrief from './pages/AIBrief'

function RequireAuth({ children }: { children: JSX.Element }) {
  const token = localStorage.getItem('auth_token')
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard"    element={<Dashboard />} />
          <Route path="cases"        element={<Cases />} />
          <Route path="entities"     element={<Entities />} />
          <Route path="graph"        element={<Graph />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="timeline"     element={<Timeline />} />
          <Route path="evidence"     element={<Evidence />} />
          <Route path="patterns"     element={<Patterns />} />
          <Route path="roles"        element={<Roles />} />
          <Route path="ml"           element={<MLPrediction />} />
          <Route path="ai-brief"     element={<AIBrief />} />
          <Route path="settings"     element={<Settings />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
