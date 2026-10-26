import { ArrowDown, ArrowRight, GithubLogo, Lightbulb, PaperPlaneTilt, Sparkle } from '@phosphor-icons/react'
import { useRef, useState } from 'react'
import type { PointerEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { Bobo } from '../../components/bobo/Bobo'
import { api } from '../../data/api'

export function TodayPage() {
  const navigate = useNavigate()
  const stageRef = useRef<HTMLDivElement>(null)
  const [chatDraft, setChatDraft] = useState('')
  const [idea, setIdea] = useState('')
  const [ideaState, setIdeaState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')

  function moveBobo(event: PointerEvent<HTMLElement>) {
    const stage = stageRef.current
    if (!stage) return
    const bounds = event.currentTarget.getBoundingClientRect()
    if (!bounds.width || !bounds.height || !Number.isFinite(event.clientX) || !Number.isFinite(event.clientY)) return
    const x = (event.clientX - bounds.left) / bounds.width - 0.5
    const y = (event.clientY - bounds.top) / bounds.height - 0.5
    stage.style.setProperty('--bobo-x', `${x * 26}px`)
    stage.style.setProperty('--bobo-y', `${y * 16}px`)
    stage.style.setProperty('--orbit-rotate', `${x * 8}deg`)
  }

  async function saveIdea() {
    const text = idea.trim()
    if (!text || ideaState === 'saving') return
    setIdeaState('saving')
    try {
      await api.createIdea(text)
      setIdea('')
      setIdeaState('saved')
    } catch {
      setIdeaState('error')
    }
  }

  return (
    <div className="home-page">
      <section className="home-hero" onPointerMove={moveBobo}>
        <div className="home-copy">
          <p className="home-kicker"><Sparkle size={15} weight="fill" /> A quiet place to become</p>
          <h1>You don&apos;t choose a future.<br /><em>You learn your way into one.</em></h1>
          <p className="home-intro">Think aloud. Keep what matters. Take one small step.</p>
          <div className="home-chat glass-strong">
            <label htmlFor="home-chat-input">现在，想从哪里开始？</label>
            <div className="home-chat-row">
              <textarea id="home-chat-input" rows={2} value={chatDraft} onChange={(event) => setChatDraft(event.target.value)} placeholder="和泊泊说说最近在想什么……" />
              <button type="button" onClick={() => navigate('/chat', { state: { draft: chatDraft.trim() } })} aria-label="进入对话"><PaperPlaneTilt size={20} weight="fill" /></button>
            </div>
          </div>
          <div className="quick-idea glass-card">
            <Lightbulb size={18} weight="duotone" /><input aria-label="记录一个小想法" value={idea} onChange={(event) => { setIdea(event.target.value); setIdeaState('idle') }} placeholder="有个念头？先放在这里。" />
            <button type="button" onClick={() => void saveIdea()} disabled={!idea.trim() || ideaState === 'saving'}>收下这个想法</button>
          </div>
          <p className={`idea-feedback ${ideaState}`} aria-live="polite">{ideaState === 'saved' ? '已经替你收好了。' : ideaState === 'error' ? '暂时没有存好，再试一次。' : ideaState === 'saving' ? '正在收好……' : ''}</p>
        </div>
        <div className="home-character" ref={stageRef}>
          <div className="bobo-orbit" aria-hidden="true"><span /><span /><span /></div><Bobo mood="idle" size={430} />
          <div className="bobo-note glass-card"><strong>泊泊</strong><span>我在，慢慢说。</span></div>
        </div>
        <a className="scroll-cue" href="#dreaming"><ArrowDown size={17} />向下看看夜里发生了什么</a>
      </section>

      <section className="dreaming-showcase" id="dreaming">
        <div className="dreaming-copy"><p className="eyebrow">While you rest</p><h2>Dreaming</h2><p>零散的话不会被立刻定义。它们会在安静的时候重新靠近，慢慢长成你能看见的线索。</p><button className="soft-link" type="button" onClick={() => navigate('/dreaming')}>看看昨夜的联结 <ArrowRight size={17} /></button></div>
        <div className="dream-orbit" aria-label="Dreaming 正在连接想法"><div className="dream-core glass-strong"><Bobo mood="dreaming" size={154} /><span>泊泊正在 Dreaming</span></div>{['喜欢把模糊变清楚', '稳定，但仍能创造', '真实项目让我更有判断'].map((text, index) => <div className={`dream-node dream-node-${index + 1} glass-card`} key={text}>{text}</div>)}</div>
      </section>

      <footer className="product-footer" role="contentinfo">
        <div className="footer-story"><img src="/assets/careerpilot-wordmark.png" alt="CareerPilot" /><h2>A companion for the uncertain middle.</h2><p>CareerPilot turns conversations, small thoughts and real-world evidence into a path you can keep adjusting.</p><a href="https://github.com" target="_blank" rel="noreferrer"><GithubLogo size={18} /> GitHub</a></div>
        <div className="footer-column"><strong>Menu</strong><a href="/chat">Chat</a><a href="/compass">Compass</a><a href="/journey">Journey</a><a href="/knowledge/jobs">Knowledge</a></div>
        <div className="footer-column"><strong>Essentials</strong><a href="/settings">Privacy</a><a href="/settings">Safety</a></div>
        <div className="footer-column"><strong>Supported by</strong><span>MemOS</span><span>Alibaba Cloud</span><span>OpenAI</span><span>FastAPI</span></div>
        <div className="footer-mark" aria-hidden="true">CareerPilot</div>
      </footer>
    </div>
  )
}
