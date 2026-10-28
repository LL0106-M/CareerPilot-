import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../../auth/AuthProvider'
import { RegisterPage } from './RegisterPage'

describe('RegisterPage', () => {
  it('sends a code and registers without automatically logging in', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'authentication required' }), { status: 401, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'sent', expires_at: '2026-10-27T08:10:00Z', retry_after_seconds: 60 }), { status: 202, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 'a1', username: 'careerpilot', email: 'pilot@example.com' }), { status: 201, headers: { 'Content-Type': 'application/json' } }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()

    render(<MemoryRouter initialEntries={['/register']}><AuthProvider><Routes><Route path="/register" element={<RegisterPage />} /><Route path="/login" element={<div>注册成功，请登录</div>} /></Routes></AuthProvider></MemoryRouter>)
    await screen.findByRole('heading', { name: '创建账户' })
    await user.type(screen.getByLabelText('用户名'), 'careerpilot')
    await user.type(screen.getByLabelText('邮箱'), 'pilot@example.com')
    await user.click(screen.getByRole('button', { name: '发送验证码' }))
    await user.type(screen.getByLabelText('邮箱验证码'), '123456')
    await user.type(screen.getByLabelText('密码'), 'A secure passphrase 2026!')
    await user.type(screen.getByLabelText('确认密码'), 'A secure passphrase 2026!')
    await user.click(screen.getByRole('button', { name: '注册' }))

    await waitFor(() => expect(screen.getByText('注册成功，请登录')).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(3)
  }, 15_000)
})
