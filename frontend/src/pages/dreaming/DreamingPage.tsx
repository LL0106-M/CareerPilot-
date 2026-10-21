import { demoDreams } from '../../data/demoRepository'

export function DreamingPage() {
  return (
    <section className="glass-card dreaming-page">
      <p className="eyebrow">Dreaming</p>
      <h1 className="page-title">让零散想法在夜里慢慢相遇</h1>
      <p className="muted">
        泊泊会把最近的对话、知识库和猜想安静地放一起，看看它们有没有新的联系。
      </p>

      <ul className="dreaming-list">
        {demoDreams.map((dream) => (
          <li key={dream.id} className="dream-item glass-card">
            <div className="dream-head">
              <span className="dream-date">{dream.date}</span>
              <span className={`dream-status dream-status-${dream.status}`}>
                {dream.status}
              </span>
            </div>
            <h2 className="dream-title">{dream.title}</h2>
            <p className="dream-summary">{dream.summary}</p>
            <p className="dream-evidence">
              {dream.evidenceCount} 条证据支持这一观察。
            </p>
            <div className="dream-actions">
              <button type="button">确认猜想</button>
              <button type="button">继续观察</button>
              <button type="button">驳回</button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
