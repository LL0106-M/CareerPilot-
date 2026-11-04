import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'

import { AppShell } from '../components/layout/AppShell'
import { AuthProvider } from '../auth/AuthProvider'
import { GuestRoute, ProtectedRoute } from '../auth/ProtectedRoute'

const ChatPage = lazy(() => import('../pages/chat/ChatPage').then(({ ChatPage }) => ({ default: ChatPage })))
const TodayPage = lazy(() => import('../pages/today/TodayPage').then(({ TodayPage }) => ({ default: TodayPage })))
const DreamingPage = lazy(() => import('../pages/dreaming/DreamingPage').then(({ DreamingPage }) => ({ default: DreamingPage })))
const CompassPage = lazy(() => import('../pages/compass/CompassPage').then(({ CompassPage }) => ({ default: CompassPage })))
const JourneyPage = lazy(() => import('../pages/journey/JourneyPage').then(({ JourneyPage }) => ({ default: JourneyPage })))
const SettingsPage = lazy(() => import('../pages/settings/SettingsPage').then(({ SettingsPage }) => ({ default: SettingsPage })))
const IntroPage = lazy(() => import('../pages/intro/IntroPage').then(({ IntroPage }) => ({ default: IntroPage })))
const KnowledgeLayout = lazy(() => import('../pages/knowledge/KnowledgeLayout').then(({ KnowledgeLayout }) => ({ default: KnowledgeLayout })))
const JobsPage = lazy(() => import('../pages/knowledge/jobs/JobsPage').then(({ JobsPage }) => ({ default: JobsPage })))
const PreparationPage = lazy(() => import('../pages/knowledge/preparation/PreparationPage').then(({ PreparationPage }) => ({ default: PreparationPage })))
const InterviewArchivePage = lazy(() => import('../pages/knowledge/interview/InterviewArchivePage').then(({ InterviewArchivePage }) => ({ default: InterviewArchivePage })))
const PersonalPage = lazy(() => import('../pages/knowledge/personal/PersonalPage').then(({ PersonalPage }) => ({ default: PersonalPage })))
const LoginPage = lazy(() => import('../pages/auth/LoginPage').then(({ LoginPage }) => ({ default: LoginPage })))
const RegisterPage = lazy(() => import('../pages/auth/RegisterPage').then(({ RegisterPage }) => ({ default: RegisterPage })))

function WrapShell({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>
}

export function App() {
  return (
    <AuthProvider>
      <Suspense fallback={<div className="auth-boot" role="status">正在打开 CareerPilot…</div>}><Routes>
        <Route element={<GuestRoute />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route element={<ProtectedRoute />}>
          <Route path="/intro" element={<IntroPage />} />
          <Route path="/" element={<WrapShell><TodayPage /></WrapShell>} />
          <Route path="/today" element={<Navigate to="/" replace />} />
          <Route path="/chat" element={<WrapShell><ChatPage /></WrapShell>} />
          <Route path="/dreaming" element={<WrapShell><DreamingPage /></WrapShell>} />
          <Route path="/compass" element={<WrapShell><CompassPage /></WrapShell>} />
          <Route path="/journey" element={<WrapShell><JourneyPage /></WrapShell>} />
          <Route path="/settings" element={<WrapShell><SettingsPage /></WrapShell>} />
          <Route path="/knowledge" element={<WrapShell><KnowledgeLayout /></WrapShell>}>
            <Route index element={<Navigate to="/knowledge/jobs" replace />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="preparation" element={<Navigate to="/knowledge/learning" replace />} />
            <Route path="interview-archive" element={<InterviewArchivePage />} />
            <Route path="learning" element={<PreparationPage />} />
            <Route path="personal" element={<PersonalPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes></Suspense>
    </AuthProvider>
  )
}
