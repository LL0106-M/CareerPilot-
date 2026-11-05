import { ArrowClockwise, ArrowSquareOut, MagnifyingGlass, Sparkle } from '@phosphor-icons/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
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
  const [updatedAt,setUpdatedAt] = useState<Date>()
  const [refreshMessage,setRefreshMessage] = useState('')
  const load = useCallback(async () => { setLoading(true); setError(''); try { const {items} = await api.getLearningResources(); const live = items.map((item) => ({...item,accent:'pine' as const})); setCollected(live); if (live[0]) setSelected(live[0].id); setUpdatedAt(new Date()) } catch (reason) { setError(reason instanceof Error ? reason.message : '资料更新失败') } finally { setLoading(false) } },[])
  const refresh = useCallback(async () => { setLoading(true); setError(''); setRefreshMessage(''); try { const result = await api.refreshLearningResources(); setRefreshMessage(result.saved > 0 ? `新收录 ${result.saved} 条来源` : result.processed > 0 ? '已检查，暂未发现新来源' : '请先从罗盘方向开始航程'); await load() } catch (reason) { setError(reason instanceof Error ? reason.message : '资料更新失败'); setLoading(false) } },[load])
  useEffect(() => { void load(); const refresh = () => void load(); window.addEventListener('focus',refresh); return () => window.removeEventListener('focus',refresh) }, [load])
  const allResources = useMemo<LearningResource[]>(() => [...collected, ...curatedLearning.map((item) => ({...item,updated_at:'',source_type:'curated'}))], [collected])
  const resources = useMemo(() => allResources.filter((item) => (category === '全部' || item.category === category) && `${item.title} ${item.publisher} ${item.description}`.toLowerCase().includes(query.toLowerCase())),[allResources,query,category])
  const featured = resources.find((item) => item.id === selected) || resources[0]
  return <section className="library-dashboard learning-library"><aside className="library-rail glass-card"><div className="rail-title"><Sparkle />专题</div>{['全部','AI 基础','产品设计','工程实践','行业应用'].map((item) => <button type="button" className={category === item ? 'active simple' : 'simple'} key={item} onClick={() => setCategory(item)}>{item}</button>)}<Link className="chat-collect" to="/chat" state={{draft:'帮我联网搜索 AI 产品经理的优质学习资料，验证来源后直接存入知识库。'}}>让泊泊继续收集</Link>{loading && <p>正在检查新资料…</p>}{error && <p role="alert">{error}</p>}</aside><div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索学习资料" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索课程、指南或案例" /></label><button type="button" className="secondary-button" aria-label="刷新知识库" onClick={() => void refresh()} disabled={loading}><ArrowClockwise /> 刷新</button>{updatedAt && <small>最近检查 {updatedAt.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</small>}{refreshMessage && <small>{refreshMessage}</small>}</div>{featured && <article className={`library-feature learning-feature accent-${featured.accent}`}><div><span>{featured.category} · {featured.format}</span><p>{featured.publisher}</p><h2>{featured.title}</h2><p>{featured.description}</p><a href={featured.url} target="_blank" rel="noreferrer" className="primary-button">打开资料 <ArrowSquareOut /></a></div></article>}<div className="library-shelf"><header><div><p className="eyebrow">Collected & curated</p><h2>学习资料</h2></div><span>{collected.length > 0 ? `${collected.length} 条来自近期对话收集` : '由 CareerPilot 编辑整理'}</span></header><div className="shelf-row">{resources.map((item) => <button type="button" className={`resource-book accent-${item.accent}`} key={item.id} onClick={() => setSelected(item.id)}><span>{item.publisher}</span><strong>{item.title}</strong><small>{item.category}</small></button>)}</div></div></div></section>
}
