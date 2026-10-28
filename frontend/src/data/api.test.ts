import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'
import { AUTH_EXPIRED_EVENT } from '../auth/auth-events'

describe('CareerPilot API client', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('sends chat without a client-controlled user id and keeps cookies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      conversation_id: 'conversation-1',
      run_id: 'run-1',
      result_status: 'completed',
      reply: '我在。',
      support_mode: 'listen',
      primary_intent: 'emotional_support',
      retrieval_sources: [],
      memory_read_status: 'ok',
      memory_write_status: 'skipped',
      dreaming_status: 'queued',
      memory_ids: [],
      citation_ids: [],
      citation_warnings: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)

    await api.chat({ message: '今天有点乱' })

    expect(fetchMock).toHaveBeenCalledWith('/v1/chat', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({ message: '今天有点乱' }),
    }))
    expect(fetchMock.mock.calls[0][1].body).not.toContain('user_id')
  })

  it('streams fragmented SSE deltas and returns the completed chat response', async () => {
    const encoder = new TextEncoder()
    const chunks = [
      'event: delta\ndata: {"text":"先',
      '别急，"}\n\nevent: delta\ndata: {"text":"我们一起看。"}\n\n',
      'event: completed\ndata: {"conversation_id":"c1","run_id":"r1","result_status":"completed","reply":"先别急，我们一起看。","support_mode":"listen","primary_intent":"emotional_support","retrieval_sources":[],"memory_read_status":"ok","memory_write_status":"skipped","dreaming_status":"skipped","memory_ids":[],"citation_ids":[],"citation_warnings":[]}\n\n',
    ]
    const stream = new ReadableStream({
      start(controller) {
        chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)))
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(new Response(stream, {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const deltas: string[] = []

    const result = await api.chatStream({ message: '今天有点乱' }, (text) => deltas.push(text))

    expect(deltas).toEqual(['先别急，', '我们一起看。'])
    expect(result.reply).toBe('先别急，我们一起看。')
    expect(fetchMock).toHaveBeenCalledWith('/v1/chat/stream', expect.objectContaining({
      method: 'POST', credentials: 'include', body: JSON.stringify({ message: '今天有点乱' }),
    }))
  })

  it('loads conversation summaries and a selected conversation', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{
        id: 'c1', title: '真实会话', updated_at: '2026-10-28T08:00:00Z', message_count: 2,
      }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id: 'c1', title: '真实会话', updated_at: '2026-10-28T08:00:00Z',
        messages: [{ role: 'user', content: '你好' }, { role: 'agent', content: '我在。' }],
      }), { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)

    const summaries = await api.getConversations()
    const selected = await api.getConversation('c1')

    expect(summaries.items[0].title).toBe('真实会话')
    expect(selected.messages).toEqual([
      { role: 'user', content: '你好' }, { role: 'agent', content: '我在。' },
    ])
  })

  it('announces an expired session when streaming chat returns 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 401 })))
    const listener = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, listener)

    await expect(api.chatStream({ message: '你好' }, vi.fn())).rejects.toMatchObject({ status: 401 })

    expect(listener).toHaveBeenCalledOnce()
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener)
  })

  it('creates an explicitly authorized idea', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 'idea-1' }), {
      status: 201,
      headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.createIdea('把作品集再讲清楚一点')

    expect(fetchMock).toHaveBeenCalledWith('/v1/me/ideas', expect.objectContaining({
      method: 'POST',
      credentials: 'include',
      body: JSON.stringify({
        raw_text: '把作品集再讲清楚一点',
        title: '把作品集再讲清楚一点',
        authorization: 'granted',
        sensitivity: 'normal',
      }),
    }))
  })

  it('normalizes server failures into a readable ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'service unavailable' }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })))

    await expect(api.getDashboard()).rejects.toMatchObject({
      name: 'ApiError',
      status: 503,
      message: 'service unavailable',
    })
  })

  it('uploads supported personal files as binary content', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 'doc-1', title: 'resume.pdf', category: '简历', file_format: 'PDF', size_text: '3 B',
      uploaded_at: 'now', status: '解析中', retrieval_enabled: false,
    }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['pdf'], 'resume.pdf', { type: 'application/pdf' })

    await api.uploadDocument(file, '简历')

    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/v1/me/documents?'), expect.objectContaining({
      method: 'POST', body: file, credentials: 'include',
    }))
  })
})
