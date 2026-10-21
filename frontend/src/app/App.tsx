import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/layout/AppShell'
import { ChatPage } from '../pages/chat/ChatPage'
import { TodayPage } from '../pages/today/TodayPage'
import { DreamingPage } from '../pages/dreaming/DreamingPage'
import { KnowledgeLayout } from '../pages/knowledge/KnowledgeLayout'
import { JobsPage } from '../pages/knowledge/jobs/JobsPage'
import { PreparationPage } from '../pages/knowledge/preparation/PreparationPage'
import { PersonalPage } from '../pages/knowledge/personal/PersonalPage'

function Placeholder({ title }: { title: string }) {
  return (
    <section className="glass-card" style={{ minHeight: 560, padding: 40, borderRadius: 28 }}>
      <p className="eyebrow">CareerPilot</p>
      <h1 className="page-title">{title}</h1>
      <p className="muted">这一页正在准备中。</p>
    </section>
  )
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/today" element={<TodayPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/dreaming" element={<DreamingPage />} />
        <Route path="/compass" element={<Placeholder title="罗盘" />} />
        <Route path="/journey" element={<Placeholder title="航程" />} />
        <Route path="/memory" element={<Placeholder title="记忆" />} />
        <Route path="/settings" element={<Placeholder title="设置" />} />
        <Route path="/knowledge" element={<KnowledgeLayout />}>
          <Route index element={<Navigate to="/knowledge/jobs" replace />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="preparation" element={<PreparationPage />} />
          <Route path="personal" element={<PersonalPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/today" replace />} />
      </Routes>
    </AppShell>
  )
}
