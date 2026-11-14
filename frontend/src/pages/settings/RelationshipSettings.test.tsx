import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'

import { SettingsPage } from './SettingsPage'

vi.mock('../../auth/AuthProvider', () => ({
  useAuth: () => ({ account: { username: '测试用户', email: 'user@example.com' } }),
}))

afterEach(() => vi.unstubAllGlobals())

it('configures situational Bobo preferences without personality labels', async () => {
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(new Response(JSON.stringify({ core:{version:'bobo-core-v1',principles:[]},dimensions:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ dimension:'challenge',value:'direct',status:'confirmed' }), { status:200,headers:{'Content-Type':'application/json'} }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ status:'reset' }), { status:200,headers:{'Content-Type':'application/json'} }))
    .mockResolvedValueOnce(new Response(JSON.stringify({ core:{version:'bobo-core-v1',principles:[]},dimensions:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
  vi.stubGlobal('fetch', fetchMock)
  const user = userEvent.setup()
  render(<SettingsPage />)

  expect(await screen.findByText('你卡住时，希望我怎么做？')).toBeInTheDocument()
  expect(screen.queryByText(/MBTI|INTJ/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name:'可以直接指出' }))
  expect(fetchMock).toHaveBeenNthCalledWith(2, '/v1/me/relationship-profile/challenge', expect.objectContaining({ method:'PUT' }))
  await user.click(screen.getByRole('button', { name:'恢复默认' }))
  expect(fetchMock).toHaveBeenNthCalledWith(3, '/v1/me/relationship-profile', expect.objectContaining({ method:'DELETE' }))
})
