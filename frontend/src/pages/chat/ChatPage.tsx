import { CaretDoubleLeft, CaretDoubleRight, FolderSimple, Paperclip, PaperPlaneTilt, Plus, SidebarSimple } from '@phosphor-icons/react'
import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { Bobo } from '../../components/bobo/Bobo'
import { api } from '../../data/api'

interface ChatMessage { role: 'user' | 'agent'; content: string }
interface ChatLocationState { draft?: string }

export function ChatPage() {
  const startsNarrow = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 760px)').matches
  const initialDraft = (useLocation().state as ChatLocationState | null)?.draft || ''
  const [input, setInput] = useState(initialDraft)
  const [conversationId, setConversationId] = useState<string>()
  const [messages, setMessages] = useState<ChatMessage[]>([{ role: 'agent', content: '我在。你可以从一件很小、还没想清楚的事开始。' }])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [historyOpen, setHistoryOpen] = useState(!startsNarrow)
  const [contextOpen, setContextOpen] = useState(!startsNarrow)
  const [files, setFiles] = useState<File[]>([])
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (typeof endRef.current?.scrollIntoView === 'function') {
      endRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, sending])

  async function send() {
    const text = input.trim()
    if (!text || sending) return
    setMessages((previous) => [...previous, { role: 'user', content: text }]); setInput(''); setError(''); setSending(true)
    try {
      const uploaded = files.length > 0
        ? await Promise.all(files.map((file) => api.uploadDocument(file, '其他资料')))
        : []
      const attachmentContext = uploaded.length > 0
        ? `\n\n[本轮已上传到个人知识库的资料：${uploaded.map((item) => `${item.title}（${item.id}）`).join('、')}。请结合可用的资料状态回应；若仍在解析，请明确说明。]`
        : ''
      const message = `${text}${attachmentContext}`
      const response = await api.chat(conversationId ? { message, conversation_id: conversationId } : { message })
      setConversationId(response.conversation_id)
      setMessages((previous) => [...previous, { role: 'agent', content: response.reply }])
      setFiles([])
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '这次没有送达，再试一次。'); setInput(text)
    } finally { setSending(false) }
  }

  return (
    <section className={`chat-workspace${historyOpen ? '' : ' history-closed'}${contextOpen ? '' : ' context-closed'}`}>
      <aside className="chat-history glass-card" aria-label="历史对话"><div className="chat-panel-head"><span>Conversations</span><button type="button" aria-label="收起历史对话" onClick={() => setHistoryOpen(false)}><CaretDoubleLeft /></button></div><button className="new-chat-button" type="button" onClick={() => { setMessages([{ role: 'agent', content: '新的这一页，从哪里开始？' }]); setConversationId(undefined) }}><Plus /> 新对话</button><div className="conversation-folder"><FolderSimple weight="duotone" /> 求职准备 <span>3</span></div><button className="conversation-item active" type="button"><strong>现在不知道先做什么</strong><span>刚刚</span></button><button className="conversation-item" type="button"><strong>作品集怎么讲更清楚</strong><span>昨天</span></button><div className="conversation-folder"><FolderSimple weight="duotone" /> 慢慢想 <span>2</span></div><button className="conversation-item" type="button"><strong>我想要怎样的工作节奏</strong><span>10 月 21 日</span></button></aside>
      {!historyOpen && <button className="panel-reopen history-reopen" type="button" aria-label="展开历史对话" onClick={() => { setHistoryOpen(true); if (startsNarrow) setContextOpen(false) }}><SidebarSimple /></button>}
      <div className="chat-center"><header className="chat-titlebar"><div><p className="eyebrow">A conversation with Bobo</p><h1>慢慢说，我们一起把它想清楚。</h1></div><Bobo mood={sending ? 'thinking' : 'listen'} size={78} /></header><div className="chat-stream" aria-live="polite">{messages.map((message, index) => <div key={`${message.role}-${index}`} className={`chat-message ${message.role}`}><span>{message.content}</span></div>)}{sending && <div className="chat-message agent typing"><i /><i /><i /></div>}<div ref={endRef} /></div><div className="chat-composer glass-strong">{files.length > 0 && <div className="file-chips">{files.map((file) => <span key={file.name}>{file.name}</span>)}</div>}<textarea aria-label="给泊泊发送消息" rows={3} value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void send() } }} placeholder="写下一点想法，或者告诉我你现在的感受……" /><div className="composer-tools"><label className="attach-button"><Paperclip /> 附件<input type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={(event) => setFiles(Array.from(event.target.files || []))} /></label><span>泊泊会自己判断如何回应</span><button type="button" aria-label="发送" onClick={() => void send()} disabled={!input.trim() || sending}><PaperPlaneTilt weight="fill" /></button></div>{error && <div className="chat-error" role="alert">{error}</div>}</div></div>
      <aside className="chat-context glass-card" aria-label="关联内容"><div className="chat-panel-head"><span>Alongside</span><button type="button" aria-label="收起关联内容" onClick={() => setContextOpen(false)}><CaretDoubleRight /></button></div><p className="context-label">泊泊正在留意</p><h2>你不是在选一个标准答案，而是在收集对自己有用的证据。</h2><div className="context-card"><span>Dreaming</span><strong>稳定与创造，也许不是二选一</strong><small>自动形成，不打断对话</small></div><div className="context-card pending"><span>等待确认</span><strong>把“工作节奏”加入罗盘？</strong><small>涉及其他页面时由你决定</small></div></aside>
      {!contextOpen && <button className="panel-reopen context-reopen" type="button" aria-label="展开关联内容" onClick={() => { setContextOpen(true); if (startsNarrow) setHistoryOpen(false) }}><SidebarSimple /></button>}
    </section>
  )
}
