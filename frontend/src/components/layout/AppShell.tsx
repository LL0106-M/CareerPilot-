import { CaretDown, GearSix, SignOut } from '@phosphor-icons/react'
import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'

import { useAuth } from '../../auth/AuthProvider'
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
  const { account, logout } = useAuth()
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)

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

        <div className="topbar-actions account-menu-wrap">
          <button
            className="profile-button"
            type="button"
            aria-expanded={accountMenuOpen}
            aria-haspopup="menu"
            aria-label={`${account?.username ?? '用户'}的账户菜单`}
            onClick={() => setAccountMenuOpen((open) => !open)}
          >
            <img src="/assets/bobo-idle.png" alt="" />
            <span>{account?.username}</span>
            <CaretDown size={15} weight="bold" aria-hidden="true" />
          </button>
          {accountMenuOpen && account ? (
            <div className="account-menu glass-strong" role="menu">
              <div className="account-summary">
                <strong>{account.username}</strong>
                <span>{account.email}</span>
              </div>
              <Link to="/settings" role="menuitem" onClick={() => setAccountMenuOpen(false)}>
                <GearSix size={18} weight="duotone" aria-hidden="true" />
                设置
              </Link>
              <button type="button" role="menuitem" onClick={() => void logout()}>
                <SignOut size={18} weight="duotone" aria-hidden="true" />
                退出登录
              </button>
            </div>
          ) : null}
        </div>
      </header>

      <main className="app-content" id="main-content">{children}</main>
    </div>
  )
}
