import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../app/App'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('core pages', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
      if (String(input) === '/v1/me/dreaming/today') {
        return Promise.resolve(new Response(JSON.stringify({ detail: 'not found' }), {
          status: 404, headers: { 'Content-Type': 'application/json' },
        }))
      }
      const payload = String(input) === '/v1/auth/me'
        ? { id: 'a1', username: '泊泊用户', email: 'pilot@example.com' }
        : { hypotheses: [], journey: [], ideas: [], dreaming: [], memories: [] }
      return Promise.resolve(new Response(JSON.stringify(payload), {
        status: 200, headers: { 'Content-Type': 'application/json' },
      }))
    }))
  })
  afterEach(() => vi.unstubAllGlobals())

  it('renders Home with companion entry, quick thought and Dreaming', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { name: /You don't choose a future/ })).toBeInTheDocument()
    expect(screen.getByLabelText('记录一个小想法')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dreaming' })).toBeInTheDocument()
  })

  it('keeps Dreaming as a dedicated page', async () => {
    renderAt('/dreaming')
    expect(await screen.findByRole('heading', { name: '让零散想法慢慢连成线' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '开始 Dreaming' })).toBeInTheDocument()
  })

  it('lets the agent decide the chat support mode', async () => {
    renderAt('/chat')
    expect(await screen.findByText('泊泊会自己判断如何回应')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '倾听' })).not.toBeInTheDocument()
  })
})
