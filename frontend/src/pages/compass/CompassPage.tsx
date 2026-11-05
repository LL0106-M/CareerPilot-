import { ArrowDown, ArrowLeft, ArrowRight, Check, Compass, Lightbulb, Path, Sparkle } from '@phosphor-icons/react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../data/api'
import { useDashboard } from '../../hooks/useDashboard'

export function CompassPage() {
  const { data, error, loading, reload } = useDashboard()
  const [index, setIndex] = useState(0)
  const [mutation, setMutation] = useState('')
  const [journeyConfirmOpen, setJourneyConfirmOpen] = useState(false)
  const [journeyState, setJourneyState] = useState<'idle' | 'saving' | 'error'>('idle')
  const [compareOpen, setCompareOpen] = useState(false)
  const hypotheses = data?.hypotheses || []
  const directions = data?.directions || []
  const journeys = data?.journeys || []
  const compassItems = useMemo(() => [
    ...directions.map((item) => ({ kind: 'direction' as const, item })),
    ...hypotheses.map((item) => ({ kind: 'hypothesis' as const, item })),
  ], [directions, hypotheses])
  const current = compassItems[index]
  const ideas = data?.ideas || []
  const confirmed = useMemo(
    () => directions.length + hypotheses.filter((item) => item.status === '已确认').length,
    [directions, hypotheses],
  )
  const currentJourney = current?.kind === 'direction'
    ? journeys.find((journey) => journey.direction_id === current.item.id)
    : undefined
  const currentBranches = current?.kind === 'direction'
    ? (data?.direction_branches || []).filter((branch) => branch.direction_id === current.item.id && branch.status !== 'archived')
    : []
  const currentSummary = current?.kind === 'direction'
    ? (data?.direction_summaries || []).find((summary) => summary.direction_id === current.item.id)
    : undefined
  const currentEvidence = current?.kind === 'direction'
    ? (data?.direction_evidence || []).filter((item) => item.direction_id === current.item.id)
    : []

  async function decide(decision: 'confirm' | 'uncertain') {
    if (!current || current.kind !== 'hypothesis') return
    setMutation('saving')
    try {
      await api.decideHypothesis(current.item.id, decision)
      await reload()
      setMutation('saved')
    } catch {
      setMutation('error')
    }
  }

  async function startJourney() {
    if (!current || current.kind !== 'direction') return
    setJourneyState('saving')
    try {
      await api.startDirectionJourney(current.item.id)
      await reload()
      setJourneyConfirmOpen(false)
      setJourneyState('idle')
    } catch {
      setJourneyState('error')
    }
  }

  return (
    <div className="compass-experience">
      <section className="compass-focus glass-card">
        <div className="compass-intro">
          <p className="eyebrow">Compass · Career explorations</p>
          <h1>现在，哪一种方向<br />值得你靠近一点？</h1>
          <p>不用先想出完整答案。罗盘只保存你确认过的方向，以及仍需要聊清楚的线索。</p>
          <div className="compass-progress"><span>{confirmed} 条已确认</span><span>{hypotheses.length} 条正在形成</span></div>
          <a href="#idea-field" className="soft-link dark">继续看那些还没成形的想法 <ArrowDown /></a>
        </div>
        <div className="direction-stage">
          {loading && <div className="state-panel">泊泊正在整理最近的线索……</div>}
          {error && <div className="state-panel error"><span>{error}</span><button type="button" onClick={() => void reload()}>重试</button></div>}
          {!loading && !error && !current && <div className="state-panel"><Compass size={36} weight="duotone" /><h2>罗盘还没有方向</h2><p>先去聊一会儿。只有你表达或确认过的方向才会出现在这里。</p><Link to="/chat" className="primary-button">去对话</Link></div>}

          {current?.kind === 'direction' && <article className="direction-card glass-strong">
            <div className="direction-index">{String(index + 1).padStart(2, '0')} / {String(compassItems.length).padStart(2, '0')}</div>
            <span className="direction-status">已确认方向</span>
            <h2>{current.item.label}</h2>
            <p>“{current.item.source_quote}”</p>
            <div className="evidence-strip"><span>{current.item.source_kind === 'conversation' ? '来自对话' : '来自你的想法'}</span><span>{current.item.reason}</span></div>
            {currentBranches.length > 0 && <div className="target-branches" aria-label="目标分支">{currentBranches.map((branch) => <span key={branch.id}>{[branch.company, branch.business].filter(Boolean).join('｜') || branch.role}</span>)}</div>}
            {currentSummary && <div className="direction-context-grid">
              <div><span>为什么在这里</span><strong>{currentSummary.reason}</strong></div>
              <div><span>最大未知</span><strong>{currentSummary.unknown_question}</strong></div>
              <div><span>最近变化</span><strong>{currentSummary.recent_change}</strong></div>
              <div className="next-validation"><span>下一验证点</span><strong>{currentSummary.next_validation}</strong></div>
            </div>}
            {currentEvidence.length > 0 && <details className="evidence-drawer"><summary>查看证据与未知项</summary><div>{currentEvidence.map((item) => <article key={item.id}><span>{item.kind === 'support' ? '支持证据' : item.kind === 'counter' ? '反对证据' : '仍未知'}</span><strong>{item.content}</strong>{item.source_quote && <small>“{item.source_quote}”</small>}</article>)}</div></details>}
            {currentJourney
              ? <div className="direction-actions"><Link className="primary-button" to="/journey">查看航程</Link>{currentBranches.length > 1 && <button type="button" className="secondary-button" onClick={() => setCompareOpen((value) => !value)}>对比目标</button>}</div>
              : <><div className="direction-actions"><button type="button" className="primary-button" onClick={() => { setJourneyState('idle'); setJourneyConfirmOpen(true) }}><Path /> 开始航程</button>{currentBranches.length > 1 && <button type="button" className="secondary-button" onClick={() => setCompareOpen((value) => !value)}>对比目标</button>}</div><p className="mutation-note">它在罗盘里，只有你确认后才会开启航程。</p></>}
          </article>}

          {current?.kind === 'hypothesis' && <article className="direction-card glass-strong">
            <div className="direction-index">{String(index + 1).padStart(2, '0')} / {String(compassItems.length).padStart(2, '0')}</div>
            <span className="direction-status">{current.item.status}</span>
            <h2>{current.item.statement || current.item.content}</h2>
            <p>这是 AI 的待验证观察，不是你已经确认的方向。</p>
            {current.item.evidence && current.item.evidence.length > 0 && <div className="evidence-strip">{current.item.evidence.slice(0, 3).map((item) => <span key={item}>{item}</span>)}</div>}
            <div className="direction-actions"><button type="button" className="primary-button" onClick={() => void decide('confirm')}><Check /> 加入罗盘</button><button type="button" className="text-button" onClick={() => void decide('uncertain')}>先继续观察</button></div>
            <p className="mutation-note" aria-live="polite">{mutation === 'saving' ? '正在更新……' : mutation === 'saved' ? '已写入你的罗盘。' : mutation === 'error' ? '没有更新成功，请重试。' : ''}</p>
          </article>}

          {compassItems.length > 1 && <div className="direction-nav"><button type="button" aria-label="上一个方向" onClick={() => setIndex((index - 1 + compassItems.length) % compassItems.length)}><ArrowLeft /></button><button type="button" aria-label="下一个方向" onClick={() => setIndex((index + 1) % compassItems.length)}><ArrowRight /></button></div>}
        </div>
      </section>

      {compareOpen && current?.kind === 'direction' && currentBranches.length > 1 && <section className="branch-comparison glass-card" aria-label="目标分支对比"><header><div><p className="eyebrow">Compare targets</p><h2>同一方向，不同现实路径。</h2></div><button type="button" className="text-button" onClick={() => setCompareOpen(false)}>收起对比</button></header><div className="branch-comparison-grid">{currentBranches.slice(0,3).map((branch) => <article key={branch.id}><h3>{[branch.company,branch.business].filter(Boolean).join('｜') || branch.role}</h3><dl><div><dt>岗位</dt><dd>{branch.role || '还不知道'}</dd></div><div><dt>地点</dt><dd>{branch.location || '还不知道'}</dd></div><div><dt>已有证据</dt><dd>{currentEvidence.find((item) => item.branch_id === branch.id && item.kind === 'support')?.content || '还不知道'}</dd></div><div><dt>最大未知</dt><dd>{currentEvidence.find((item) => item.branch_id === branch.id && item.kind === 'unknown')?.content || currentSummary?.unknown_question || '还不知道'}</dd></div></dl></article>)}</div></section>}

      {(data?.career_profile || []).length > 0 && <section className="career-profile-strip glass-card"><div><p className="eyebrow">Career profile</p><h2>罗盘也在理解你如何工作。</h2></div><div>{(data?.career_profile || []).slice(0,4).map((item) => <span key={item.id}><small>{item.category}</small><strong>{item.value}</strong></span>)}</div></section>}

      {journeyConfirmOpen && current?.kind === 'direction' && <div className="modal-backdrop"><div className="modal-panel glass-strong" role="dialog" aria-modal="true" aria-label="确认开始航程"><Path size={28} /><h2>从“{current.item.label}”开始一段航程？</h2><p>确认后会创建一条可编辑的路线，并开始收集岗位信息、往年题目和学习资源。不会替你投递，也不会自动添加日历。</p>{journeyState === 'error' && <p className="chat-error" role="alert">航程没有创建成功，请重试。</p>}<div className="modal-actions"><button type="button" className="text-button" onClick={() => setJourneyConfirmOpen(false)} disabled={journeyState === 'saving'}>取消</button><button type="button" className="primary-button" onClick={() => void startJourney()} disabled={journeyState === 'saving'}>{journeyState === 'saving' ? '正在开始…' : '确认开始'}</button></div></div></div>}

      <section className="idea-field" id="idea-field">
        <header><div><p className="eyebrow">Thought fragments</p><h2>有些想法，先让它们散落着。</h2></div><p>它们不需要马上变成方向。靠近其中一张，和泊泊继续聊清楚它可能走向哪里。</p></header>
        <div className="idea-cloud">
          {ideas.length === 0
            ? <div className="empty-ideas glass-card"><Lightbulb size={28} /><span>你记录的小想法会在这里慢慢聚拢。</span><Link to="/">回首页记下一条</Link></div>
            : ideas.map((idea, itemIndex) => <article className={`idea-note idea-note-${itemIndex % 5} glass-card`} key={idea.id}><Sparkle weight="fill" /><h3>{idea.title}</h3><p>{idea.raw_text || idea.content || '还在酝酿中'}</p><span>{idea.stage}</span><Link to="/chat" state={{ draft: idea.raw_text || idea.content || idea.title }} className="idea-action" aria-label={`展开“${idea.title}”`}>展开看看 <Path /></Link></article>)}
        </div>
      </section>
    </div>
  )
}
