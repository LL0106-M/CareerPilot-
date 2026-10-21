import { NavLink, Outlet } from 'react-router-dom'

const subNav = [
  { to: '/knowledge/jobs', label: '岗位信息' },
  { to: '/knowledge/preparation', label: '备考资料' },
  { to: '/knowledge/personal', label: '个人资料库' },
]

export function KnowledgeLayout() {
  return (
    <div className="knowledge-layout">
      <nav className="knowledge-subnav glass-card" aria-label="知识库子导航">
        {subNav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) => `subnav-item${isActive ? ' active' : ''}`}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  )
}
