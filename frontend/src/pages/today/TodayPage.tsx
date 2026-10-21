import { Link } from 'react-router-dom'
import { demoHypotheses, demoJourney } from '../../data/demoRepository'

export function TodayPage() {
  return (
    <section className="today-layout">
      <div className="glass-card today-greeting">
        <p className="eyebrow">今天</p>
        <h1 className="page-title">早上好，今天想从哪里继续？</h1>
        <p className="muted">写下一点想法，或者告诉我你现在的感受……</p>
        <Link to="/chat" className="primary-button">
          开始对话
        </Link>
      </div>

      <div className="today-grid">
        <div className="glass-card today-card">
          <p className="eyebrow">今日航向</p>
          <h2 className="card-title">今日航向</h2>
          <ul className="journey-list">
            {demoJourney.map((item) => (
              <li key={item.id} className="journey-item">
                <span className={`state state-${item.state}`}>{item.state}</span>
                <div className="journey-body">
                  <div className="journey-title">{item.title}</div>
                  <div className="journey-meta">{item.related} · {item.due}</div>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="glass-card today-card hypothesis-card">
          <p className="eyebrow">我的猜想</p>
          <h2 className="card-title">我的猜想</h2>
          <ul className="hypothesis-list">
            {demoHypotheses.map((h) => (
              <li key={h.id} className="hypothesis-item">
                <div className="hypothesis-statement">{h.statement}</div>
                <div className="hypothesis-meta">
                  把握 {h.confidence} · {h.status}
                </div>
                <div className="hypothesis-actions">
                  <button type="button">确认</button>
                  <button type="button">暂不确定</button>
                  <button type="button">驳回</button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="glass-card today-card">
          <p className="eyebrow">离线反思</p>
          <h2 className="card-title">昨夜的 Dreaming</h2>
          <p className="muted">让零散想法在夜里慢慢相遇。</p>
          <p className="muted">
            4 条证据 · 稳定感和创造性不一定互相排斥。
          </p>
          <Link to="/dreaming" className="text-link">查看完整离线反思</Link>
        </div>
      </div>
    </section>
  )
}
