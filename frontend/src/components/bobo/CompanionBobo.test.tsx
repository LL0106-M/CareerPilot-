import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../data/api'
import { CompanionBobo } from './CompanionBobo'
import { getCompanionConfig } from './companionConfig'

vi.mock('../../data/api', () => ({ api: {
  chatStream: vi.fn(),
  getConversation: vi.fn(),
} }))

describe('companion Bobo', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api.chatStream).mockReset()
    vi.mocked(api.getConversation).mockReset()
  })

  it('gives core pages distinct companion personalities', () => {
    expect(getCompanionConfig('/').mood).toBe('idle')
    expect(getCompanionConfig('/compass').mood).toBe('explore')
    expect(getCompanionConfig('/journey').mood).toBe('act')
    expect(getCompanionConfig('/knowledge/jobs').mood).toBe('organize')
    expect(getCompanionConfig('/dreaming').mood).toBe('dreaming')
    expect(new Set([
      getCompanionConfig('/').prompt,
      getCompanionConfig('/compass').prompt,
      getCompanionConfig('/journey').prompt,
      getCompanionConfig('/knowledge/jobs').prompt,
    ]).size).toBe(4)
  })

  it('opens a contextual side conversation from the page', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/compass']}><CompanionBobo /></MemoryRouter>)

    await user.click(screen.getByRole('button', { name: '打开泊泊侧边对话' }))

    expect(screen.getByRole('complementary', { name: '泊泊侧边对话' })).toBeInTheDocument()
    expect(screen.getByText('正在看：罗盘')).toBeInTheDocument()
    expect(screen.getByText('一起看看这个方向还缺什么。')).toBeInTheDocument()
  })

  it('does not duplicate Bobo inside the full chat page', () => {
    render(<MemoryRouter initialEntries={['/chat']}><CompanionBobo /></MemoryRouter>)
    expect(screen.queryByRole('button', { name: '打开泊泊侧边对话' })).not.toBeInTheDocument()
  })

  it('closes the side conversation with Escape', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/journey']}><CompanionBobo /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '打开泊泊侧边对话' }))
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('complementary', { name: '泊泊侧边对话' })).not.toBeInTheDocument()
  })

  it('streams a page-aware reply and retains the shared conversation id', async () => {
    vi.mocked(api.chatStream).mockImplementation(async (_body, onDelta) => {
      onDelta('先看看你最在意的未知。')
      return {
        conversation_id: 'companion-1', run_id: 'run-1', result_status: 'completed',
        reply: '先看看你最在意的未知。', support_mode: 'explore', primary_intent: 'career_direction',
        retrieval_sources: [], memory_read_status: 'available', memory_write_status: 'skipped',
        memory_provider_status: 'skipped', dreaming_status: 'skipped', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
    })
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/compass']}><CompanionBobo /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '打开泊泊侧边对话' }))
    await user.type(screen.getByLabelText('给泊泊发送消息'), '我为什么还在犹豫？')
    await user.click(screen.getByRole('button', { name: '发送给泊泊' }))

    expect(await screen.findByText('先看看你最在意的未知。')).toBeInTheDocument()
    expect(api.chatStream).toHaveBeenCalledWith({
      message: '我为什么还在犹豫？',
      page_context: { page: 'compass', label: '罗盘', path: '/compass' },
    }, expect.any(Function))
    expect(localStorage.getItem('careerpilot.companionConversationId')).toBe('companion-1')
    expect(screen.getByRole('link', { name: /进入完整对话/ })).toHaveAttribute('href', '/chat')
    expect(screen.getByText('这轮没有新增长期记忆')).toBeInTheDocument()
  })

  it('restores the draft when sending fails', async () => {
    vi.mocked(api.chatStream).mockRejectedValue(new Error('暂时没有送达'))
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/journey']}><CompanionBobo /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '打开泊泊侧边对话' }))
    await user.type(screen.getByLabelText('给泊泊发送消息'), '帮我看看下一步')
    await user.click(screen.getByRole('button', { name: '发送给泊泊' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('暂时没有送达')
    expect(screen.getByLabelText('给泊泊发送消息')).toHaveValue('帮我看看下一步')
  })

  it('reopens a retained companion conversation instead of getting stuck loading', async () => {
    localStorage.setItem('careerpilot.companionConversationId', 'companion-existing')
    vi.mocked(api.getConversation).mockResolvedValue({
      id: 'companion-existing', title: '已有对话', updated_at: '2026-11-14T10:00:00Z',
      messages: [{ role: 'user', content: '刚才说到哪里？' }, { role: 'agent', content: '我们说到下一步验证。' }],
    })
    const user = userEvent.setup()
    render(<MemoryRouter initialEntries={['/compass']}><CompanionBobo /></MemoryRouter>)
    await user.click(screen.getByRole('button', { name: '打开泊泊侧边对话' }))

    expect(await screen.findByText('我们说到下一步验证。')).toBeInTheDocument()
    expect(screen.queryByText('正在接上刚才的对话…')).not.toBeInTheDocument()
  })
})
