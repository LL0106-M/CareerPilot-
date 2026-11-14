import { ArrowSquareOut, Brain, PaperPlaneTilt, X } from '@phosphor-icons/react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

import { MessageContent } from '../chat/MessageContent'
import { api } from '../../data/api'
import { Bobo } from './Bobo'
import { getCompanionConfig } from './companionConfig'
import { clearCompanionConversationId, getCompanionConversationId, saveCompanionConversationId } from './companionSession'
import './companion-bobo.css'

interface CompanionMessage { role: 'user' | 'agent'; content: string }

export function CompanionBobo() {
  const { pathname } = useLocation()
  const config = getCompanionConfig(pathname)
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<CompanionMessage[]>([])
  const [conversationId, setConversationId] = useState<string | undefined>(() => getCompanionConversationId())
  const [sending, setSending] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [error, setError] = useState('')
  const [memoryStatus, setMemoryStatus] = useState('')
  const triggerRef = useRef<HTMLButtonElement>(null)
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    if (!open) return undefined
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        window.setTimeout(() => triggerRef.current?.focus(), 0)
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [open])

  useEffect(() => {
    if (!open || !conversationId || messages.length > 0) return
    let active = true
    setLoadingHistory(true)
    void api.getConversation(conversationId).then((conversation) => {
      if (active) setMessages(conversation.messages)
    }).catch(() => {
      if (!active) return
      clearCompanionConversationId()
      setConversationId(undefined)
    }).finally(() => {
      if (active) setLoadingHistory(false)
    })
    return () => { active = false }
  }, [conversationId, open])

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    setMessages((previous) => [...previous, { role: 'user', content: text }, { role: 'agent', content: '' }])
    setInput('')
    setError('')
    setMemoryStatus('')
    setSending(true)
    try {
      const response = await api.chatStream({
        message: text,
        ...(conversationId ? { conversation_id: conversationId } : {}),
        page_context: { page: config.pageKey, label: config.label, path: pathname },
      }, (delta) => setMessages((previous) => previous.map((message, index) => (
        index === previous.length - 1 && message.role === 'agent'
          ? { ...message, content: message.content + delta }
          : message
      ))))
      setConversationId(response.conversation_id)
      saveCompanionConversationId(response.conversation_id)
      setMessages((previous) => previous.map((message, index) => (
        index === previous.length - 1 && message.role === 'agent'
          ? { ...message, content: response.reply }
          : message
      )))
      setMemoryStatus(response.memory_write_status === 'accepted'
        ? '这轮有内容进入长期记忆'
        : '这轮没有新增长期记忆')
    } catch (reason) {
      setMessages((previous) => previous.slice(0, -2))
      setInput(text)
      setError(reason instanceof Error ? reason.message : '这次没有送达，请再试一次。')
    } finally {
      setSending(false)
    }
  }

  if (config.hidden) return null

  return (
    <div className={`companion-layer companion-${config.accent}`}>
      <AnimatePresence>
        {!open && (
          <motion.button
            ref={triggerRef}
            type="button"
            className="companion-trigger"
            aria-label="打开泊泊侧边对话"
            aria-expanded="false"
            initial={reduceMotion ? false : { opacity: 0, y: 18, scale: 0.94 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={reduceMotion ? undefined : { opacity: 0, y: 8, scale: 0.96 }}
            whileHover={reduceMotion ? undefined : { y: -4 }}
            onClick={() => setOpen(true)}
          >
            <span className="companion-prompt">{config.prompt}</span>
            <Bobo mood={config.mood} size={126} />
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <aside
            className="companion-drawer glass-strong"
            role="complementary"
            aria-label="泊泊侧边对话"
          >
            <header className="companion-drawer-head">
              <div className="companion-identity">
                <Bobo mood={config.mood} size={72} />
                <div><small>正在看：{config.label}</small><strong>和泊泊聊聊</strong></div>
              </div>
              <button type="button" aria-label="关闭泊泊侧边对话" onClick={() => setOpen(false)}><X /></button>
            </header>

            <div className="companion-stream" aria-live="polite">
              {messages.length === 0 && !loadingHistory && <div className="companion-message agent">{config.greeting}</div>}
              {loadingHistory && <p className="companion-loading">正在接上刚才的对话…</p>}
              {messages.map((message, index) => (
                <div className={`companion-message ${message.role}${!message.content ? ' typing' : ''}`} key={`${message.role}-${index}`}>
                  {message.content ? <MessageContent content={message.content} /> : <><i /><i /><i /></>}
                </div>
              ))}
            </div>

            <footer className="companion-composer">
              {memoryStatus && <div className="companion-memory-status"><Brain /> <span>{memoryStatus}</span><Link to="/memory">管理</Link></div>}
              <p className="companion-context-prompt">{config.prompt}</p>
              <textarea
                aria-label="给泊泊发送消息"
                rows={2}
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }}
                placeholder={config.prompt}
              />
              <div className="companion-composer-actions">
                <Link to="/chat" state={conversationId ? { conversationId } : undefined}>进入完整对话 <ArrowSquareOut /></Link>
                <button type="button" aria-label="发送给泊泊" disabled={!input.trim() || sending} onClick={() => void send()}><PaperPlaneTilt weight="fill" /></button>
              </div>
              {error && <p className="chat-error" role="alert">{error}</p>}
            </footer>
          </aside>
        )}
      </AnimatePresence>
    </div>
  )
}
