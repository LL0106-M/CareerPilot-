import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { JobsPage } from './jobs/JobsPage'
import { PersonalPage } from './personal/PersonalPage'
import { PreparationPage } from './preparation/PreparationPage'
import { InterviewArchivePage } from './interview/InterviewArchivePage'

afterEach(() => vi.unstubAllGlobals())
function json(value: unknown) { return new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } }) }

describe('knowledge pages', () => {
  it('labels interview experiences separately from learning resources', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(json({items:[{
      id:'i1',title:'产品经理一面面经',publisher:'候选人经验',year:'2025',round:'一面',trust:'experience',
      url:'https://example.com/interview',excerpt:'候选人回忆的一面问题。',updated_at:'2026-11-04',source_type:'experience_report',
    }]})))
    render(<MemoryRouter><InterviewArchivePage /></MemoryRouter>)
    expect(await screen.findByText('产品经理一面面经')).toBeInTheDocument()
    expect(screen.getByText('经验帖 · 待交叉验证')).toBeInTheDocument()
    expect(screen.getByText(/不代表未来一定出现/)).toBeInTheDocument()
    expect(screen.getByRole('button',{name:'刷新'})).toHaveClass('library-refresh')
    expect(screen.getByRole('heading',{name:'往年题目与面经'}).closest('.library-dashboard')).toHaveClass('library-dashboard--single')
  })
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
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [] })))
    const user = userEvent.setup()
    render(<MemoryRouter><PreparationPage /></MemoryRouter>)
    expect(screen.getAllByText('Machine Learning Crash Course').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: '产品设计' }))
    expect(screen.getAllByText('People + AI Guidebook').length).toBeGreaterThan(0)
  })

  it('shows newly collected preparation material from the backend', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [{
      id:'live-1', title:'2026 AI 产品实践课', publisher:'Example University', category:'产品设计',
      format:'网页', url:'https://example.com/course', description:'刚刚在对话中收集的资料。',
      updated_at:'2026-10-28T00:00:00+00:00', source_type:'web_search',
    }] })))

    render(<MemoryRouter><PreparationPage /></MemoryRouter>)

    expect(await screen.findAllByText('2026 AI 产品实践课')).not.toHaveLength(0)
    expect(screen.getByText('刚刚在对话中收集的资料。')).toBeInTheDocument()
  })

  it('keeps unverified job search results separate from active jobs', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [], collected_sources: [{
      id:'source-1', title:'AI 产品岗位汇总', publisher:'示例招聘站',
      url:'https://example.com/jobs', description:'需要打开原网页核实岗位状态。',
      updated_at:'2026-10-29T08:00:00+00:00', source_type:'web_search',
    }] })))

    render(<MemoryRouter><JobsPage /></MemoryRouter>)

    expect(await screen.findByText('待核实的岗位来源')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'AI 产品岗位汇总' })).toHaveAttribute('href','https://example.com/jobs')
    expect(screen.getByText('还没有保存的岗位。')).toBeInTheDocument()
  })

  it('lets the user refresh the library and see newly collected material', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ items: [] }))
      .mockResolvedValueOnce(json({ items: [{
        id:'live-2', title:'刚收录的 Agent 指南', publisher:'Example Lab', category:'工程实践',
        format:'网页', url:'https://example.com/agent', description:'来自刚才的对话收集。',
        updated_at:'2026-10-29T08:00:00+00:00', source_type:'web_search',
      }] }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><PreparationPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:'刷新知识库'}))

    expect(await screen.findAllByText('刚收录的 Agent 指南')).not.toHaveLength(0)
    expect(screen.getByText(/最近检查/)).toBeInTheDocument()
  })

  it('does not fabricate personal documents when the backend is empty', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(json({ items: [] })))
    render(<MemoryRouter><PersonalPage /></MemoryRouter>)
    await waitFor(() => expect(screen.getByText('你的资料，只在你需要时出现')).toBeInTheDocument())
    expect(screen.queryByText(/基础简历/)).not.toBeInTheDocument()
  })
})
