import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { JobsPage } from './jobs/JobsPage'
import { PersonalPage } from './personal/PersonalPage'
import { PreparationPage } from './preparation/PreparationPage'

afterEach(() => vi.unstubAllGlobals())
function json(value: unknown) { return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } }) }

describe('knowledge pages', () => {
  it('loads jobs from the backend and filters by company type', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [
      { id:'1', company_type:'央企', company:'中国移动', role:'产品运营', role_family:'产品', location:'北京', deadline:'2026-11-08', deadline_status:'招聘中', source:'官网', source_url:'https://example.com' },
      { id:'2', company_type:'民营企业', company:'腾讯', role:'AI 产品经理', role_family:'AI 产品', location:'深圳', deadline:'2026-10-28', deadline_status:'即将截止', source:'官网', source_url:'https://example.com' },
    ] })))
    const user = userEvent.setup()
    render(<MemoryRouter><JobsPage /></MemoryRouter>)
    expect(await screen.findAllByText('中国移动')).not.toHaveLength(0)
    await user.selectOptions(screen.getByLabelText('企业类型'), '央企')
    expect(screen.getAllByText('腾讯')).toHaveLength(1)
  })

  it('shows curated AI resources and switches collections', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><PreparationPage /></MemoryRouter>)
    expect(screen.getAllByText('Machine Learning Crash Course').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: '产品设计' }))
    expect(screen.getAllByText('People + AI Guidebook').length).toBeGreaterThan(0)
  })

  it('does not fabricate personal documents when the backend is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [] })))
    render(<MemoryRouter><PersonalPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('你的资料，只在你需要时出现')).toBeInTheDocument())
    expect(screen.queryByText(/基础简历/)).not.toBeInTheDocument()
  })
})
