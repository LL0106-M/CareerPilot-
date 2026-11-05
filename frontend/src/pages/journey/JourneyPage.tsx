import { ArrowRight, Bell, CalendarBlank, CheckCircle, CloudArrowUp, Footprints, Path, Plus, Sparkle, VideoCamera } from '@phosphor-icons/react'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../data/api'
import type { ActionPreview, FutureLetter, KnowledgeCollectionJob } from '../../data/api'
import type { JourneyItem } from '../../data/types'
import { useDashboard } from '../../hooks/useDashboard'
import './journey-calendar.css'
import { FutureLetterPanel } from './FutureLetterPanel'

type ViewMode = 'path' | 'calendar' | 'footprints'

export function JourneyPage() {
  const { data, error, loading, reload } = useDashboard()
  const [view, setView] = useState<ViewMode>('path')
  const [active, setActive] = useState(0)
  const [status, setStatus] = useState('')
  const [previewOpen, setPreviewOpen] = useState(false)
  const [syncTask, setSyncTask] = useState<JourneyItem>()
  const [actionPreview, setActionPreview] = useState<ActionPreview>()
  const [actionState, setActionState] = useState<'idle' | 'previewing' | 'confirming' | 'done' | 'error'>('idle')
  const [actionError, setActionError] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [createState, setCreateState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [futureLetter, setFutureLetter] = useState<FutureLetter>()
  const [futureState, setFutureState] = useState<'idle' | 'loading' | 'error'>('idle')
  const [companySelection, setCompanySelection] = useState('')
  const [branchSelection, setBranchSelection] = useState('')
  const [branchConfirm, setBranchConfirm] = useState<string>()
  const [branchState, setBranchState] = useState<'idle' | 'saving' | 'error'>('idle')
  const groups = useMemo(() => groupJourneys(data?.journey || [], data?.journeys || []), [data])
  const current = groups[active]
  const currentBranches = (data?.journey_branches || []).filter(
    (branch) => current?.journeyIds.includes(branch.journey_id),
  )
  const targetBranches = currentBranches.filter((branch) => branch.kind === 'target')
  const companies = unique(targetBranches.map(branchCompany))
  const activeCompany = companies.includes(companySelection) ? companySelection : companies[0] || ''
  const companyBranches = targetBranches.filter((branch) => branchCompany(branch) === activeCompany)
  const activeBranchId = companyBranches.some((branch) => branch.id === branchSelection)
    ? branchSelection
    : companyBranches[0]?.id || ''
  const selectedBranch = companyBranches.find((branch) => branch.id === activeBranchId)
  const visibleTasks = !current ? [] : selectedBranch
    ? current.tasks.filter((task) => task.scope !== 'branch_specific' || task.journey_branch_id === selectedBranch.id)
    : current.tasks.filter((task) => task.scope !== 'branch_specific')
  const visibleGroup = current ? { ...current, tasks: visibleTasks } : undefined
  const currentJobs = (data?.collection_jobs || []).filter(
    (job) => current?.directionIds.includes(job.direction_id),
  )

  useEffect(() => scheduleBrowserReminders(data?.journey || []), [data?.journey])
  useEffect(() => {
    setCompanySelection('')
    setBranchSelection('')
  }, [active])

  async function activateBranch() {
    if (!selectedBranch || !branchConfirm) return
    setBranchState('saving')
    try {
      await api.activateJourneyBranch(selectedBranch.journey_id, branchConfirm)
      await reload()
      setBranchSelection(branchConfirm)
      setBranchConfirm(undefined)
      setBranchState('idle')
    } catch {
      setBranchState('error')
    }
  }

  async function advance(task: JourneyItem) {
    const next: JourneyItem['state'] = task.state === '准备开始' ? '进行中' : task.state === '进行中' ? '已完成' : task.state
    if (next === task.state) return
    setStatus('saving')
    try { await api.updateJourneyTask(task.id, next); await reload(); setStatus('saved') }
    catch { setStatus('error') }
  }

  async function generatePreview() {
    const task = syncTask || visibleGroup?.tasks.find((item) => item.state !== '已完成') || visibleGroup?.tasks[0]
    if (!task) return
    setActionState('previewing'); setActionError('')
    const start = task.start_at ? new Date(task.start_at) : new Date(Date.now() + 24 * 60 * 60 * 1000)
    if (!task.start_at) start.setHours(19, 0, 0, 0)
    const end = task.end_at ? new Date(task.end_at) : new Date(start.getTime() + 45 * 60 * 1000)
    try {
      const preview = await api.previewAction('feishu', 'calendar.create', {
        summary: task.title,
        start: task.start_at || start.toISOString(),
        end: task.end_at || end.toISOString(),
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

  async function createEvent(input: CalendarFormValue) {
    setCreateState('saving')
    try {
      await api.createJourneyEvent({
        title: input.title,
        start_at: localDateTimeToOffsetIso(input.startAt),
        reminder_minutes: input.reminderMinutes || undefined,
        meeting_url: input.meetingUrl || undefined,
        notes: input.notes || undefined,
      })
      setCreateState('saved')
      setCreateOpen(false)
      setView('calendar')
    } catch {
      setCreateState('error')
      return
    }
    if (input.reminderMinutes > 0) {
      try { await requestNotificationPermission() } catch { /* saved locally already */ }
    }
    try { await reload() } catch { /* saved locally already */ }
  }

  function openExternalPreview(task: JourneyItem) {
    setSyncTask(task)
    setActionPreview(undefined)
    setActionState('idle')
    setActionError('')
    setPreviewOpen(true)
  }

  async function openFutureLetter(journeyId: string) {
    setFutureState('loading')
    try {
      setFutureLetter(await api.generateFutureLetter(journeyId))
      setFutureState('idle')
    } catch {
      setFutureState('error')
    }
  }

  return (
    <div className="journey-experience">
      <header className="journey-hero"><div><p className="eyebrow">Journey</p><h1>不是更多待办，<br />而是一段正在发生的路。</h1></div><div className="journey-header-actions"><button type="button" className="primary-button" onClick={() => { setCreateOpen(true); setCreateState('idle') }}><Plus /> 添加日程</button><div className="journey-view-switch glass-strong">{([['path','航线',Path],['calendar','日历',CalendarBlank],['footprints','足迹',Footprints]] as const).map(([key,label,Icon]) => <button type="button" key={key} className={view === key ? 'active' : ''} onClick={() => setView(key)}><Icon />{label}</button>)}</div></div></header>
      {loading && <div className="state-panel glass-card">正在展开你的航程……</div>}
      {error && <div className="state-panel glass-card error">{error}<button type="button" onClick={() => void reload()}>重试</button></div>}
      {!loading && !error && groups.length === 0 && <div className="state-panel glass-card"><Path size={38} /><h2>路还没有开始画</h2><p>从罗盘里选一条猜想，用一个真实行动去验证。</p><Link className="primary-button" to="/compass">去罗盘看看</Link></div>}
      {groups.length > 0 && <>
        <nav className="journey-selector" aria-label="选择岗位方向">{groups.map((group,index) => <button type="button" className={active === index ? 'active' : ''} onClick={() => setActive(index)} key={group.id}><span>{String(index + 1).padStart(2,'0')}</span>{group.name}</button>)}</nav>
        {targetBranches.length > 0 && <section className="journey-target-navigation" aria-label="航程目标层级">
          <nav className="journey-company-selector" aria-label="选择目标公司">{companies.map((company) => <button type="button" className={activeCompany === company ? 'active' : ''} onClick={() => { setCompanySelection(company); setBranchSelection(targetBranches.find((branch) => branchCompany(branch) === company)?.id || '') }} key={company}>{company}</button>)}</nav>
          <nav className="journey-business-selector" aria-label="选择业务线">{companyBranches.map((branch) => <button type="button" aria-label={branchBusiness(branch)} className={activeBranchId === branch.id ? 'active' : ''} onClick={() => setBranchSelection(branch.id)} key={branch.id}>{branchBusiness(branch)}{branch.status === 'draft' && <small>待开始</small>}</button>)}</nav>
          {selectedBranch && <p className="journey-context" aria-label="当前航程目标"><strong>{current?.name}</strong><span>/</span><strong>{activeCompany}</strong><span>/</span><strong>{branchBusiness(selectedBranch)}</strong></p>}
        </section>}
        {view === 'path' && currentJobs.length > 0 && <CollectionProgress jobs={currentJobs} />}
        {view === 'path' && selectedBranch?.status === 'draft' && <section className="draft-branch-panel glass-strong"><p className="eyebrow">Target branch</p><h2>{activeCompany} · {branchBusiness(selectedBranch)}</h2><strong>尚未开始准备</strong><p>{selectedBranch.rationale}</p><p>岗位方向的基础行动会自动复用；确认后只增加这个目标特有的行动。</p><button type="button" className="primary-button" onClick={() => { setBranchState('idle'); setBranchConfirm(selectedBranch.id) }}>开始准备这个目标</button></section>}
        {view === 'path' && visibleGroup && selectedBranch?.status !== 'draft' && <PathView group={visibleGroup} onAdvance={advance} onPreview={openExternalPreview} onFutureLetter={openFutureLetter} futureState={futureState} futureLetter={futureLetter} />}
        {view === 'calendar' && <CalendarView tasks={visibleTasks} onSync={openExternalPreview} />}
        {view === 'footprints' && <FootprintView tasks={visibleTasks} />}
        <p className="mutation-note center" aria-live="polite">{status === 'saving' ? '正在推进……' : status === 'saved' ? '航程已更新。' : status === 'error' ? '这次没有更新成功。' : ''}</p>
      </>}
      {createState === 'saved' && <p className="action-success journey-save-message" role="status">日程已保存到 CareerPilot。</p>}
      {createState === 'error' && <p className="chat-error journey-save-message" role="alert">日程没有保存成功，请重试。</p>}
      {createOpen && <CalendarCreateDialog onClose={() => setCreateOpen(false)} onSave={createEvent} saving={createState === 'saving'} />}
      {branchConfirm && <div className="modal-backdrop"><div className="modal-panel glass-strong" role="dialog" aria-modal="true" aria-label="确认开始目标分支"><Path size={28} /><h2>开始准备这个目标？</h2><p>只会新增目标差异行动，通用主线不会复制。</p>{branchState === 'error' && <p className="chat-error" role="alert">这次没有开始成功，请重试。</p>}<div className="modal-actions"><button type="button" className="text-button" onClick={() => setBranchConfirm(undefined)} disabled={branchState === 'saving'}>取消</button><button type="button" className="primary-button" onClick={() => void activateBranch()} disabled={branchState === 'saving'}>{branchState === 'saving' ? '正在开始…' : '确认开始准备'}</button></div></div></div>}
      {previewOpen && <div className="modal-backdrop"><div className="modal-panel glass-strong" role="dialog" aria-modal="true" aria-label="确认调用外部应用"><CloudArrowUp size={28} /><h2>先预览，再交给其他应用</h2><p>CareerPilot 会先生成操作预览。你确认内容和目标应用后，才会真正执行。</p><div className="preview-row"><span>目标</span><strong>飞书日历</strong></div><div className="preview-row"><span>内容</span><strong>{current?.tasks[0]?.title}</strong></div>{actionPreview && <div className="action-confirmation"><p className="eyebrow">等待你的最终确认</p><small>预览已由后端生成；只有点击确认后才会写入外部应用。</small></div>}{actionState === 'done' && <p className="action-success">已交给飞书日历。</p>}{actionError && <p className="chat-error" role="alert">{actionError}</p>}<div className="modal-actions"><button className="text-button" type="button" onClick={() => { setPreviewOpen(false); setActionPreview(undefined); setActionState('idle'); setActionError('') }}>关闭</button>{!actionPreview && actionState !== 'done' && <button className="primary-button" type="button" onClick={() => void generatePreview()} disabled={actionState === 'previewing'}>{actionState === 'previewing' ? '正在生成…' : '生成预览'}</button>}{actionPreview && actionState !== 'done' && <button className="primary-button" type="button" onClick={() => void confirmAndApply()} disabled={actionState === 'confirming'}>{actionState === 'confirming' ? '正在执行…' : '确认并创建日程'}</button>}</div></div></div>}
    </div>
  )
}

function CollectionProgress({ jobs }: { jobs: KnowledgeCollectionJob[] }) {
  const purpose = {
    job_opportunity: '岗位信息',
    interview_archive: '往年题目',
    learning_resource: '学习资源',
  }
  const status = {
    queued: '等待收集',
    collecting: '收集中',
    completed: '已完成',
    partial: '部分完成',
    failed: '暂时失败',
  }
  return <section className="collection-progress" aria-label="航程资料收集状态">{jobs.map((job) => <article className={`collection-status-card status-${job.status}`} key={job.id}><span>{purpose[job.purpose]} · {status[job.status]}</span></article>)}</section>
}

function groupJourneys(tasks: JourneyItem[], journeys: Array<{ id: string; direction_id?: string; title: string }>) {
  type Group = { id: string; name: string; journeyIds: string[]; directionIds: string[]; tasks: JourneyItem[] }
  const result = new Map<string, Group>()
  const journeyById = new Map(journeys.map((journey) => [journey.id, journey]))
  journeys.forEach((journey) => {
    const key = normalizeJourneyName(journey.title)
    const group = result.get(key)
    if (group) {
      group.journeyIds.push(journey.id)
      if (journey.direction_id && !group.directionIds.includes(journey.direction_id)) group.directionIds.push(journey.direction_id)
    } else {
      result.set(key, {
        id: journey.id,
        name: journey.title,
        journeyIds: [journey.id],
        directionIds: journey.direction_id ? [journey.direction_id] : [],
        tasks: [],
      })
    }
  })
  tasks.forEach((task) => {
    const journey = task.journey_id ? journeyById.get(task.journey_id) : undefined
    const name = journey?.title || task.related || '未命名航程'
    const key = normalizeJourneyName(name)
    let group = result.get(key)
    if (!group) {
      const id = task.journey_id || `legacy:${name}`
      group = { id, name, journeyIds: [id], directionIds: [], tasks: [] }
      result.set(key, group)
    }
    if (task.journey_id && !group.journeyIds.includes(task.journey_id)) group.journeyIds.push(task.journey_id)
    if (task.direction_id && !group.directionIds.includes(task.direction_id)) group.directionIds.push(task.direction_id)
    const duplicateIndex = task.scope !== 'branch_specific' && task.step_kind
      ? group.tasks.findIndex((item) => item.scope !== 'branch_specific' && item.step_kind === task.step_kind)
      : -1
    if (duplicateIndex < 0) group.tasks.push(task)
    else if (task.journey_id === group.id) group.tasks[duplicateIndex] = task
  })
  return Array.from(result.values()).filter((group) => group.tasks.length > 0)
}

function normalizeJourneyName(value: string) {
  return value.toLocaleLowerCase('zh-CN').replace(/\s+/g, '')
}

function unique(values: string[]) {
  return values.filter((value, index) => value && values.indexOf(value) === index)
}

function branchCompany(branch: { company?: string; title: string }) {
  return branch.company?.trim() || branch.title.split('｜')[0]?.trim() || '目标公司待确认'
}

function branchBusiness(branch: { business?: string; role?: string; title: string }) {
  return branch.business?.trim() || branch.title.split('｜')[1]?.trim() || branch.role?.trim() || '业务线待确认'
}

function PathView({ group, onAdvance, onPreview, onFutureLetter, futureState, futureLetter }: { group: { name: string; tasks: JourneyItem[] }; onAdvance: (task: JourneyItem) => void; onPreview: (task: JourneyItem) => void; onFutureLetter: (journeyId: string) => void; futureState: 'idle' | 'loading' | 'error'; futureLetter?: FutureLetter }) {
  const focus = group.tasks.find((task) => task.state === '进行中') || group.tasks.find((task) => task.state === '准备开始') || group.tasks[0]
  const journeyId = focus.journey_id
  return <section className="journey-path"><div className="journey-path-main"><aside className="journey-story glass-card"><p className="eyebrow">Why this journey</p><h2>{group.name}</h2><p>{focus.why || '用一次真实行动补充证据，而不是只靠想象判断方向。'}</p><div className="next-milestone"><Sparkle weight="fill" /><span>下一节点</span><strong>{focus.due}</strong></div></aside><article className="focus-action glass-strong"><span className={`state state-${focus.state}`}>{focus.state}</span><p className="eyebrow">One focus action</p><h2>{focus.title}</h2><p>现在只需要看这一件。其他动作仍在航线上，但不会同时占据你的注意力。</p><div className="focus-actions"><button type="button" className="primary-button" onClick={() => void onAdvance(focus)} disabled={focus.state === '已完成'}>{focus.state === '准备开始' ? '开始这一步' : focus.state === '进行中' ? '完成并留下足迹' : '已经完成'} <ArrowRight /></button><button type="button" className="secondary-button" onClick={() => onPreview(focus)}><CloudArrowUp /> 调用其他 App</button></div>{journeyId && <button type="button" className="text-button future-letter-trigger" onClick={() => void onFutureLetter(journeyId)} disabled={futureState === 'loading'}>{futureState === 'loading' ? '正在等未来回信…' : '给未来的我写一句话'}</button>}{futureState === 'error' && <p className="chat-error" role="alert">未来回信暂时没有寄到，请稍后再试。</p>}</article></div>{futureLetter && futureLetter.journey_id === journeyId && <FutureLetterPanel letter={futureLetter} />}<ol className="journey-route">{group.tasks.map((task,index) => <li className={`route-step state-${task.state}`} key={task.id}><span>{index + 1}</span><div><strong>{task.title}</strong><small>{task.state}</small></div></li>)}</ol></section>
}

function CalendarView({ tasks, onSync }: { tasks: JourneyItem[]; onSync: (task: JourneyItem) => void }) {
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
  return <section className="calendar-board glass-card"><header><div><p className="eyebrow">Calendar · 所有航程</p><div className="calendar-month-nav"><button type="button" aria-label="上个月" onClick={() => setMonth(new Date(year, monthIndex - 1, 1))}>‹</button><h2>{year} 年 {monthIndex + 1} 月</h2><button type="button" aria-label="下个月" onClick={() => setMonth(new Date(year, monthIndex + 1, 1))}>›</button></div></div><p>对话和手动添加都会保存在这里；飞书是可选同步，不影响本地日程。</p></header><div className="calendar-grid">{['一','二','三','四','五','六','日'].map((day) => <div className="calendar-head" key={day}>{day}</div>)}{Array.from({length:cellCount},(_,index) => { const day = index - leading + 1; const dayTasks = tasksByDay.get(day) || []; return day > 0 && day <= daysInMonth ? <div className={`calendar-cell${dayTasks.length ? ' has-task' : ''}`} key={index}><span>{day}</span>{dayTasks.map((task) => <CalendarEvent task={task} onSync={onSync} key={task.id} />)}</div> : <div className="calendar-cell empty" key={index} /> })}</div>{undated.length > 0 && <aside className="calendar-unscheduled"><h3>未安排具体日期</h3><p>这些行动不会被随意塞进某一天。</p><div>{undated.map((task) => <span key={task.id}><strong>{task.title}</strong><small>{task.due}</small></span>)}</div></aside>}</section>
}

function CalendarEvent({ task, onSync }: { task: JourneyItem; onSync: (task: JourneyItem) => void }) {
  const start = task.start_at ? new Date(task.start_at) : null
  return <article className="calendar-event"><strong>{task.title}</strong>{start && <small>{start.toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'})}</small>}{typeof task.reminder_minutes === 'number' && task.reminder_minutes > 0 && <small><Bell /> 提前 {task.reminder_minutes} 分钟提醒</small>}{task.meeting_url && <a href={task.meeting_url} target="_blank" rel="noreferrer"><VideoCamera /> 加入腾讯会议</a>}{task.start_at && <button type="button" className="text-button" aria-label={`同步“${task.title}”到飞书`} onClick={() => onSync(task)}><CloudArrowUp /> 同步飞书</button>}</article>
}

type CalendarFormValue = { title: string; startAt: string; reminderMinutes: number; meetingUrl: string; notes: string }

function localDateTimeToOffsetIso(value: string) {
  const local = new Date(value)
  const offset = -local.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const hours = String(Math.floor(Math.abs(offset) / 60)).padStart(2,'0')
  const minutes = String(Math.abs(offset) % 60).padStart(2,'0')
  const withSeconds = value.length === 16 ? `${value}:00` : value
  return `${withSeconds}${sign}${hours}:${minutes}`
}

function CalendarCreateDialog({ onClose, onSave, saving }: { onClose: () => void; onSave: (value: CalendarFormValue) => void; saving: boolean }) {
  const [value,setValue] = useState<CalendarFormValue>({ title:'',startAt:'',reminderMinutes:0,meetingUrl:'',notes:'' })
  return <div className="modal-backdrop"><form className="modal-panel calendar-create-form glass-strong" role="dialog" aria-modal="true" aria-label="添加日程" onSubmit={(event) => { event.preventDefault(); void onSave(value) }}><CalendarBlank size={28} /><h2>添加到 CareerPilot 日历</h2><p>日程先保存在这里，之后可选择同步到飞书。</p><label>日程标题<input aria-label="日程标题" required value={value.title} onChange={(event) => setValue({...value,title:event.target.value})} /></label><label>开始时间<input aria-label="开始时间" type="datetime-local" required value={value.startAt} onChange={(event) => setValue({...value,startAt:event.target.value})} /></label><label>提醒时间<select aria-label="提醒时间" value={value.reminderMinutes} onChange={(event) => setValue({...value,reminderMinutes:Number(event.target.value)})}><option value="0">不提醒</option><option value="10">提前 10 分钟</option><option value="30">提前 30 分钟</option><option value="60">提前 1 小时</option><option value="1440">提前 1 天</option></select></label><label>腾讯会议链接（可选）<input aria-label="腾讯会议链接" type="url" placeholder="https://meeting.tencent.com/..." value={value.meetingUrl} onChange={(event) => setValue({...value,meetingUrl:event.target.value})} /></label><label>备注（可选）<textarea aria-label="备注" value={value.notes} onChange={(event) => setValue({...value,notes:event.target.value})} /></label><div className="modal-actions"><button type="button" className="text-button" onClick={onClose}>取消</button><button type="submit" className="primary-button" disabled={saving}>{saving ? '正在保存…' : '保存到 CareerPilot'}</button></div></form></div>
}

async function requestNotificationPermission() {
  if (typeof Notification === 'undefined' || Notification.permission !== 'default') return
  await Notification.requestPermission()
}

function scheduleBrowserReminders(tasks: JourneyItem[]) {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return undefined
  const timers = tasks.flatMap((task) => {
    if (!task.start_at || !task.reminder_minutes) return []
    const delay = new Date(task.start_at).getTime() - task.reminder_minutes * 60_000 - Date.now()
    if (delay <= 0 || delay > 2_147_000_000) return []
    return [window.setTimeout(() => new Notification(task.title,{body: task.meeting_url ? '日程即将开始，腾讯会议链接已准备好。' : '日程即将开始。'}),delay)]
  })
  return () => timers.forEach((timer) => window.clearTimeout(timer))
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
