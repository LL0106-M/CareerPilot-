import { ArrowSquareOut, MagnifyingGlass, Sparkle } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { curatedLearning } from '../../../data/curatedLearning'
import { api, type PreparationResource } from '../../../data/api'

type LearningResource = PreparationResource & { accent: 'pine' | 'amber' | 'sky' | 'clay' }

export function PreparationPage() {
  const [query,setQuery] = useState('')
  const [category,setCategory] = useState('全部')
  const [selected,setSelected] = useState(curatedLearning[0].id)
  const [collected,setCollected] = useState<LearningResource[]>([])
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  useEffect(() => { let alive = true; api.getPreparation().then(({items}) => { if (!alive) return; const live = items.map((item) => ({...item,accent:'pine' as const})); setCollected(live); if (live[0]) setSelected(live[0].id) }).catch((reason) => { if (alive) setError(reason instanceof Error ? reason.message : '资料更新失败') }).finally(() => { if (alive) setLoading(false) }); return () => { alive = false } }, [])
  const allResources = useMemo<LearningResource[]>(() => [...collected, ...curatedLearning.map((item) => ({...item,updated_at:'',source_type:'curated'}))], [collected])
  const resources = useMemo(() => allResources.filter((item) => (category === '全部' || item.category === category) && `${item.title} ${item.publisher} ${item.description}`.toLowerCase().includes(query.toLowerCase())),[allResources,query,category])
  const featured = resources.find((item) => item.id === selected) || resources[0]
  return <section className="library-dashboard learning-library"><aside className="library-rail glass-card"><div className="rail-title"><Sparkle />专题</div>{['全部','AI 基础','产品设计','工程实践','行业应用'].map((item) => <button type="button" className={category === item ? 'active simple' : 'simple'} key={item} onClick={() => setCategory(item)}>{item}</button>)}<Link className="chat-collect" to="/chat" state={{draft:'帮我联网搜索 AI 产品经理的优质学习资料，验证来源后直接存入知识库。'}}>让泊泊继续收集</Link>{loading && <p>正在检查新资料…</p>}{error && <p role="alert">{error}</p>}</aside><div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索学习资料" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索课程、指南或案例" /></label></div>{featured && <article className={`library-feature learning-feature accent-${featured.accent}`}><div><span>{featured.category} · {featured.format}</span><p>{featured.publisher}</p><h2>{featured.title}</h2><p>{featured.description}</p><a href={featured.url} target="_blank" rel="noreferrer" className="primary-button">打开资料 <ArrowSquareOut /></a></div></article>}<div className="library-shelf"><header><div><p className="eyebrow">Collected & curated</p><h2>学习资料</h2></div><span>{collected.length > 0 ? `${collected.length} 条来自近期对话收集` : '由 CareerPilot 编辑整理'}</span></header><div className="shelf-row">{resources.map((item) => <button type="button" className={`resource-book accent-${item.accent}`} key={item.id} onClick={() => setSelected(item.id)}><span>{item.publisher}</span><strong>{item.title}</strong><small>{item.category}</small></button>)}</div></div></div></section>
}
