import { useState } from 'react'
import { demoMemories } from '../../data/demoRepository'
import type { MemoryItem } from '../../data/types'

const TABS = [
  { key: 'all', label: '全部' },
  { key: '长期目标', label: '长期目标' },
  { key: '偏好', label: '偏好' },
  { key: '事实', label: '事实' },
] as const

type TabKey = (typeof TABS)[number]['key']

const TYPE_COLOR: Record<MemoryItem['type'], string> = {
  '长期目标': 'tag-hypothesis',
  '偏好': 'tag',
  '事实': 'tag-state',
  '情绪': 'tag-warning',
}

export function MemoryPage() {
  const [tab, setTab] = useState<TabKey>('all')
  const [paused, setPaused] = useState<Set<string>>(new Set())

  const items = demoMemories.filter((m) => tab === 'all' || m.type === tab)

  function togglePause(id: string) {
    setPaused((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div className="memory-layout">
      <section className="glass-card memory-header">
        <p className="eyebrow">记忆</p>
        <h1 className="page-title">知识库和记忆是两回事</h1>
        <p className="muted">
          这里只放你明确说"记住这个"的事、稳定偏好、长期目标和 Agent 确认过的猜想。岗位、PDF、简历正文都不在这里。
        </p>
      </section>

      <section className="glass-card memory-panel">
        <div className="memory-tabs">
          {TABS.map((t) => (
            <button
              key={t.key}
              type="button"
              className={`memory-tab${tab === t.key ? ' active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <ul className="memory-list">
          {items.map((item) => {
            const isPaused = paused.has(item.id)
            return (
              <li key={item.id} className={`memory-item${isPaused ? ' paused' : ''}`}>
                <div className="memory-main">
                  <div className="memory-content">{item.content}</div>
                  <div className="memory-meta">
                    <span className={`tag ${TYPE_COLOR[item.type]}`}>{item.type}</span>
                    <span className="memory-source">来自 {item.source}</span>
                    <span className="muted">· {item.createdAt}</span>
                  </div>
                </div>
                <div className="memory-actions">
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => togglePause(item.id)}
                  >
                    {isPaused ? '恢复使用' : '暂停使用'}
                  </button>
                  <button type="button" className="text-button">修改</button>
                  <button type="button" className="text-button danger">删除</button>
                </div>
              </li>
            )
          })}
          {items.length === 0 && (
            <li className="empty-row">当前分类下还没有记忆。</li>
          )}
        </ul>
      </section>
    </div>
  )
}
