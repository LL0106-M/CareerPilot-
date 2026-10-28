import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../data/api'
import { ChatPage } from './ChatPage'

vi.mock('../../data/api', () => ({ api: {
  chat: vi.fn(), chatStream: vi.fn(), getConversations: vi.fn(), getConversation: vi.fn(),
  getDashboard: vi.fn(), uploadDocument: vi.fn(),
} }))

describe('chat page', () => {
  afterEach(() => vi.unstubAllGlobals())
  beforeEach(() => {
    vi.mocked(api.chat).mockReset()
    vi.mocked(api.chatStream).mockReset()
    vi.mocked(api.getConversations).mockReset().mockResolvedValue({ items: [] })
    vi.mocked(api.getConversation).mockReset()
    vi.mocked(api.getDashboard).mockReset().mockResolvedValue({
      hypotheses: [], journey: [], ideas: [], dreaming: [], memories: [],
    })
    vi.mocked(api.uploadDocument).mockReset()
  })

  it('lets the agent choose support mode and renders the real reply', async () => {
    vi.mocked(api.chatStream).mockImplementation(async (_body, onDelta) => {
      onDelta('我们先从最小的一步开始。')
      return {
      conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '我们先从最小的一步开始。',
      support_mode: 'organize', primary_intent: 'planning', retrieval_sources: [], memory_read_status: 'ok',
      memory_write_status: 'skipped', dreaming_status: 'queued', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)
    expect(screen.queryByRole('button', { name: '倾听' })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('给泊泊发送消息'), '我不知道先做什么')
    await user.click(screen.getByRole('button', { name: '发送' }))
    expect(await screen.findByText('我们先从最小的一步开始。')).toBeInTheDocument()
    expect(api.chatStream).toHaveBeenCalledWith({ message: '我不知道先做什么' }, expect.any(Function))
  })

  it('uploads selected files before sending their context to chat', async () => {
    vi.mocked(api.uploadDocument).mockResolvedValue({
      id: 'doc-1', title: 'resume.pdf', category: '其他资料', file_format: 'PDF', size_text: '3 B',
      uploaded_at: 'now', status: '解析中', retrieval_enabled: false,
    })
    vi.mocked(api.chatStream).mockImplementation(async (_body, onDelta) => {
      onDelta('我会结合这份资料来看。')
      return {
      conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '我会结合这份资料来看。',
      support_mode: 'organize', primary_intent: 'planning', retrieval_sources: [], memory_read_status: 'ok',
      memory_write_status: 'skipped', dreaming_status: 'queued', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)
    const file = new File(['pdf'], 'resume.pdf', { type: 'application/pdf' })

    await user.upload(screen.getByLabelText('附件'), file)
    await user.type(screen.getByLabelText('给泊泊发送消息'), '帮我看看简历')
    await user.click(screen.getByRole('button', { name: '发送' }))

    expect(api.uploadDocument).toHaveBeenCalledWith(file, '其他资料')
    expect(api.chatStream).toHaveBeenCalledWith(expect.objectContaining({ message: expect.stringContaining('resume.pdf') }), expect.any(Function))
    expect(await screen.findByText('我会结合这份资料来看。')).toBeInTheDocument()
  })

  it('starts side panels collapsed on a narrow screen and lets users reopen them', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: '展开历史对话' }))
    expect(screen.getByLabelText('历史对话').closest('.chat-workspace')).not.toHaveClass('history-closed')
    await user.click(screen.getByRole('button', { name: '展开关联内容' }))
    expect(screen.getByLabelText('关联内容').closest('.chat-workspace')).not.toHaveClass('context-closed')
  })

  it('loads real conversations and reopens the selected message history', async () => {
    vi.mocked(api.getConversations).mockResolvedValue({ items: [{
      id: 'c1', title: '真实保存的会话', updated_at: '2026-10-28T08:00:00Z', message_count: 2,
    }] })
    vi.mocked(api.getConversation).mockResolvedValue({
      id: 'c1', title: '真实保存的会话', updated_at: '2026-10-28T08:00:00Z',
      messages: [{ role: 'user', content: '这是旧问题' }, { role: 'agent', content: '这是旧回复' }],
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button', { name: /真实保存的会话/ }))

    expect(await screen.findByText('这是旧问题')).toBeInTheDocument()
    expect(screen.getByText('这是旧回复')).toBeInTheDocument()
    expect(screen.queryByText('作品集怎么讲更清楚')).not.toBeInTheDocument()
  })

  it('renders dashboard-derived context instead of demo copy', async () => {
    vi.mocked(api.getDashboard).mockResolvedValue({
      hypotheses: [{ id: 'h1', statement: '我可能更适合稳定节奏', status: '继续观察' }],
      journey: [], ideas: [], memories: [],
      dreaming: [{ id: 'd1', title: '稳定不是停滞', summary: '最近的选择都在寻找可预期感。' }],
    })

    render(<MemoryRouter><ChatPage /></MemoryRouter>)

    expect(await screen.findByText('稳定不是停滞')).toBeInTheDocument()
    expect(screen.getByText('我可能更适合稳定节奏')).toBeInTheDocument()
    expect(screen.queryByText('稳定与创造，也许不是二选一')).not.toBeInTheDocument()
  })

  it('keeps a completed reply when refreshing the history list fails', async () => {
    vi.mocked(api.getConversations)
      .mockResolvedValueOnce({ items: [] })
      .mockRejectedValueOnce(new Error('history unavailable'))
    vi.mocked(api.chatStream).mockImplementation(async (_body, onDelta) => {
      onDelta('已经收到回复。')
      return {
        conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '已经收到回复。',
        support_mode: 'listen', primary_intent: 'general_question', retrieval_sources: [], memory_read_status: 'ok',
        memory_write_status: 'skipped', dreaming_status: 'skipped', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)

    await user.type(screen.getByLabelText('给泊泊发送消息'), '测试刷新失败')
    await user.click(screen.getByRole('button', { name: '发送' }))

    expect(await screen.findByText('已经收到回复。')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not let a stale conversation load overwrite a newly sent turn', async () => {
    vi.mocked(api.getConversations).mockResolvedValue({ items: [{
      id: 'old', title: '较慢的旧会话', updated_at: '2026-10-28T08:00:00Z', message_count: 2,
    }] })
    let resolveDetail!: (value: Awaited<ReturnType<typeof api.getConversation>>) => void
    vi.mocked(api.getConversation).mockReturnValue(new Promise((resolve) => { resolveDetail = resolve }))
    vi.mocked(api.chatStream).mockImplementation(async (_body, onDelta) => {
      onDelta('新的流式回复')
      return {
        conversation_id: 'new', run_id: 'r1', result_status: 'completed', reply: '新的流式回复',
        support_mode: 'listen', primary_intent: 'general_question', retrieval_sources: [], memory_read_status: 'ok',
        memory_write_status: 'skipped', dreaming_status: 'skipped', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button', { name: /较慢的旧会话/ }))
    await user.type(screen.getByLabelText('给泊泊发送消息'), '开始新问题')
    await user.click(screen.getByRole('button', { name: '发送' }))
    expect(await screen.findByText('新的流式回复')).toBeInTheDocument()

    await act(async () => resolveDetail({
      id: 'old', title: '较慢的旧会话', updated_at: '2026-10-28T08:00:00Z',
      messages: [{ role: 'user', content: '旧问题' }, { role: 'agent', content: '旧回复' }],
    }))

    expect(screen.getByText('新的流式回复')).toBeInTheDocument()
    expect(screen.queryByText('旧回复')).not.toBeInTheDocument()
  })

  it('distinguishes rail loading failures from honest empty states', async () => {
    vi.mocked(api.getConversations).mockRejectedValue(new Error('history unavailable'))
    vi.mocked(api.getDashboard).mockRejectedValue(new Error('dashboard unavailable'))

    render(<MemoryRouter><ChatPage /></MemoryRouter>)

    expect(await screen.findByText('历史对话加载失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新加载历史对话' })).toBeInTheDocument()
    expect(screen.getByText('关联内容加载失败')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新加载关联内容' })).toBeInTheDocument()
    expect(screen.queryByText('还没有保存的对话')).not.toBeInTheDocument()
    expect(screen.queryByText('还没有形成关联线索')).not.toBeInTheDocument()
  })
})
