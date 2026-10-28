import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from './App'

describe('CareerPilot app shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      const url = String(input)
      const payload = url === '/v1/auth/me'
        ? { id: 'a1', username: '泊泊用户', email: 'pilot@example.com' }
        : { hypotheses: [], journey: [], ideas: [], dreaming: [], memories: [] }
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('shows the brand and the five approved primary destinations', async () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect((await screen.findAllByRole('img', { name: 'CareerPilot' })).length).toBeGreaterThan(0)
    for (const label of ['首页', '对话', '罗盘', '航程', '知识库']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
    expect(screen.queryByRole('link', { name: '记忆' })).not.toBeInTheDocument()
  })

  it('routes the root URL to the homepage', async () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )
    expect(await screen.findByRole('main')).toBeInTheDocument()
  })
})
