import { afterEach, describe, expect, it, vi } from 'vitest'

import { api } from './api'

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
})
