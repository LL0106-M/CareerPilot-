import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, it, vi } from 'vitest'

import { App } from './App'

afterEach(() => vi.unstubAllGlobals())

it('keeps the user intent while moving from home chat into the connected product pages', async () => {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input)
    if (url === '/v1/chat/stream') {
      const completed = {
        conversation_id: 'c1', run_id: 'r1', result_status: 'completed', reply: '我们先收集一条真实证据。',
        support_mode: 'explore', primary_intent: 'career_exploration', retrieval_sources: [], memory_read_status: 'ok',
        memory_write_status: 'skipped', dreaming_status: 'queued', memory_ids: [], citation_ids: [], citation_warnings: [],
      }
      return Promise.resolve(new Response(
        `event: delta\ndata: {"text":"我们先收集一条真实证据。"}\n\nevent: completed\ndata: ${JSON.stringify(completed)}\n\n`,
        { status: 200, headers: { 'Content-Type': 'text/event-stream' } },
      ))
    }
    const payload = url === '/v1/auth/me'
      ? { id: 'a1', username: '泊泊用户', email: 'pilot@example.com' }
      : url === '/v1/me/conversations'
        ? { items: [] }
        : { hypotheses: [], journey: [], ideas: [], dreaming: [], memories: [] }
    return Promise.resolve(new Response(JSON.stringify(payload), {
      status: 200, headers: { 'Content-Type': 'application/json' },
    }))
  })
  vi.stubGlobal('fetch', fetchMock)
  vi.stubGlobal('scrollTo', vi.fn())
  const user = userEvent.setup()
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)

  await user.type(await screen.findByLabelText('现在，想从哪里开始？'), '我想探索 AI 产品方向')
  await user.click(screen.getByRole('button', { name: '进入对话' }))
  expect(screen.getByLabelText('给泊泊发送消息')).toHaveValue('我想探索 AI 产品方向')
  await user.click(screen.getByRole('button', { name: '发送' }))
  expect(await screen.findByText('我们先收集一条真实证据。')).toBeInTheDocument()

  await user.click(screen.getByRole('link', { name: '罗盘' }))
  expect(await screen.findByRole('heading', { name: /哪一种方向/ })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: '航程' }))
  expect(await screen.findByRole('heading', { name: /一段正在发生的路/ })).toBeInTheDocument()
  await user.click(screen.getByRole('link', { name: '知识库' }))
  expect(await screen.findByRole('heading', { name: '知识库' })).toBeInTheDocument()
}, 15_000)
