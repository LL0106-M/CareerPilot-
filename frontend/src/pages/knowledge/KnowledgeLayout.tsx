import { Briefcase, Books, UserCircle } from '@phosphor-icons/react'
import { NavLink, Outlet } from 'react-router-dom'

const subNav = [
  { to: '/knowledge/personal', label: '个人资料', icon: UserCircle },
  { to: '/knowledge/jobs', label: '岗位信息', icon: Briefcase },
  { to: '/knowledge/preparation', label: '学习资料', icon: Books },
]

export function KnowledgeLayout() {
  return <div className="library-shell"><header className="library-header"><div><p className="eyebrow">Your archive</p><h1>知识库</h1><p>需要的时候找到它，不需要的时候保持安静。</p></div><nav className="library-tabs glass-strong" aria-label="知识库分类">{subNav.map(({to,label,icon:Icon}) => <NavLink to={to} key={to} className={({isActive}) => isActive ? 'active' : ''}><Icon />{label}</NavLink>)}</nav></header><Outlet /></div>
}
