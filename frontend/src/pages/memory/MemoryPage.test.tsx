import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MemoryPage } from './MemoryPage'

const memory = {
  id: 'm1',
  type: 'preference',
  content: '我更看重稳定节奏',
  status: 'active',
  sensitivity: 'normal',
  origin: 'user_explicit',
  source_type: 'conversation',
  source_reference: 'run-1',
  confidence: 'high',
  importance: 4,
  version: 1,
  created_at: '2026-11-01T00:00:00+00:00',
  updated_at: '2026-11-01T00:00:00+00:00',
  last_used_at: null,
  expires_at: null,
  deleted_at: null,
  metadata: {},
}

afterEach(() => vi.unstubAllGlobals())

describe('MemoryPage', () => {
  it('loads canonical memories and pauses one through the server', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [memory] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, status: 'paused', version: 2 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ ...memory, status: 'paused', version: 2 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<MemoryPage />)

    expect(await screen.findByText('我更看重稳定节奏')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '暂停使用' }))

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/v1/me/memories/m1/pause',
      expect.objectContaining({ method: 'POST', body: JSON.stringify({ expected_version: 1 }) }),
    )
    expect(await screen.findByRole('button', { name: '恢复使用' })).toBeInTheDocument()
  })

  it('edits and deletes canonical memory instead of changing local demo state', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [memory] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, content: '我更看重稳定且有自主权', version: 2 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [{ ...memory, content: '我更看重稳定且有自主权', version: 2 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...memory, status: 'deleted', version: 3 }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ items: [] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<MemoryPage />)
    await user.click(await screen.findByRole('button', { name: '修改' }))
    const editor = screen.getByRole('textbox', { name: '记忆内容' })
    await user.clear(editor)
    await user.type(editor, '我更看重稳定且有自主权')
    await user.click(screen.getByRole('button', { name: '保存修改' }))

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/v1/me/memories/m1',
      expect.objectContaining({ method: 'PATCH', body: JSON.stringify({ expected_version: 1, content: '我更看重稳定且有自主权' }) }),
    )
    await user.click(await screen.findByRole('button', { name: '删除' }))
    expect(fetchMock).toHaveBeenCalledTimes(3)
    await user.click(screen.getByRole('button', { name: '确认删除' }))
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      '/v1/me/memories/m1?expected_version=2',
      expect.objectContaining({ method: 'DELETE' }),
    )
    expect(await screen.findByText('当前分类下还没有记忆。')).toBeInTheDocument()
  })
})
