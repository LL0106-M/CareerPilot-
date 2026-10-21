import { demoHypotheses } from '../../data/demoRepository'
import type { CareerHypothesis } from '../../data/types'

const SECTIONS = [
  { key: 'interests', label: '兴趣与好奇', icon: '✨' },
  { key: 'strengths', label: '能力与经历', icon: '🎯' },
  { key: 'environment', label: '工作环境偏好', icon: '🏔️' },
  { key: 'risks', label: '风险与顾虑', icon: '⛰️' },
  { key: 'directions', label: '候选职业方向', icon: '🧭' },
] as const

type SectionKey = (typeof SECTIONS)[number]['key']

interface CompassEntry {
  id: string
  section: SectionKey
  text: string
  status: '已确认' | 'Agent 猜想' | '存在矛盾' | '等待验证'
}

const demoEntries: CompassEntry[] = [
  { id: 'c1', section: 'interests', text: '对 AI 产品的落地应用持续感兴趣', status: '已确认' },
  { id: 'c2', section: 'interests', text: '喜欢把模糊想法整理成清晰结构', status: '已确认' },
  { id: 'c3', section: 'strengths', text: '有完整的产品项目经历和作品集', status: '已确认' },
  { id: 'c4', section: 'strengths', text: '善于跨团队沟通并推动执行', status: '等待验证' },
  { id: 'c5', section: 'environment', text: '希望有清晰边界但保留创造空间', status: 'Agent 猜想' },
  { id: 'c6', section: 'environment', text: '不喜欢完全重复的工作', status: '已确认' },
  { id: 'c7', section: 'risks', text: '担心准备不足导致错失机会', status: '存在矛盾' },
  { id: 'c8', section: 'risks', text: '对"稳定"和"创造"能否兼得存疑', status: '等待验证' },
  { id: 'c9', section: 'directions', text: '国央企产品岗位', status: 'Agent 猜想' },
  { id: 'c10', section: 'directions', text: 'AI 产品经理（民营企业）', status: '已确认' },
]

const STATUS_COLOR: Record<CompassEntry['status'], string> = {
  '已确认': 'status-enabled',
  'Agent 猜想': 'status-hypothesis',
  '存在矛盾': 'status-conflict',
  '等待验证': 'status-waiting',
}

export function CompassPage() {
  return (
    <div className="compass-layout">
      <section className="glass-card compass-header">
        <p className="eyebrow">罗盘</p>
        <h1 className="page-title">你现在对自己的职业版图知道些什么</h1>
        <p className="muted">
          这里不追求一张完美的知识图谱。先把目前能确认的、还在猜的、互相矛盾的摊开来看。
        </p>
      </section>

      <div className="compass-grid">
        {SECTIONS.map((section) => {
          const entries = demoEntries.filter((e) => e.section === section.key)
          return (
            <section key={section.key} className="glass-card compass-section">
              <div className="section-head">
                <span className="section-icon">{section.icon}</span>
                <h2 className="card-title">{section.label}</h2>
                <span className="section-count">{entries.length}</span>
              </div>
              <ul className="compass-entry-list">
                {entries.map((entry) => (
                  <li key={entry.id} className="compass-entry">
                    <div className="entry-text">{entry.text}</div>
                    <span className={`entry-status ${STATUS_COLOR[entry.status]}`}>
                      {entry.status}
                    </span>
                  </li>
                ))}
                {entries.length === 0 && (
                  <li className="empty-row muted">还没有内容。对话里慢慢会浮出来的。</li>
                )}
              </ul>
            </section>
          )
        })}
      </div>

      <section className="glass-card compass-hypotheses">
        <div className="section-head">
          <span className="section-icon">💡</span>
          <h2 className="card-title">待验证猜想</h2>
        </div>
        <ul className="hypothesis-detail-list">
          {demoHypotheses.map((h) => (
            <li key={h.id} className="hypothesis-detail glass-card">
              <div className="hypothesis-statement">{h.statement}</div>
              <div className="hypothesis-meta">把握 {h.confidence} · {h.status}</div>
              <div className="hypothesis-evidence">
                <div className="evidence-sub">支持证据</div>
                <ul>
                  {h.evidence.map((e) => <li key={e}>{e}</li>)}
                </ul>
              </div>
              <div className="hypothesis-actions">
                <button type="button" className="secondary-button">确认</button>
                <button type="button" className="text-button">修改</button>
                <button type="button" className="text-button">驳回</button>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
