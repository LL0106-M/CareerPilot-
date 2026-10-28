import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { AuthProvider, useAuth } from './AuthProvider'

function Probe() {
  const { status, account } = useAuth()
  return <div>{status}:{account?.username || 'none'}</div>
}

describe('AuthProvider', () => {
  it('waits for the current-account request before exposing authenticated state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      id: 'account-1', username: 'careerpilot', email: 'pilot@example.com',
    }), { status: 200, headers: { 'Content-Type': 'application/json' } })))

    render(<AuthProvider><Probe /></AuthProvider>)

    expect(screen.getByText('loading:none')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('authenticated:careerpilot')).toBeInTheDocument())
  })

  it('treats a 401 bootstrap response as a signed-out visitor', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'authentication required' }), {
      status: 401, headers: { 'Content-Type': 'application/json' },
    })))

    render(<AuthProvider><Probe /></AuthProvider>)

    await waitFor(() => expect(screen.getByText('guest:none')).toBeInTheDocument())
  })
})
