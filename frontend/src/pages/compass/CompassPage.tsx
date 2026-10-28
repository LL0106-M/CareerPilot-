import { ArrowDown, ArrowLeft, ArrowRight, Check, Compass, Lightbulb, Path, Sparkle } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../data/api'
import { useDashboard } from '../../hooks/useDashboard'

export function CompassPage() {
  const { data, error, loading, reload } = useDashboard()
  const [index, setIndex] = useState(0)
  const [mutation, setMutation] = useState('')
  const [ideaMutation, setIdeaMutation] = useState('')
  const hypotheses = data?.hypotheses || []
  const current = hypotheses[index]
  const ideas = data?.ideas || []
  const confirmed = useMemo(() => hypotheses.filter((item) => item.status === '已确认').length, [hypotheses])

  async function decide(decision: 'confirm' | 'uncertain') {
    if (!current) return
    setMutation('saving')
    try { await api.decideHypothesis(current.id, decision); await reload(); setMutation('saved') }
    catch { setMutation('error') }
  }

  async function verify() {
    if (!current) return
    setMutation('saving')
    try { await api.createVerificationTask(current.id); setMutation('task') }
    catch { setMutation('error') }
  }

  async function verifyIdea(id: string) {
    setIdeaMutation(`saving:${id}`)
    try { await api.createIdeaVerificationTask(id); setIdeaMutation(`saved:${id}`) }
    catch { setIdeaMutation(`error:${id}`) }
  }

  return (
    <div className="compass-experience">
      <section className="compass-focus glass-card">
        <div className="compass-intro"><p className="eyebrow">Compass · Career explorations</p><h1>现在，哪一种方向<br />值得你靠近一点？</h1><p>不用先想出完整答案。每次只看一个方向，再决定要不要用现实行动验证它。</p><div className="compass-progress"><span>{confirmed} 条已确认</span><span>{hypotheses.length} 条正在形成</span></div><a href="#idea-field" className="soft-link dark">继续看那些还没成形的想法 <ArrowDown /></a></div>
        <div className="direction-stage">
          {loading && <div className="state-panel">泊泊正在整理最近的线索……</div>}
          {error && <div className="state-panel error"><span>{error}</span><button type="button" onClick={() => void reload()}>重试</button></div>}
          {!loading && !error && !current && <div className="state-panel"><Compass size={36} weight="duotone" /><h2>罗盘还没有方向</h2><p>先去聊一会儿。泊泊会从你的表达里形成可确认的方向。</p><Link to="/chat" className="primary-button">去对话</Link></div>}
          {current && <article className="direction-card glass-strong"><div className="direction-index">{String(index + 1).padStart(2,'0')} / {String(hypotheses.length).padStart(2,'0')}</div><span className="direction-status">{current.status}</span><h2>{current.statement || current.content}</h2><p>这不是结论，而是一条可以被现实修正的职业猜想。</p>{current.evidence && current.evidence.length > 0 && <div className="evidence-strip">{current.evidence.slice(0,3).map((item) => <span key={item}>{item}</span>)}</div>}<div className="direction-actions"><button type="button" className="primary-button" onClick={() => void decide('confirm')}><Check /> 这很像我</button><button type="button" className="secondary-button" onClick={() => void verify()}><Path /> 用一次行动验证</button><button type="button" className="text-button" onClick={() => void decide('uncertain')}>先继续观察</button></div><p className="mutation-note" aria-live="polite">{mutation === 'saving' ? '正在更新……' : mutation === 'saved' ? '已写入你的罗盘。' : mutation === 'task' ? '验证行动已加入航程。' : mutation === 'error' ? '没有更新成功，请重试。' : ''}</p></article>}
          {hypotheses.length > 1 && <div className="direction-nav"><button type="button" aria-label="上一个方向" onClick={() => setIndex((index - 1 + hypotheses.length) % hypotheses.length)}><ArrowLeft /></button><button type="button" aria-label="下一个方向" onClick={() => setIndex((index + 1) % hypotheses.length)}><ArrowRight /></button></div>}
        </div>
      </section>

      <section className="idea-field" id="idea-field"><header><div><p className="eyebrow">Thought fragments</p><h2>有些想法，先让它们散落着。</h2></div><p>它们不需要马上变成方向。靠近其中一张，决定是否用一个小行动看看它会走向哪里。</p></header><div className="idea-cloud">{ideas.length === 0 ? <div className="empty-ideas glass-card"><Lightbulb size={28} /><span>你记录的小想法会在这里慢慢聚拢。</span><Link to="/">回首页记下一条</Link></div> : ideas.map((idea, itemIndex) => <article className={`idea-note idea-note-${itemIndex % 5} glass-card`} key={idea.id}><Sparkle weight="fill" /><h3>{idea.title}</h3><p>{idea.raw_text || idea.content || '还在酝酿中'}</p><span>{idea.stage}</span><button type="button" className="idea-action" aria-label={`把“${idea.title}”加入航程`} onClick={() => void verifyIdea(idea.id)} disabled={ideaMutation === `saving:${idea.id}`}>{ideaMutation === `saving:${idea.id}` ? '正在加入…' : '用一个行动试试看'} <Path /></button>{ideaMutation === `saved:${idea.id}` && <small role="status">已把这个想法加入航程。</small>}{ideaMutation === `error:${idea.id}` && <small role="alert">这次没有加入成功，请重试。</small>}</article>)}</div></section>
    </div>
  )
}
