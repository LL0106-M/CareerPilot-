import { ArrowRight, CalendarBlank, CheckCircle, CloudArrowUp, Footprints, Path, Sparkle } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../data/api'
import type { ActionPreview } from '../../data/api'
import type { JourneyItem } from '../../data/types'
import { useDashboard } from '../../hooks/useDashboard'

type ViewMode = 'path' | 'calendar' | 'footprints'

export function JourneyPage() {
  const { data, error, loading, reload } = useDashboard()
  const [view, setView] = useState<ViewMode>('path')
  const [active, setActive] = useState(0)
  const [status, setStatus] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [actionPreview, setActionPreview] = useState<ActionPreview>()
  const [actionState, setActionState] = useState<'idle' | 'previewing' | 'confirming' | 'done' | 'error'>('idle')
  const [actionError, setActionError] = useState('')
  const groups = useMemo(() => groupJourneys(data?.journey || []), [data])
  const current = groups[active]

  async function advance(task: JourneyItem) {
    const next: JourneyItem['state'] = task.state === '准备开始' ? '进行中' : task.state === '进行中' ? '已完成' : task.state
    if (next === task.state) return
    setStatus('saving')
    try { await api.updateJourneyTask(task.id, next); await reload(); setStatus('saved') }
    catch { setStatus('error') }
  }

  async function generatePreview() {
    const task = current?.tasks.find((item) => item.state !== '已完成') || current?.tasks[0]
    if (!task) return
    setActionState('previewing'); setActionError('')
    const start = new Date(Date.now() + 24 * 60 * 60 * 1000)
    start.setHours(19, 0, 0, 0)
    const end = new Date(start.getTime() + 45 * 60 * 1000)
    try {
      const preview = await api.previewAction('feishu', 'calendar.create', {
        summary: task.title,
        start: start.toISOString(),
        end: end.toISOString(),
      })
      setActionPreview(preview)
      setActionState('idle')
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : '无法生成预览')
      setActionState('error')
    }
  }

  async function confirmAndApply() {
    if (!actionPreview) return
    setActionState('confirming'); setActionError('')
    try {
      const confirmation = await api.confirmAction(actionPreview.action_id, actionPreview.preview_hash)
      await api.applyAction(actionPreview.action_id, confirmation.confirmation_token, confirmation.preview_hash, crypto.randomUUID())
      setActionState('done')
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : '外部应用没有执行成功')
      setActionState('error')
    }
  }

  return (
    <div className="journey-experience">
      <header className="journey-hero"><div><p className="eyebrow">Journey</p><h1>不是更多待办，<br />而是一段正在发生的路。</h1></div><div className="journey-view-switch glass-strong">{([['path','航线',Path],['calendar','日历',CalendarBlank],['footprints','足迹',Footprints]] as const).map(([key,label,Icon]) => <button type="button" key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}><Icon />{label}</button>)}</div></header>
      {loading && <div className="state-panel glass-card">正在展开你的航程……</div>}
      {error && <div className="state-panel glass-card error">{error}<button type="button" onClick={() => void reload()}>重试</button></div>}
      {!loading && !error && groups.length === 0 && <div className="state-panel glass-card"><Path size={38} /><h2>路还没有开始画</h2><p>从罗盘里选一条猜想，用一个真实行动去验证。</p><Link className="primary-button" to="/compass">去罗盘看看</Link></div>}
      {groups.length > 0 && <>
        <nav className="journey-selector" aria-label="选择航程">{groups.map((group,index) => <button type="button" className={active === index ? 'active' : ''} onClick={() => setActive(index)} key={group.name}><span>{String(index + 1).padStart(2,'0')}</span>{group.name}</button>)}</nav>
        {view === 'path' && current && <PathView group={current} onAdvance={advance} onPreview={() => setPreviewOpen(true)} />}
        {view === 'calendar' && <CalendarView tasks={data?.journey || []} />}
        {view === 'footprints' && <FootprintView tasks={data?.journey || []} />}
        <p className="mutation-note center" aria-live="polite">{status === 'saving' ? '正在推进……' : status === 'saved' ? '航程已更新。' : status === 'error' ? '这次没有更新成功。' : ''}</p>
      </>}
      {previewOpen && <div className="modal-backdrop"><div className="modal-panel glass-strong" role="dialog" aria-modal="true" aria-label="确认调用外部应用"><CloudArrowUp size={28} /><h2>先预览，再交给其他应用</h2><p>CareerPilot 会先生成操作预览。你确认内容和目标应用后，才会真正执行。</p><div className="preview-row"><span>目标</span><strong>飞书日历</strong></div><div className="preview-row"><span>内容</span><strong>{current?.tasks[0]?.title}</strong></div>{actionPreview && <div className="action-confirmation"><p className="eyebrow">等待你的最终确认</p><small>预览已由后端生成；只有点击确认后才会写入外部应用。</small></div>}{actionState === 'done' && <p className="action-success">已交给飞书日历。</p>}{actionError && <p className="chat-error" role="alert">{actionError}</p>}<div className="modal-actions"><button className="text-button" type="button" onClick={() => { setPreviewOpen(false); setActionPreview(undefined); setActionState('idle'); setActionError('') }}>关闭</button>{!actionPreview && actionState !== 'done' && <button className="primary-button" type="button" onClick={() => void generatePreview()} disabled={actionState === 'previewing'}>{actionState === 'previewing' ? '正在生成…' : '生成预览'}</button>}{actionPreview && actionState !== 'done' && <button className="primary-button" type="button" onClick={() => void confirmAndApply()} disabled={actionState === 'confirming'}>{actionState === 'confirming' ? '正在执行…' : '确认并创建日程'}</button>}</div></div></div>}
    </div>
  )
}

function groupJourneys(tasks: JourneyItem[]) {
  const result = new Map<string, JourneyItem[]>()
  tasks.forEach((task) => { const name = task.related || '未命名航程'; result.set(name, [...(result.get(name) || []), task]) })
  return Array.from(result, ([name, grouped]) => ({ name, tasks: grouped }))
}

function PathView({ group, onAdvance, onPreview }: { group: { name: string; tasks: JourneyItem[] }; onAdvance: (task: JourneyItem) => void; onPreview: () => void }) {
  const focus = group.tasks.find((task) => task.state === '进行中') || group.tasks.find((task) => task.state === '准备开始') || group.tasks[0]
  return <section className="journey-path"><aside className="journey-story glass-card"><p className="eyebrow">Why this journey</p><h2>{group.name}</h2><p>{focus.why || '用一次真实行动补充证据，而不是只靠想象判断方向。'}</p><div className="next-milestone"><Sparkle weight="fill" /><span>下一节点</span><strong>{focus.due}</strong></div></aside><article className="focus-action glass-strong"><span className={`state state-${focus.state}`}>{focus.state}</span><p className="eyebrow">One focus action</p><h2>{focus.title}</h2><p>现在只需要看这一件。其他动作仍在航线上，但不会同时占据你的注意力。</p><div className="focus-actions"><button type="button" className="primary-button" onClick={() => void onAdvance(focus)} disabled={focus.state === '已完成'}>{focus.state === '准备开始' ? '开始这一步' : focus.state === '进行中' ? '完成并留下足迹' : '已经完成'} <ArrowRight /></button><button type="button" className="secondary-button" onClick={onPreview}><CloudArrowUp /> 调用其他 App</button></div></article><div className="route-line" aria-hidden="true" />{group.tasks.map((task,index) => <div className={`route-stop stop-${index % 4}`} key={task.id}><span>{index + 1}</span><strong>{task.title}</strong><small>{task.state}</small></div>)}</section>
}

function CalendarView({ tasks }: { tasks: JourneyItem[] }) {
  const dated = tasks.map((task) => ({ task, date: parseJourneyDate(task.due) })).filter((item): item is { task: JourneyItem; date: Date } => item.date !== null)
  const firstDate = dated[0]?.date || new Date()
  const [month, setMonth] = useState(() => new Date(firstDate.getFullYear(), firstDate.getMonth(), 1))
  const year = month.getFullYear()
  const monthIndex = month.getMonth()
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate()
  const leading = (new Date(year, monthIndex, 1).getDay() + 6) % 7
  const cellCount = Math.ceil((leading + daysInMonth) / 7) * 7
  const tasksByDay = new Map<number, JourneyItem[]>()
  dated.forEach(({ task, date }) => {
    if (date.getFullYear() !== year || date.getMonth() !== monthIndex) return
    tasksByDay.set(date.getDate(), [...(tasksByDay.get(date.getDate()) || []), task])
  })
  const undated = tasks.filter((task) => parseJourneyDate(task.due) === null)
  return <section className="calendar-board glass-card"><header><div><p className="eyebrow">Calendar · 所有航程</p><div className="calendar-month-nav"><button type="button" aria-label="上个月" onClick={() => setMonth(new Date(year, monthIndex - 1, 1))}>‹</button><h2>{year} 年 {monthIndex + 1} 月</h2><button type="button" aria-label="下个月" onClick={() => setMonth(new Date(year, monthIndex + 1, 1))}>›</button></div></div><p>只有明确日期的行动进入日历；其余仍留在路径里。</p></header><div className="calendar-grid">{['一','二','三','四','五','六','日'].map((day) => <div className="calendar-head" key={day}>{day}</div>)}{Array.from({length:cellCount},(_,index) => { const day = index - leading + 1; const dayTasks = tasksByDay.get(day) || []; return day > 0 && day <= daysInMonth ? <div className={`calendar-cell${dayTasks.length ? ' has-task' : ''}`} key={index}><span>{day}</span>{dayTasks.map((task) => <strong key={task.id}>{task.title}</strong>)}</div> : <div className="calendar-cell empty" key={index} /> })}</div>{undated.length > 0 && <aside className="calendar-unscheduled"><h3>未安排具体日期</h3><p>这些行动不会被随意塞进某一天。</p><div>{undated.map((task) => <span key={task.id}><strong>{task.title}</strong><small>{task.due}</small></span>)}</div></aside>}</section>
}

function FootprintView({ tasks }: { tasks: JourneyItem[] }) {
  const done = tasks.filter((task) => task.state === '已完成')
  return <section className="footprint-board"><header><p className="eyebrow">Footprints</p><h2>真实行动留下的足迹</h2><p>这里只记录已经发生的事，不用完成率替你定义进展。</p></header>{done.length === 0 ? <div className="state-panel glass-card"><Footprints size={34} /><h3>第一枚足迹还在路上</h3><p>完成一个真实行动后，这里才会出现记录；不会用空卡片催促你。</p></div> : done.map((task) => <article className="footprint-card glass-card" key={task.id}><CheckCircle size={24} weight="fill" /><div><strong>{task.title}</strong><p>{task.reflection || '你推进了这一小步。之后可以在对话里回看，它改变了什么。'}</p></div></article>)}</section>
}

function parseJourneyDate(value: string): Date | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim())
  if (!match) return null
  const year = Number(match[1])
  const month = Number(match[2]) - 1
  const day = Number(match[3])
  const date = new Date(year, month, day)
  return date.getFullYear() === year && date.getMonth() === month && date.getDate() === day ? date : null
}
