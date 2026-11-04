import { ArrowClockwise, ArrowSquareOut, Buildings, Clock, MagnifyingGlass } from '@phosphor-icons/react'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, mapApiJob } from '../../../data/api'
import type { CollectedJobSource } from '../../../data/api'
import { filterJobs } from '../../../data/filtering'
import type { JobFilters, JobRecord } from '../../../data/types'

const TYPES = ['全部','央企','地方国企','民营企业','外资企业','政府部门','事业单位','未知']
const DEADLINES = ['全部','招聘中','即将截止','已截止','时间未知']

export function JobsPage() {
  const [jobs,setJobs] = useState<JobRecord[]>([])
  const [collectedSources,setCollectedSources] = useState<CollectedJobSource[]>([])
  const [selected,setSelected] = useState('')
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [updatedAt,setUpdatedAt] = useState<Date>()
  const [filters,setFilters] = useState<JobFilters>({query:'',companyType:'全部',company:'全部',roleType:'全部',deadlineStatus:'全部'})
  const load = useCallback(async () => { setLoading(true); setError(''); try { const {items,collected_sources} = await api.getJobs(); setJobs(items.map(mapApiJob)); setCollectedSources(collected_sources || []); setUpdatedAt(new Date()) } catch (reason) { setError(reason instanceof Error ? reason.message : '加载失败') } finally { setLoading(false) } },[])
  useEffect(() => { void load(); const refresh = () => void load(); window.addEventListener('focus',refresh); return () => window.removeEventListener('focus',refresh) },[load])
  const rows = useMemo(() => filterJobs(jobs,filters),[jobs,filters])
  const featured = rows.find((job) => job.id === selected) || rows[0]
  const update = <K extends keyof JobFilters>(key:K,value:JobFilters[K]) => setFilters((old) => ({...old,[key]:value}))

  return <section className="library-dashboard jobs-library">
    <aside className="library-rail glass-card"><div className="rail-title"><Clock />最近查看</div>{jobs.slice(0,5).map((job) => <button type="button" key={job.id} onClick={() => setSelected(job.id)} className={featured?.id === job.id ? 'active' : ''}><span>{job.company.slice(0,1)}</span><div><strong>{job.role}</strong><small>{job.company}</small></div></button>)}{jobs.length === 0 && !loading && <p>还没有保存的岗位。</p>}</aside>
    <div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索企业或岗位" placeholder="搜索企业或岗位" value={filters.query} onChange={(e) => update('query',e.target.value)} /></label><select aria-label="企业类型" value={filters.companyType} onChange={(e) => update('companyType',e.target.value)}>{TYPES.map((item) => <option key={item}>{item}</option>)}</select><select aria-label="截止状态" value={filters.deadlineStatus} onChange={(e) => update('deadlineStatus',e.target.value)}>{DEADLINES.map((item) => <option key={item}>{item}</option>)}</select><button type="button" className="secondary-button" aria-label="刷新岗位知识库" onClick={() => void load()} disabled={loading}><ArrowClockwise /> 刷新</button>{updatedAt && <small>最近检查 {updatedAt.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</small>}</div>
      {loading && <div className="library-feature glass-card loading">正在从知识库读取岗位……</div>}{error && <div className="library-feature glass-card error">{error}</div>}{!loading && !error && !featured && <div className="library-feature glass-card empty"><Buildings size={40} /><h2>这里还没有岗位</h2><p>在对话里明确说“搜索并保存 AI 产品岗位”，核验过且带来源链接的结果会进入这里。</p><Link to="/chat" state={{draft:'帮我搜索适合应届生的 AI 产品岗位，并把核验过的结果存入知识库。'}} className="primary-button">去对话搜索</Link></div>}
      {featured && <article className="library-feature job-feature"><div className="feature-shade"><div className="feature-tags"><span>{featured.companyType}</span><span>{featured.roleType}</span><span>{featured.deadlineStatus}</span></div><p>{featured.company}</p><h2>{featured.role}</h2><div className="job-facts"><span>{featured.location}</span><span>截止 {featured.deadline}</span><span>{featured.source}</span></div><p className="feature-description">{featured.description || '打开来源网页查看完整岗位说明。'}</p><div className="feature-actions">{featured.sourceUrl && <a href={featured.sourceUrl} target="_blank" rel="noreferrer" className="primary-button">查看来源 <ArrowSquareOut /></a>}<Link to="/chat" state={{draft:`帮我分析 ${featured.company} 的 ${featured.role}，并结合我的资料给出准备建议。`}} className="secondary-button">和泊泊一起看</Link></div></div></article>}
      {rows.length > 0 && <div className="library-shelf"><header><div><p className="eyebrow">Opportunities</p><h2>筛选结果</h2></div><span>{rows.length} 个岗位</span></header><div className="shelf-row">{rows.map((job) => <button className={`job-book ${featured?.id === job.id ? 'active' : ''}`} type="button" key={job.id} onClick={() => setSelected(job.id)}><span className="book-company">{job.company}</span><strong>{job.role}</strong><small>{job.location} · {job.deadline}</small><i>{job.companyType}</i></button>)}</div></div>}
      {collectedSources.length > 0 && <div className="library-shelf"><header><div><p className="eyebrow">Needs verification</p><h2>待核实的岗位来源</h2></div><span>不计入正式岗位</span></header><div className="shelf-row">{collectedSources.map((source) => <a className="job-book" aria-label={source.title} href={source.url} target="_blank" rel="noreferrer" key={source.id}><span className="book-company">{source.publisher}</span><strong>{source.title}</strong><small>{source.description}</small></a>)}</div></div>}
    </div>
  </section>
}
