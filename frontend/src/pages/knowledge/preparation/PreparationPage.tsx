import { useMemo, useState } from 'react'
import { demoMaterials } from '../../../data/demoRepository'
import { filterMaterials } from '../../../data/filtering'
import type { MaterialFilters, PreparationPrimary, PreparationSecondary } from '../../../data/types'

const SECONDARY_MAP: Record<PreparationPrimary, PreparationSecondary[]> = {
  面试: ['面经', '面试准备'],
  笔试: ['考题', '准备资料'],
}

export function PreparationPage() {
  const [filters, setFilters] = useState<MaterialFilters>({
    query: '',
    primary: '面试',
    secondary: '面经',
    company: '全部',
  })

  const companies = useMemo(() => {
    const set = new Set(demoMaterials.map((m) => m.company))
    return ['全部', ...Array.from(set)]
  }, [])

  const rows = useMemo(() => filterMaterials(demoMaterials, filters), [filters])

  function setPrimary(value: PreparationPrimary) {
    setFilters((prev) => ({ ...prev, primary: value, secondary: SECONDARY_MAP[value][0] }))
  }

  function setSecondary(value: PreparationSecondary) {
    setFilters((prev) => ({ ...prev, secondary: value }))
  }

  return (
    <section className="glass-strong preparation-page">
      <div className="prep-header">
        <p className="eyebrow">知识库 · 备考资料</p>
        <h1 className="page-title">备考资料</h1>
      </div>

      <div className="prep-category-row">
        {(['面试', '笔试'] as const).map((primary) => (
          <button
            key={primary}
            type="button"
            className={`category-pill${filters.primary === primary ? ' active' : ''}`}
            onClick={() => setPrimary(primary)}
          >
            {primary}
          </button>
        ))}
      </div>

      <div className="prep-category-row secondary">
        {SECONDARY_MAP[filters.primary].map((secondary) => (
          <button
            key={secondary}
            type="button"
            className={`category-pill secondary${filters.secondary === secondary ? ' active' : ''}`}
            onClick={() => setSecondary(secondary)}
          >
            {secondary}
          </button>
        ))}
      </div>

      <div className="prep-filters">
        <input
          className="filter-search"
          placeholder="搜索资料关键词"
          aria-label="搜索资料关键词"
          value={filters.query}
          onChange={(e) => setFilters((prev) => ({ ...prev, query: e.target.value }))}
        />
        <label className="filter-label">
          <span>企业</span>
          <select
            aria-label="企业"
            value={filters.company}
            onChange={(e) => setFilters((prev) => ({ ...prev, company: e.target.value }))}
          >
            {companies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="text-button"
          onClick={() =>
            setFilters((prev) => ({ ...prev, query: '', company: '全部' }))
          }
        >
          清除筛选
        </button>
      </div>

      <ul className="material-list">
        {rows.map((m) => (
          <li key={m.id} className="material-item glass-card">
            <div className="material-title">{m.title}</div>
            <div className="material-meta">
              {m.company} · {m.source} · {m.updatedAt}
            </div>
            <p className="material-excerpt muted">{m.excerpt}</p>
          </li>
        ))}
        {rows.length === 0 && <li className="empty-row">没有匹配的资料。</li>}
      </ul>
    </section>
  )
}
