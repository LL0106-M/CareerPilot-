import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../../auth/AuthProvider'
import { AppShell } from './AppShell'

describe('AppShell account menu', () => {
  it('shows the signed-in username and logs out from the top-right menu', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'a1', username: '泊泊用户', email: 'pilot@example.com' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<MemoryRouter><AuthProvider><AppShell><div>内容</div></AppShell></AuthProvider></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('button', { name: '泊泊用户的账户菜单' })).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: '泊泊用户的账户菜单' }))

    expect(screen.getByText('pilot@example.com')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: '设置' })).toBeInTheDocument()
    await user.click(screen.getByRole('menuitem', { name: '退出登录' }))
    expect(fetchMock).toHaveBeenLastCalledWith('/v1/auth/logout', expect.objectContaining({ method: 'POST' }))
  })
})
