import { useState } from 'react'
import { demoJourney } from '../../data/demoRepository'
import type { JourneyItem } from '../../data/types'

type ViewMode = 'week' | 'calendar' | 'done'

const STATE_LABEL: Record<JourneyItem['state'], string> = {
  '准备开始': '准备开始',
  '进行中': '进行中',
  '等待结果': '等待结果',
  '已完成': '已完成',
}

export function JourneyPage() {
  const [view, setView] = useState<ViewMode>('week')

  const items =
    view === 'done'
      ? demoJourney.filter((j) => j.state === '已完成')
      : demoJourney

  return (
    <div className="journey-layout">
      <section className="glass-card journey-header">
        <p className="eyebrow">航程</p>
        <h1 className="page-title">把想法变成具体行动</h1>
        <p className="muted">
          这里列的不是待办清单，而是每一条背后都有"为什么要做"和"关联哪个岗位或猜想"。
        </p>

        <div className="journey-tabs">
          {(['week', 'calendar', 'done'] as const).map((m) => (
            <button
              key={m}
              type="button"
              className={`journey-tab${view === m ? ' active' : ''}`}
              onClick={() => setView(m)}
            >
              {m === 'week' ? '本周' : m === 'calendar' ? '日历' : '已完成'}
            </button>
          ))}
        </div>
      </section>

      <section className="journey-main">
        {view === 'calendar' ? <CalendarView /> : <TaskList items={items} />}
      </section>
    </div>
  )
}

function TaskList({ items }: { items: JourneyItem[] }) {
  return (
    <ul className="journey-task-list">
      {items.map((item) => (
        <li key={item.id} className="journey-task glass-card">
          <div className="task-head">
            <span className={`state state-${item.state}`}>{STATE_LABEL[item.state]}</span>
            <span className="task-due">截止 {item.due}</span>
          </div>
          <div className="task-title">{item.title}</div>
          <div className="task-related">关联：{item.related}</div>
          <div className="task-why">
            <div className="muted task-why-label">为什么要做</div>
            验证自己对工作节奏的真实感受，帮助判断"稳定"和"创造"能不能兼得。
          </div>
          <div className="task-review">
            <div className="muted task-why-label">完成后的复盘问题</div>
            做完这件事之后，我对原来的想法有什么变化？
          </div>
          <div className="task-actions">
            <button type="button" className="secondary-button">标记推进</button>
            <button type="button" className="text-button">编辑</button>
          </div>
        </li>
      ))}
      {items.length === 0 && (
        <li className="empty-row glass-card">
          这里暂时没有任务。和泊泊聊聊你最近想做什么，它会帮你拆成航程。
        </li>
      )}
    </ul>
  )
}

function CalendarView() {
  const days = ['一', '二', '三', '四', '五', '六', '日']
  const highlights: Record<number, string> = { 15: '进行中', 22: '即将截止', 28: '等待结果' }
  return (
    <section className="glass-card calendar-panel">
      <h2 className="card-title">十月 2026</h2>
      <div className="calendar-grid">
        {days.map((d) => (
          <div key={d} className="calendar-head muted">{d}</div>
        ))}
        {Array.from({ length: 35 }, (_, i) => {
          const day = i - 1 // offset to make Mon=1
          if (day <= 0 || day > 31) return <div key={i} className="calendar-cell empty" />
          const label = highlights[day]
          return (
            <div key={i} className={`calendar-cell${label ? ' has-task' : ''}`}>
              <div className="calendar-day">{day}</div>
              {label && <div className={`calendar-dot state-${label}`}>{label}</div>}
            </div>
          )
        })}
      </div>
      <p className="muted" style={{ marginTop: 16 }}>日历视图会和航程任务联动，点击某一天可以看到当天需要做的事。</p>
    </section>
  )
}
