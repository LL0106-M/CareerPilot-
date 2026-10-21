import { useState } from 'react'
import type { ReactNode } from 'react'

const MODES = ['倾听', '梳理', '探索', '行动'] as const
export type SupportMode = (typeof MODES)[number]

interface ChatMessage {
  role: 'user' | 'agent'
  content: string
}

export function ChatPage() {
  const [mode, setMode] = useState<SupportMode | 'auto'>('auto')
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: 'agent', content: '泊泊在这儿。想先聊聊，还是一起做点什么？' },
  ])

  function send() {
    const text = input.trim()
    if (!text) return
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    // 临时占位回复；后端 API 接入后替换
    setMessages((prev) => [
      ...prev,
      { role: 'agent', content: '收到了。等后端 /v1/chat 接入后这里会是泊泊的真回复。' },
    ])
  }

  return (
    <section className="chat-layout">
      <div className="glass-card chat-main">
        <div className="chat-mode-bar">
          <ModeButton
            active={mode === 'auto'}
            onClick={() => setMode('auto')}
          >
            让泊泊判断
          </ModeButton>
          {MODES.map((m) => (
            <ModeButton key={m} active={mode === m} onClick={() => setMode(m)}>
              {m}
            </ModeButton>
          ))}
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={i} className={`chat-bubble chat-bubble-${msg.role}`}>
              {msg.content}
            </div>
          ))}
        </div>

        <div className="chat-input-row">
          <textarea
            className="chat-input"
            placeholder="写下一点想法，或者告诉我你现在的感受……"
            rows={2}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
          />
          <button className="primary-button" onClick={send} type="button">
            发送
          </button>
        </div>
      </div>

      <aside className="glass-card chat-side">
        <h2 className="eyebrow">当前上下文</h2>
        <h3 className="side-title">本轮泊泊关注的范围</h3>
        <ul className="side-list">
          <li>支持模式：{mode === 'auto' ? '自动判断' : mode}</li>
          <li>检索范围：岗位、备考、个人资料</li>
          <li>联网：本地资料不足时会提示你</li>
        </ul>
      </aside>
    </section>
  )
}

function ModeButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      className={`mode-button${active ? ' active' : ''}`}
      onClick={onClick}
      aria-pressed={active}
    >
      {children}
    </button>
  )
}
