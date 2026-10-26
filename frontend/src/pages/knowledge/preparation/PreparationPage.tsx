import { ArrowSquareOut, MagnifyingGlass, Sparkle } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { curatedLearning } from '../../../data/curatedLearning'

export function PreparationPage() {
  const [query,setQuery] = useState('')
  const [category,setCategory] = useState('全部')
  const [selected,setSelected] = useState(curatedLearning[0].id)
  const resources = useMemo(() => curatedLearning.filter((item) => (category === '全部' || item.category === category) && `${item.title} ${item.publisher} ${item.description}`.toLowerCase().includes(query.toLowerCase())),[query,category])
  const featured = resources.find((item) => item.id === selected) || resources[0]
  return <section className="library-dashboard learning-library"><aside className="library-rail glass-card"><div className="rail-title"><Sparkle />专题</div>{['全部','AI 基础','产品设计','工程实践','行业应用'].map((item) => <button type="button" className={category === item ? 'active simple' : 'simple'} key={item} onClick={() => setCategory(item)}>{item}</button>)}<Link className="chat-collect" to="/chat" state={{draft:'帮我联网搜索 AI 产品经理的优质学习资料，验证来源后直接存入知识库。'}}>让泊泊继续收集</Link></aside><div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索学习资料" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索课程、指南或案例" /></label></div>{featured && <article className={`library-feature learning-feature accent-${featured.accent}`}><div><span>{featured.category} · {featured.format}</span><p>{featured.publisher}</p><h2>{featured.title}</h2><p>{featured.description}</p><a href={featured.url} target="_blank" rel="noreferrer" className="primary-button">打开资料 <ArrowSquareOut /></a></div></article>}<div className="library-shelf"><header><div><p className="eyebrow">Curated for every major</p><h2>AI 共同能力</h2></div><span>由 CareerPilot 编辑整理</span></header><div className="shelf-row">{resources.map((item) => <button type="button" className={`resource-book accent-${item.accent}`} key={item.id} onClick={() => setSelected(item.id)}><span>{item.publisher}</span><strong>{item.title}</strong><small>{item.category}</small></button>)}</div></div></div></section>
}
