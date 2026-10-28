import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from './AuthProvider'

export function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') return <div className="auth-boot" role="status">正在打开 CareerPilot…</div>
  if (status === 'guest') return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}

export function GuestRoute() {
  const { status } = useAuth()
  if (status === 'loading') return <div className="auth-boot" role="status">正在打开 CareerPilot…</div>
  if (status === 'authenticated') return <Navigate to="/" replace />
  return <Outlet />
}
