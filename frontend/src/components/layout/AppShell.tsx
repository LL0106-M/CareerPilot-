import {
  BellSimple,
  Binoculars,
  BookOpenText,
  Brain,
  ChatsCircle,
  Compass,
  House,
  Path,
} from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import './app-shell.css'

const navigation = [
  { to: '/today', label: '今天', icon: House },
  { to: '/chat', label: '对话', icon: ChatsCircle },
  { to: '/compass', label: '罗盘', icon: Compass },
  { to: '/journey', label: '航程', icon: Path },
  { to: '/knowledge/jobs', label: '知识库', icon: BookOpenText },
  { to: '/memory', label: '记忆', icon: Brain },
]

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <div className="app-backdrop" aria-hidden="true" />
      <header className="topbar glass-strong">
        <NavLink className="brand-lockup" to="/today" aria-label="返回今天">
          <img src="/assets/careerpilot-wordmark.png" alt="CareerPilot" />
        </NavLink>

        <nav className="main-nav" aria-label="主导航">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <Icon size={18} weight="duotone" aria-hidden="true" />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="topbar-actions">
          <button className="icon-button" type="button" aria-label="打开通知">
            <BellSimple size={21} weight="duotone" />
            <span className="notification-dot" />
          </button>
          <NavLink className="profile-button" to="/settings" aria-label="打开设置">
            <img src="/assets/bobo-idle.png" alt="" />
            <span>泊泊</span>
            <Binoculars size={17} weight="duotone" aria-hidden="true" />
          </NavLink>
        </div>
      </header>

      <main className="app-content">{children}</main>
    </div>
  )
}
