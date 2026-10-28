import { CaretDoubleLeft, CaretDoubleRight, FolderSimple, Paperclip, PaperPlaneTilt, Plus, SidebarSimple } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { Bobo } from '../../components/bobo/Bobo'
import { api, type ConversationSummary, type DashboardResponse } from '../../data/api'

interface ChatMessage { role: 'user' | 'agent'; content: string }
interface ChatLocationState { draft?: string }

const WELCOME_MESSAGE: ChatMessage = { role: 'agent', content: '我在。你可以从一件很小、还没想清楚的事开始。' }

function conversationTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '最近'
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return '刚刚'
  return date.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

export function ChatPage() {
  const startsNarrow = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 760px)').matches
  const initialDraft = (useLocation().state as ChatLocationState | null)?.draft || ''
  const [input, setInput] = useState(initialDraft)
  const [conversationId, setConversationId] = useState<string>()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [dashboard, setDashboard] = useState<DashboardResponse>()
  const [historyStatus, setHistoryStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [contextStatus, setContextStatus] = useState<'loading' | 'ready' | 'error'>('loading')
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [historyOpen, setHistoryOpen] = useState(!startsNarrow)
  const [contextOpen, setContextOpen] = useState(!startsNarrow)
  const [files, setFiles] = useState<File[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  const selectionRequestRef = useRef(0)

  async function loadConversations(showLoading = true) {
    if (showLoading) setHistoryStatus('loading')
    try {
      const response = await api.getConversations()
      if (Array.isArray(response.items)) setConversations(response.items)
      setHistoryStatus('ready')
    } catch (reason) {
      setHistoryStatus('error')
      throw reason
    }
  }

  async function loadDashboard() {
    setContextStatus('loading')
    try {
      setDashboard(await api.getDashboard())
      setContextStatus('ready')
    } catch (reason) {
      setContextStatus('error')
      throw reason
    }
  }

  useEffect(() => {
    void loadConversations().catch(() => undefined)
    void loadDashboard().catch(() => undefined)
  }, [])

  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === 'function') endRef.current.scrollIntoView({ behavior: 'smooth' })
  }, [messages, sending])

  async function openConversation(id: string) {
    if (sending) return
    const requestId = ++selectionRequestRef.current
    setError('')
    try {
      const detail = await api.getConversation(id)
      if (requestId !== selectionRequestRef.current) return
      setConversationId(detail.id)
      setMessages(detail.messages)
      if (startsNarrow) setHistoryOpen(false)
    } catch (reason) {
      if (requestId !== selectionRequestRef.current) return
      setError(reason instanceof Error ? reason.message : '暂时无法打开这段对话。')
    }
  }

  function startNewConversation() {
    if (sending) return
    selectionRequestRef.current += 1
    setMessages([{ role: 'agent', content: '新的这一页，从哪里开始？' }])
    setConversationId(undefined)
    setError('')
  }

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    selectionRequestRef.current += 1
    setMessages((previous) => [...previous, { role: 'user', content: text }, { role: 'agent', content: '' }])
    setInput('')
    setError('')
    setSending(true)
    try {
      const uploaded = files.length > 0
        ? await Promise.all(files.map((file) => api.uploadDocument(file, '其他资料')))
        : []
      const attachmentContext = uploaded.length > 0
        ? `\n\n[本轮已上传到个人知识库的资料：${uploaded.map((item) => `${item.title}（${item.id}）`).join('、')}。请结合可用的资料状态回应；若仍在解析，请明确说明。]`
        : ''
      const message = `${text}${attachmentContext}`
      const response = await api.chatStream(
        conversationId ? { message, conversation_id: conversationId } : { message },
        (delta) => setMessages((previous) => previous.map((item, index) => (
          index === previous.length - 1 && item.role === 'agent'
            ? { ...item, content: item.content + delta }
            : item
        ))),
      )
      setConversationId(response.conversation_id)
      setMessages((previous) => previous.map((item, index) => (
        index === previous.length - 1 && item.role === 'agent'
          ? { ...item, content: response.reply }
          : item
      )))
      setFiles([])
      void loadConversations(false).catch(() => undefined)
    } catch (reason) {
      setMessages((previous) => previous.slice(0, -1))
      setError(reason instanceof Error ? reason.message : '这次没有送达，再试一次。')
      setInput(text)
    } finally {
      setSending(false)
    }
  }

  const latestDream = dashboard?.dreaming[0]
  const pendingHypothesis = dashboard?.hypotheses.find((item) => !['已确认', 'confirmed', 'rejected'].includes(item.status)) || dashboard?.hypotheses[0]

  return (
    <section className={`chat-workspace${historyOpen ? '' : ' history-closed'}${contextOpen ? '' : ' context-closed'}`}>
      <aside className="chat-history glass-card" aria-label="历史对话">
        <div className="chat-panel-head"><span>Conversations</span><button type="button" aria-label="收起历史对话" onClick={() => setHistoryOpen(false)}><CaretDoubleLeft /></button></div>
        <button className="new-chat-button" type="button" onClick={startNewConversation} disabled={sending}><Plus /> 新对话</button>
        <div className="conversation-folder"><FolderSimple weight="duotone" /> 最近对话 <span>{conversations.length}</span></div>
        {historyStatus === 'loading' && conversations.length === 0 && <p className="conversation-empty">正在加载历史对话…</p>}
        {historyStatus === 'error' && <div className="conversation-empty"><p>历史对话加载失败</p><button type="button" onClick={() => void loadConversations().catch(() => undefined)}>重新加载历史对话</button></div>}
        {historyStatus === 'ready' && conversations.length === 0 && <p className="conversation-empty">还没有保存的对话</p>}
        {conversations.map((conversation) => (
          <button className={`conversation-item${conversation.id === conversationId ? ' active' : ''}`} type="button" key={conversation.id} disabled={sending} onClick={() => void openConversation(conversation.id)}>
            <strong>{conversation.title}</strong><span>{conversationTime(conversation.updated_at)}</span>
          </button>
        ))}
      </aside>
      {!historyOpen && <button className="panel-reopen history-reopen" type="button" aria-label="展开历史对话" onClick={() => { setHistoryOpen(true); if (startsNarrow) setContextOpen(false) }}><SidebarSimple /></button>}
      <div className="chat-center">
        <header className="chat-titlebar"><div><p className="eyebrow">A conversation with Bobo</p><h1>慢慢说，我们一起把它想清楚。</h1></div><Bobo mood={sending ? 'thinking' : 'listen'} size={78} /></header>
        <div className="chat-stream" aria-live="polite">
          {messages.map((message, index) => (
            <div key={`${message.role}-${index}`} className={`chat-message ${message.role}${!message.content ? ' typing' : ''}`}>
              {message.content ? <span>{message.content}</span> : <><i /><i /><i /></>}
            </div>
          ))}
          <div ref={endRef} />
        </div>
        <div className="chat-composer glass-strong">
          {files.length > 0 && <div className="file-chips">{files.map((file) => <span key={file.name}>{file.name}</span>)}</div>}
          <textarea aria-label="给泊泊发送消息" rows={3} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder="写下一点想法，或者告诉我你现在的感受……" />
          <div className="composer-tools"><label className="attach-button"><Paperclip /> 附件<input type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={(event) => setFiles(Array.from(event.target.files || []))} /></label><span>泊泊会自己判断如何回应</span><button type="button" aria-label="发送" onClick={() => void send()} disabled={!input.trim() || sending}><PaperPlaneTilt weight="fill" /></button></div>
          {error && <div className="chat-error" role="alert">{error}</div>}
        </div>
      </div>
      <aside className="chat-context glass-card" aria-label="关联内容">
        <div className="chat-panel-head"><span>Alongside</span><button type="button" aria-label="收起关联内容" onClick={() => setContextOpen(false)}><CaretDoubleRight /></button></div>
        <p className="context-label">泊泊正在留意</p>
        <h2>{latestDream?.summary || pendingHypothesis?.statement || pendingHypothesis?.content || '对话中的线索会在这里慢慢形成。'}</h2>
        {latestDream && <div className="context-card"><span>Dreaming</span><strong>{latestDream.title || latestDream.summary || '新的观察'}</strong><small>来自你的近期复盘</small></div>}
        {pendingHypothesis && <div className="context-card pending"><span>{pendingHypothesis.status || '等待确认'}</span><strong>{pendingHypothesis.statement || pendingHypothesis.content}</strong><small>需要更多真实经历来验证</small></div>}
        {contextStatus === 'loading' && <p className="conversation-empty">正在加载关联内容…</p>}
        {contextStatus === 'error' && <div className="conversation-empty"><p>关联内容加载失败</p><button type="button" onClick={() => void loadDashboard().catch(() => undefined)}>重新加载关联内容</button></div>}
        {contextStatus === 'ready' && !latestDream && !pendingHypothesis && <p className="conversation-empty">还没有形成关联线索</p>}
      </aside>
      {!contextOpen && <button className="panel-reopen context-reopen" type="button" aria-label="展开关联内容" onClick={() => { setContextOpen(true); if (startsNarrow) setHistoryOpen(false) }}><SidebarSimple /></button>}
    </section>
  )
}
