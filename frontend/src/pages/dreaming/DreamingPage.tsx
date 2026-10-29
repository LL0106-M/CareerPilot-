import { ArrowClockwise, CheckCircle, MoonStars, Sparkle } from '@phosphor-icons/react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { api, type DreamingResult } from '../../data/api'

const ACTIVE_JOB_KEY = 'careerpilot:active-dreaming-job'

export function DreamingPage() {
  const [result, setResult] = useState<DreamingResult | null>(null)
  const [state, setState] = useState<'loading' | 'idle' | 'generating' | 'failed'>('loading')
  const [message, setMessage] = useState('')
  const [confirmed, setConfirmed] = useState<Set<number>>(new Set())
  const timerRef = useRef<number | null>(null)

  const poll = useCallback(async (jobId: string) => {
    try {
      const job = await api.getDreamingJob(jobId)
      if (job.status === 'completed' && job.result) {
        setResult(job.result)
        setState('idle')
        setMessage('最近 7 天的线索已经整理好了。')
        localStorage.removeItem(ACTIVE_JOB_KEY)
        return
      }
      if (job.status === 'failed') {
        setState('failed')
        setMessage('这次没有生成成功，原有结果仍然保留。')
        localStorage.removeItem(ACTIVE_JOB_KEY)
        return
      }
      setState('generating')
      setMessage('泊泊正在连接最近 7 天的对话、想法和资料……')
      timerRef.current = window.setTimeout(() => void poll(jobId), 1200)
    } catch {
      setState('failed')
      setMessage('暂时无法读取生成进度，请稍后重试。')
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const activeJob = localStorage.getItem(ACTIVE_JOB_KEY)
      if (activeJob) {
        setState('generating')
        await poll(activeJob)
        return
      }
      try {
        const today = await api.getDreamingToday()
        if (!cancelled) setResult(today)
      } catch {
        // A missing result is the normal first-use state.
      } finally {
        if (!cancelled) setState('idle')
      }
    }
    void load()
    return () => {
      cancelled = true
      if (timerRef.current !== null) window.clearTimeout(timerRef.current)
    }
  }, [poll])

  async function start() {
    setState('generating')
    setMessage('正在准备最近 7 天的内容……')
    try {
      const job = await api.startDreaming()
      localStorage.setItem(ACTIVE_JOB_KEY, job.job_id)
      await poll(job.job_id)
    } catch (error) {
      setState('failed')
      setMessage(error instanceof Error ? error.message : '暂时无法开始 Dreaming。')
    }
  }

  async function confirm(index: number) {
    if (!result) return
    try {
      await api.confirmDreamingHypothesis(result.id, index)
      setConfirmed((items) => new Set(items).add(index))
    } catch {
      setMessage('这条方向暂时没有加入罗盘，请重试。')
    }
  }

  return (
    <section className="dreaming-page dreaming-real">
      <header className="dreaming-hero glass-strong">
        <div><p className="eyebrow">Dreaming · 最近 7 天</p><h1 className="page-title">让零散想法慢慢连成线</h1><p>泊泊会整理你的对话、小想法、罗盘方向和个人资料。生成的方向只是候选，由你决定是否加入罗盘。</p></div>
        <button className="primary-button dreaming-start" type="button" onClick={() => void start()} disabled={state === 'loading' || state === 'generating'}>
          {state === 'generating' ? <MoonStars className="dreaming-spin" /> : result ? <ArrowClockwise /> : <Sparkle />}
          {state === 'generating' ? '正在 Dreaming' : result ? '重新生成并更新今天的结果' : '开始 Dreaming'}
        </button>
      </header>
      <p className={`dreaming-live ${state}`} role="status" aria-live="polite">{message}</p>
      {state !== 'loading' && !result && state !== 'generating' && <div className="dreaming-empty glass-card"><MoonStars size={40} /><h2>还没有今天的 Dreaming</h2><p>点击上方按钮，整理最近 7 天留下的线索。</p></div>}
      {result && <div className="dreaming-result">
        <article className="dream-summary-card glass-card"><span>{result.local_date} · 第 {result.version} 版</span><h2>{result.summary}</h2>{result.tomorrow_step && <p><strong>下一小步：</strong>{result.tomorrow_step}</p>}</article>
        <div className="dreaming-columns">
          {result.wins.length > 0 && <section className="glass-card"><h3>本周观察</h3><ul>{result.wins.map((item) => <li key={item}>{item}</li>)}</ul></section>}
          {result.open_loops.length > 0 && <section className="glass-card"><h3>仍待验证</h3><ul>{result.open_loops.map((item) => <li key={item}>{item}</li>)}</ul></section>}
        </div>
        <section className="dreaming-hypotheses"><header><p className="eyebrow">Candidate directions</p><h2>可能值得靠近的方向</h2></header>{result.hypotheses.map((item, index) => <article className="dream-hypothesis glass-card" key={`${item.statement}-${index}`}><span>{item.confidence_band === 'high' ? '线索较强' : item.confidence_band === 'medium' ? '正在形成' : '初步观察'}</span><h3>{item.statement}</h3>{item.open_questions.length > 0 && <p>{item.open_questions[0]}</p>}<button type="button" className="secondary-button" onClick={() => void confirm(index)} disabled={confirmed.has(index)}>{confirmed.has(index) ? <><CheckCircle /> 已加入罗盘</> : '确认并加入罗盘'}</button></article>)}</section>
      </div>}
    </section>
  )
}
