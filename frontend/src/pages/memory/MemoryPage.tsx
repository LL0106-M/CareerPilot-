import { useCallback, useEffect, useState } from 'react'

import { api, type CanonicalMemory, type CanonicalMemoryType } from '../../data/api'

const TABS = [
  { key: 'all', label: '全部' },
  { key: 'goal', label: '长期目标' },
  { key: 'preference', label: '偏好' },
  { key: 'fact', label: '事实' },
  { key: 'candidate', label: '待确认' },
] as const

type TabKey = (typeof TABS)[number]['key']

const TYPE_LABEL: Record<CanonicalMemoryType, string> = {
  fact: '事实', preference: '偏好', goal: '长期目标', constraint: '约束',
  idea: '想法', experience: '经历', decision: '决定', hypothesis: '待验证猜想',
}

const SOURCE_LABEL: Record<CanonicalMemory['source_type'], string> = {
  conversation: '对话', manual: '手动添加', integration: '外部资料', dreaming: '后台整理', migration: '历史迁移',
}

const STATUS_LABEL: Record<CanonicalMemory['status'], string> = {
  candidate: '待你确认', active: '正在使用', paused: '已暂停', superseded: '已被更新', deleted: '已删除',
}

export function MemoryPage() {
  const [tab, setTab] = useState<TabKey>('all')
  const [items, setItems] = useState<CanonicalMemory[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState('')
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setError('')
    try {
      const result = await api.getMemories()
      setItems(result.items)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '记忆暂时无法读取，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])

  const visibleItems = items.filter((item) => (
    tab === 'all' || (tab === 'candidate' ? item.status === 'candidate' : item.type === tab)
  ))

  async function transition(item: CanonicalMemory, operation: 'confirm' | 'pause' | 'resume') {
    setBusy(item.id)
    setError('')
    try {
      await api.transitionMemory(item.id, operation, item.version)
      await reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '这次没有更新成功，请重试。')
    } finally {
      setBusy('')
    }
  }

  async function save(item: CanonicalMemory) {
    const content = draft.trim()
    if (!content) return
    setBusy(item.id)
    try {
      await api.updateMemory(item.id, item.version, content)
      setEditing(null)
      await reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '这次没有保存成功，请重试。')
    } finally {
      setBusy('')
    }
  }

  async function remove(item: CanonicalMemory) {
    setBusy(item.id)
    try {
      await api.deleteMemory(item.id, item.version)
      setDeleteConfirm(null)
      await reload()
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '这次没有删除成功，请重试。')
    } finally {
      setBusy('')
    }
  }

  return (
    <div className="memory-layout">
      <section className="glass-card memory-header">
        <p className="eyebrow">记忆</p>
        <h1 className="page-title">知识库和记忆是两回事</h1>
        <p className="muted">
          这里只放你明确要求保留的内容、稳定偏好、长期目标和待你确认的发现。一次情绪不会被当成永久标签。
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

        {loading && <div className="state-panel">泊泊正在整理你的记忆……</div>}
        {error && <div className="state-panel error" role="alert"><span>{error}</span><button type="button" onClick={() => void reload()}>重试</button></div>}
        {!loading && <ul className="memory-list">
          {visibleItems.map((item) => {
            const isPaused = item.status === 'paused'
            const isEditing = editing === item.id
            return (
              <li key={item.id} className={`memory-item${isPaused ? ' paused' : ''}`}>
                <div className="memory-main">
                  {isEditing ? (
                    <label className="memory-editor">记忆内容
                      <textarea aria-label="记忆内容" value={draft} onChange={(event) => setDraft(event.target.value)} />
                    </label>
                  ) : <div className="memory-content">{item.content}</div>}
                  <div className="memory-meta">
                    <span className="tag">{TYPE_LABEL[item.type]}</span>
                    <span className="tag tag-state">{STATUS_LABEL[item.status]}</span>
                    {item.sensitivity !== 'normal' && <span className="tag tag-warning">{item.sensitivity === 'sensitive' ? '敏感' : '私密'}</span>}
                    <span className="memory-source">来自 {SOURCE_LABEL[item.source_type]}</span>
                    <span className="muted">· {new Date(item.updated_at).toLocaleDateString('zh-CN')}</span>
                  </div>
                </div>
                <div className="memory-actions">
                  {item.status === 'candidate' && <button type="button" className="text-button" disabled={busy === item.id} onClick={() => void transition(item, 'confirm')}>确认记住</button>}
                  {(item.status === 'active' || item.status === 'paused') && <button type="button" className="text-button" disabled={busy === item.id} onClick={() => void transition(item, isPaused ? 'resume' : 'pause')}>{isPaused ? '恢复使用' : '暂停使用'}</button>}
                  {isEditing ? <button type="button" className="text-button" disabled={busy === item.id || !draft.trim()} onClick={() => void save(item)}>保存修改</button> : <button type="button" className="text-button" onClick={() => { setEditing(item.id); setDraft(item.content) }}>修改</button>}
                  {isEditing && <button type="button" className="text-button" onClick={() => setEditing(null)}>取消</button>}
                  <button
                    type="button"
                    className="text-button danger"
                    disabled={busy === item.id}
                    onClick={() => deleteConfirm === item.id ? void remove(item) : setDeleteConfirm(item.id)}
                  >
                    {deleteConfirm === item.id ? '确认删除' : '删除'}
                  </button>
                </div>
              </li>
            )
          })}
          {visibleItems.length === 0 && (
            <li className="empty-row">当前分类下还没有记忆。</li>
          )}
        </ul>}
      </section>
    </div>
  )
}
