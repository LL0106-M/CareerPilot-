import { GearSix } from '@phosphor-icons/react'
import type { ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { AmbientScene } from '../ambient/AmbientScene'
import { ScrollDirector } from '../motion/ScrollDirector'
import './app-shell.css'

const navigation = [
  { to: '/', label: '首页', end: true },
  { to: '/chat', label: '对话' },
  { to: '/compass', label: '罗盘' },
  { to: '/journey', label: '航程' },
  { to: '/knowledge/jobs', label: '知识库' },
]

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <ScrollDirector />
      <AmbientScene />
      <header className="topbar">
        <NavLink className="brand-lockup" to="/" aria-label="返回首页">
          <img src="/assets/careerpilot-wordmark.png" alt="CareerPilot" />
        </NavLink>

        <nav className="main-nav glass-strong" aria-label="主导航">
          {navigation.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
            >
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="topbar-actions">
          <NavLink className="profile-button" to="/settings" aria-label="打开设置">
            <img src="/assets/bobo-idle.png" alt="" />
            <GearSix size={17} weight="duotone" aria-hidden="true" />
          </NavLink>
        </div>
      </header>

      <main className="app-content" id="main-content">{children}</main>
    </div>
  )
}
