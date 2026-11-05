import { ArrowRight, Check, ChatCircleDots, Compass, Sparkle } from '@phosphor-icons/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../data/api'
import type { FutureLetter } from '../../data/api'
import './future-letter.css'

export function FutureLetterPanel({ letter }: { letter: FutureLetter }) {
  const [selected, setSelected] = useState(0)
  const [takeawayState, setTakeawayState] = useState<'idle' | 'confirming' | 'saving' | 'saved' | 'error'>(letter.takeaway ? 'saved' : 'idle')
  const path = letter.paths[selected]

  async function confirmTakeaway() {
    setTakeawayState('saving')
    try {
      await api.confirmFutureTakeaway(letter.journey_id, letter.id, path)
      setTakeawayState('saved')
    } catch { setTakeawayState('error') }
  }

  const chatDraft = `我想继续聊这封未来回信。当前问题是：${letter.message}\n我正在看的可能路径是“${path.label}”：${path.summary}\n请基于这条模拟路径问我问题，帮我看清选择，不要把它当成预测。`
  return <section className="future-letter glass-strong" aria-label="未来回信">
    <header className="future-letter-header"><div className="future-letter-mark"><Sparkle weight="fill" /></div><div><p className="eyebrow">Future letter · 一次可能性推演</p><h2>两年后的我，回信了</h2></div><p>这不是预测，只是把现在的证据向前展开。</p></header>
    <div className="future-path-tabs" role="tablist" aria-label="选择未来路径">{letter.paths.map((item,index) => <button type="button" role="tab" aria-selected={selected === index} className={selected === index ? 'active' : ''} onClick={() => { setSelected(index); setTakeawayState(letter.takeaway?.path_kind === item.kind ? 'saved' : 'idle') }} key={item.kind}><span>{String(index + 1).padStart(2,'0')}</span>{item.label}</button>)}</div>
    <article className="future-path-body" role="tabpanel"><div className="future-path-copy"><span className="future-path-kicker"><Compass /> {path.label}</span><h3>{path.title}</h3><p>{path.summary}</p>{path.signals.length > 0 && <div className="future-signals">{path.signals.map((signal) => <span key={signal}>{signal}</span>)}</div>}</div><aside className="future-question"><small>这条路的张力</small><p>{path.tension}</p><small>留给现在的我</small><strong>{path.question}</strong></aside></article>
    <footer className="future-letter-actions"><Link className="secondary-button" to="/chat" state={{draft:chatDraft}}><ChatCircleDots /> 问未来的我</Link>{takeawayState === 'confirming' ? <div className="takeaway-confirm"><span>只带回这个问题，不会创建任务或记忆。</span><button type="button" className="primary-button" onClick={() => void confirmTakeaway()}>确认带回 <ArrowRight /></button></div> : <button type="button" className="text-button future-takeaway" onClick={() => setTakeawayState('confirming')} disabled={takeawayState === 'saving' || takeawayState === 'saved'}>{takeawayState === 'saved' ? <><Check /> 已带回航程</> : takeawayState === 'saving' ? '正在带回…' : '带回一个问题'}</button>}{takeawayState === 'error' && <span className="chat-error" role="alert">没有保存成功，请重试。</span>}</footer>
  </section>
}
