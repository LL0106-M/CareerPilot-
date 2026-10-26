import { ArrowSquareOut, Buildings, Clock, MagnifyingGlass } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api, mapApiJob } from '../../../data/api'
import { filterJobs } from '../../../data/filtering'
import type { JobFilters, JobRecord } from '../../../data/types'

const TYPES = ['全部','央企','地方国企','民营企业','外资企业','政府部门','事业单位','未知']
const DEADLINES = ['全部','招聘中','即将截止','已截止','时间未知']

export function JobsPage() {
  const [jobs,setJobs] = useState<JobRecord[]>([])
  const [selected,setSelected] = useState('')
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState('')
  const [filters,setFilters] = useState<JobFilters>({query:'',companyType:'全部',company:'全部',roleType:'全部',deadlineStatus:'全部'})
  useEffect(() => { let alive = true; setLoading(true); api.getJobs().then(({items}) => { if (alive) setJobs(items.map(mapApiJob)) }).catch((reason) => { if (alive) setError(reason instanceof Error ? reason.message : '加载失败') }).finally(() => { if (alive) setLoading(false) }); return () => { alive = false } }, [])
  const rows = useMemo(() => filterJobs(jobs,filters),[jobs,filters])
  const featured = rows.find((job) => job.id === selected) || rows[0]
  const update = <K extends keyof JobFilters>(key:K,value:JobFilters[K]) => setFilters((old) => ({...old,[key]:value}))

  return <section className="library-dashboard jobs-library">
    <aside className="library-rail glass-card"><div className="rail-title"><Clock />最近查看</div>{jobs.slice(0,5).map((job) => <button type="button" key={job.id} onClick={() => setSelected(job.id)} className={featured?.id === job.id ? 'active' : ''}><span>{job.company.slice(0,1)}</span><div><strong>{job.role}</strong><small>{job.company}</small></div></button>)}{jobs.length === 0 && !loading && <p>还没有保存的岗位。</p>}</aside>
    <div className="library-main"><div className="library-tools"><label><MagnifyingGlass /><input aria-label="搜索企业或岗位" placeholder="搜索企业或岗位" value={filters.query} onChange={(e) => update('query',e.target.value)} /></label><select aria-label="企业类型" value={filters.companyType} onChange={(e) => update('companyType',e.target.value)}>{TYPES.map((item) => <option key={item}>{item}</option>)}</select><select aria-label="截止状态" value={filters.deadlineStatus} onChange={(e) => update('deadlineStatus',e.target.value)}>{DEADLINES.map((item) => <option key={item}>{item}</option>)}</select></div>
      {loading && <div className="library-feature glass-card loading">正在从知识库读取岗位……</div>}{error && <div className="library-feature glass-card error">{error}</div>}{!loading && !error && !featured && <div className="library-feature glass-card empty"><Buildings size={40} /><h2>这里还没有岗位</h2><p>在对话里说“搜索 AI 产品岗位”，搜索结果会直接存进知识库。</p><Link to="/chat" state={{draft:'帮我搜索适合应届生的 AI 产品岗位，并把结果存入知识库。'}} className="primary-button">去对话搜索</Link></div>}
      {featured && <article className="library-feature job-feature"><div className="feature-shade"><div className="feature-tags"><span>{featured.companyType}</span><span>{featured.roleType}</span><span>{featured.deadlineStatus}</span></div><p>{featured.company}</p><h2>{featured.role}</h2><div className="job-facts"><span>{featured.location}</span><span>截止 {featured.deadline}</span><span>{featured.source}</span></div><p className="feature-description">{featured.description || '打开来源网页查看完整岗位说明。'}</p><div className="feature-actions">{featured.sourceUrl && <a href={featured.sourceUrl} target="_blank" rel="noreferrer" className="primary-button">查看来源 <ArrowSquareOut /></a>}<Link to="/chat" state={{draft:`帮我分析 ${featured.company} 的 ${featured.role}，并结合我的资料给出准备建议。`}} className="secondary-button">和泊泊一起看</Link></div></div></article>}
      {rows.length > 0 && <div className="library-shelf"><header><div><p className="eyebrow">Opportunities</p><h2>筛选结果</h2></div><span>{rows.length} 个岗位</span></header><div className="shelf-row">{rows.map((job) => <button className={`job-book ${featured?.id === job.id ? 'active' : ''}`} type="button" key={job.id} onClick={() => setSelected(job.id)}><span className="book-company">{job.company}</span><strong>{job.role}</strong><small>{job.location} · {job.deadline}</small><i>{job.companyType}</i></button>)}</div></div>}
    </div>
  </section>
}
