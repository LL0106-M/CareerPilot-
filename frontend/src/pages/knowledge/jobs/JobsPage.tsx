import { useMemo, useState } from 'react'
import { demoJobs } from '../../../data/demoRepository'
import { filterJobs } from '../../../data/filtering'
import type { JobFilters } from '../../../data/types'

const COMPANY_TYPES = ['全部', '央企', '地方国企', '民营企业', '外资企业', '政府部门', '事业单位', '未知']
const ROLE_TYPES = ['全部', '产品', 'AI 产品', '运营', '技术', '数据', '职能', '管培生', '其他']
const DEADLINE_STATUSES = ['全部', '招聘中', '即将截止', '已截止', '时间未知']

export function JobsPage() {
  const [filters, setFilters] = useState<JobFilters>({
    query: '',
    companyType: '全部',
    company: '全部',
    roleType: '全部',
    deadlineStatus: '全部',
  })

  const rows = useMemo(() => filterJobs(demoJobs, filters), [filters])

  function update<K extends keyof JobFilters>(key: K, value: JobFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  function clearFilters() {
    setFilters({ query: '', companyType: '全部', company: '全部', roleType: '全部', deadlineStatus: '全部' })
  }

  return (
    <section className="glass-strong jobs-page">
      <div className="jobs-header">
        <div>
          <p className="eyebrow">知识库 · 岗位信息</p>
          <h1 className="page-title">岗位信息</h1>
        </div>
        <div className="jobs-header-actions">
          <button type="button" className="secondary-button">联网搜索岗位</button>
        </div>
      </div>

      <div className="jobs-filters">
        <input
          className="filter-search"
          placeholder="搜索企业或岗位"
          aria-label="搜索企业或岗位"
          value={filters.query}
          onChange={(e) => update('query', e.target.value)}
        />
        <label className="filter-label">
          <span>企业类型</span>
          <select
            aria-label="企业类型"
            value={filters.companyType}
            onChange={(e) => update('companyType', e.target.value)}
          >
            {COMPANY_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="filter-label">
          <span>企业</span>
          <input
            className="filter-search"
            placeholder="输入企业名称"
            aria-label="企业"
            value={filters.company === '全部' ? '' : filters.company}
            onChange={(e) => update('company', e.target.value ? e.target.value : '全部')}
          />
        </label>
        <label className="filter-label">
          <span>岗位类型</span>
          <select
            aria-label="岗位类型"
            value={filters.roleType}
            onChange={(e) => update('roleType', e.target.value)}
          >
            {ROLE_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>
        <label className="filter-label">
          <span>是否截止</span>
          <select
            aria-label="是否截止"
            value={filters.deadlineStatus}
            onChange={(e) => update('deadlineStatus', e.target.value)}
          >
            {DEADLINE_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
        <button type="button" className="text-button" onClick={clearFilters}>清除筛选</button>
      </div>

      <table className="jobs-table">
        <thead>
          <tr>
            <th>企业类型</th>
            <th>企业</th>
            <th>岗位</th>
            <th>岗位类型</th>
            <th>地点</th>
            <th>截止</th>
            <th>状态</th>
            <th>来源</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((job) => (
            <tr key={job.id} className={job.deadlineStatus === '已截止' ? 'row-dim' : ''}>
              <td><span className={`tag tag-${job.companyType}`}>{job.companyType}</span></td>
              <td>{job.company}</td>
              <td>{job.role}</td>
              <td><span className="tag">{job.roleType}</span></td>
              <td>{job.location}</td>
              <td>{job.deadline}</td>
              <td><span className={`status status-${job.deadlineStatus}`}>{job.deadlineStatus}</span></td>
              <td>{job.source}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={8} className="empty-row">没有匹配的岗位。</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  )
}
