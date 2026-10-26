import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/layout/AppShell'
import { ChatPage } from '../pages/chat/ChatPage'
import { TodayPage } from '../pages/today/TodayPage'
import { DreamingPage } from '../pages/dreaming/DreamingPage'
import { CompassPage } from '../pages/compass/CompassPage'
import { JourneyPage } from '../pages/journey/JourneyPage'
import { MemoryPage } from '../pages/memory/MemoryPage'
import { SettingsPage } from '../pages/settings/SettingsPage'
import { IntroPage } from '../pages/intro/IntroPage'
import { KnowledgeLayout } from '../pages/knowledge/KnowledgeLayout'
import { JobsPage } from '../pages/knowledge/jobs/JobsPage'
import { PreparationPage } from '../pages/knowledge/preparation/PreparationPage'
import { PersonalPage } from '../pages/knowledge/personal/PersonalPage'

function WrapShell({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>
}

export function App() {
  return (
    <Routes>
      <Route path="/intro" element={<IntroPage />} />
      <Route path="/" element={<WrapShell><TodayPage /></WrapShell>} />
      <Route path="/today" element={<Navigate to="/" replace />} />
      <Route path="/chat" element={<WrapShell><ChatPage /></WrapShell>} />
      <Route path="/dreaming" element={<WrapShell><DreamingPage /></WrapShell>} />
      <Route path="/compass" element={<WrapShell><CompassPage /></WrapShell>} />
      <Route path="/journey" element={<WrapShell><JourneyPage /></WrapShell>} />
      <Route path="/memory" element={<WrapShell><MemoryPage /></WrapShell>} />
      <Route path="/settings" element={<WrapShell><SettingsPage /></WrapShell>} />
      <Route path="/knowledge" element={<WrapShell><KnowledgeLayout /></WrapShell>}>
        <Route index element={<Navigate to="/knowledge/jobs" replace />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="preparation" element={<PreparationPage />} />
        <Route path="personal" element={<PersonalPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
