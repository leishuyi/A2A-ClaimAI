import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import CaseList from './pages/CaseList'
import CaseDetail from './pages/CaseDetail'
import HumanGate from './pages/HumanGate'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/cases" element={<CaseList />} />
        <Route path="/cases/:id" element={<CaseDetail />} />
        <Route path="/cases/:id/review" element={<HumanGate />} />
        <Route path="*" element={<Navigate to="/cases" replace />} />
      </Routes>
    </Layout>
  )
}
