import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../../auth/AuthProvider'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  it('submits username-or-email, password and remember-me then enters the app', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'authentication required' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'a1', username: '泊泊用户', email: 'pilot@example.com' }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<MemoryRouter initialEntries={['/login']}><AuthProvider><Routes><Route path="/login" element={<LoginPage />} /><Route path="/" element={<div>首页已登录</div>} /></Routes></AuthProvider></MemoryRouter>)
    await screen.findByRole('heading', { name: '欢迎回来' })
    await user.type(screen.getByLabelText('用户名或邮箱'), 'pilot@example.com')
    await user.type(screen.getByLabelText('密码'), 'A secure passphrase 2026!')
    await user.click(screen.getByLabelText('记住我（5 天内免登录）'))
    await user.click(screen.getByRole('button', { name: '登录' }))

    await waitFor(() => expect(screen.getByText('首页已登录')).toBeInTheDocument())
    expect(JSON.parse(String(fetchMock.mock.calls[1][1]?.body))).toEqual({
      identifier: 'pilot@example.com', password: 'A secure passphrase 2026!', remember_me: true,
    })
  })
})
