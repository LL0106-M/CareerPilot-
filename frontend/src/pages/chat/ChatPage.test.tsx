import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../data/api'
import { ChatPage } from './ChatPage'

vi.mock('../../data/api', () => ({ api: { chat: vi.fn(), uploadDocument: vi.fn() } }))

describe('chat page', () => {
  afterEach(() => vi.unstubAllGlobals())
  beforeEach(() => {
    vi.mocked(api.chat).mockReset()
    vi.mocked(api.uploadDocument).mockReset()
  })

  it('lets the agent choose support mode and renders the real reply', async () => {
    vi.mocked(api.chat).mockResolvedValue({
      conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '我们先从最小的一步开始。',
      support_mode: 'organize', primary_intent: 'planning', retrieval_sources: [], memory_read_status: 'ok',
      memory_write_status: 'skipped', dreaming_status: 'queued', memory_ids: [], citation_ids: [], citation_warnings: [],
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)
    expect(screen.queryByRole('button', { name: '倾听' })).not.toBeInTheDocument()
    await user.type(screen.getByLabelText('给泊泊发送消息'), '我不知道先做什么')
    await user.click(screen.getByRole('button', { name: '发送' }))
    expect(await screen.findByText('我们先从最小的一步开始。')).toBeInTheDocument()
    expect(api.chat).toHaveBeenCalledWith({ message: '我不知道先做什么' })
  })

  it('uploads selected files before sending their context to chat', async () => {
    vi.mocked(api.uploadDocument).mockResolvedValue({
      id: 'doc-1', title: 'resume.pdf', category: '其他资料', file_format: 'PDF', size_text: '3 B',
      uploaded_at: 'now', status: '解析中', retrieval_enabled: false,
    })
    vi.mocked(api.chat).mockResolvedValue({
      conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '我会结合这份资料来看。',
      support_mode: 'organize', primary_intent: 'planning', retrieval_sources: [], memory_read_status: 'ok',
      memory_write_status: 'skipped', dreaming_status: 'queued', memory_ids: [], citation_ids: [], citation_warnings: [],
    })
    const user = userEvent.setup()
    render(<MemoryRouter><ChatPage /></MemoryRouter>)
    const file = new File(['pdf'], 'resume.pdf', { type: 'application/pdf' })

    await user.upload(screen.getByLabelText('附件'), file)
    await user.type(screen.getByLabelText('给泊泊发送消息'), '帮我看看简历')
    await user.click(screen.getByRole('button', { name: '发送' }))

    expect(api.uploadDocument).toHaveBeenCalledWith(file, '其他资料')
    expect(api.chat).toHaveBeenCalledWith(expect.objectContaining({ message: expect.stringContaining('resume.pdf') }))
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
})
