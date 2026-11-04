import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const moduleLoads = vi.hoisted(() => ({ today: vi.fn() }))

vi.mock('../pages/today/TodayPage', () => {
  moduleLoads.today()
  return { TodayPage: () => <main>首页模块</main> }
})

import { App } from './App'

describe('route-level loading', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('does not load the authenticated homepage module for a guest login visit', async () => {
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response(
      JSON.stringify({ detail: 'not authenticated' }),
      { status: 401, headers: { 'Content-Type': 'application/json' } },
    ))))

    render(<MemoryRouter initialEntries={['/login']}><App /></MemoryRouter>)

    expect(await screen.findByRole('heading', { name: '欢迎回来' })).toBeInTheDocument()
    expect(moduleLoads.today).not.toHaveBeenCalled()
  })
})
