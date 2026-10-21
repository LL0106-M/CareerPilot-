import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'

const MODES = [
  { key: 'listen', label: '先听我说', desc: '泊泊主要陪着你，不急着给建议' },
  { key: 'structure', label: '帮我梳理', desc: '一起把你现在的感受理清' },
  { key: 'explore', label: '一起探索', desc: '聊聊你没太想过的可能性' },
  { key: 'act', label: '帮我行动', desc: '拆成小步子，开始往前走' },
] as const

type ModeKey = (typeof MODES)[number]['key']

export function IntroPage() {
  const [step, setStep] = useState(0) // 0: 称呼, 1: 困扰, 2: 回应
  const [name, setName] = useState('')
  const [worry, setWorry] = useState('')
  const [mode, setMode] = useState<ModeKey | null>(null)
  const [done, setDone] = useState(false)

  if (done) return <Navigate to="/today" replace />

  return (
    <div className="intro-shell">
      <section className="glass-card intro-card">
        <img
          className="intro-bobo"
          src="/assets/bobo-idle.png"
          alt="泊泊"
        />
        <div className="intro-body">
          <p className="eyebrow">你好，我是泊泊</p>

          {step === 0 && (
            <>
              <h1 className="page-title">我该怎么称呼你？</h1>
              <input
                className="intro-input"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="一个你喜欢的称呼就行"
              />
            </>
          )}
          {step === 1 && (
            <>
              <h1 className="page-title">最近最困扰你的事是什么？</h1>
              <textarea
                className="intro-input"
                rows={3}
                value={worry}
                onChange={(e) => setWorry(e.target.value)}
                placeholder="不用想清楚，随便写几句也行"
              />
            </>
          )}
          {step === 2 && (
            <>
              <h1 className="page-title">你希望我怎么回应你？</h1>
              <div className="intro-modes">
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    type="button"
                    className={`intro-mode${mode === m.key ? ' active' : ''}`}
                    onClick={() => setMode(m.key)}
                  >
                    <div className="intro-mode-label">{m.label}</div>
                    <div className="intro-mode-desc muted">{m.desc}</div>
                  </button>
                ))}
              </div>
            </>
          )}

          <div className="intro-nav">
            {step > 0 && (
              <button type="button" className="text-button" onClick={() => setStep(step - 1)}>
                上一步
              </button>
            )}
            <div className="intro-dots">
              {[0, 1, 2].map((i) => (
                <span key={i} className={`dot${i === step ? ' active' : ''}`} />
              ))}
            </div>
            {step < 2 ? (
              <button
                type="button"
                className="primary-button"
                disabled={step === 0 ? !name.trim() : step === 1 ? !worry.trim() : false}
                onClick={() => setStep(step + 1)}
              >
                继续
              </button>
            ) : (
              <button
                type="button"
                className="primary-button"
                disabled={!mode}
                onClick={() => setDone(true)}
              >
                开始
              </button>
            )}
          </div>

          <p className="muted intro-notes">
            你告诉我的内容可能会进入长期记忆，<br />
            但知识库和记忆是分开的，上传的资料只属于你自己。
          </p>
          <Link to="/today" className="intro-skip">先跳过，直接进主页</Link>
        </div>
      </section>
    </div>
  )
}
