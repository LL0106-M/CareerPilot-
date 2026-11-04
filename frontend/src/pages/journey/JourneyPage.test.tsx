import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { JourneyPage } from './JourneyPage'

afterEach(() => vi.unstubAllGlobals())

describe('Journey', () => {
  it('uses path as the default view and can switch to calendar', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({ hypotheses:[],journey:[{id:'t1',title:'完成岗位拆解',due:'2026-10-28',state:'准备开始',related:'AI 产品经理',why:'验证岗位匹配'},{id:'t2',title:'联系一位从业者',due:'本周',state:'准备开始',related:'AI 产品经理',why:'验证工作内容'}],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} })))
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)
    expect((await screen.findAllByText('完成岗位拆解')).length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button',{name:/日历/}))
    expect(screen.getByRole('heading',{name:'2026 年 10 月'})).toBeInTheDocument()
    expect(screen.getByText('28').closest('.calendar-cell')).toHaveTextContent('完成岗位拆解')
    expect(screen.getByText('未安排具体日期')).toBeInTheDocument()
    expect(screen.getByText('联系一位从业者')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:/足迹/}))
    expect(screen.getByRole('heading',{name:'真实行动留下的足迹'})).toBeInTheDocument()
  })

  it('requests a real external-action preview before offering confirmation', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[{id:'t1',title:'完成岗位拆解',due:'今天',state:'准备开始',related:'AI 产品经理',why:'验证岗位匹配'}],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ action_id:'a1',provider_id:'feishu',capability:'calendar.create',payload:{title:'完成岗位拆解'},preview_hash:'hash-1',requires_confirmation:true }), { status:201,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:/调用其他 App/}))
    await user.click(screen.getByRole('button',{name:'生成预览'}))

    expect(fetchMock).toHaveBeenNthCalledWith(2,'/v1/me/actions/preview',expect.objectContaining({ method:'POST' }))
    expect(await screen.findByText('等待你的最终确认')).toBeInTheDocument()
  })

  it('creates a local calendar event manually before any external sync', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id:'event-1',title:'腾讯产品二面',due:'2026-10-30',state:'准备开始',related:'个人日程',start_at:'2026-10-30T15:00:00+08:00',end_at:'2026-10-30T16:00:00+08:00',reminder_minutes:30,meeting_url:'https://meeting.tencent.com/dm/abc',created_via:'manual' }), { status:201,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[{ id:'event-1',title:'腾讯产品二面',due:'2026-10-30',state:'准备开始',related:'个人日程',start_at:'2026-10-30T15:00:00+08:00',end_at:'2026-10-30T16:00:00+08:00',reminder_minutes:30,meeting_url:'https://meeting.tencent.com/dm/abc',created_via:'manual' }],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:'添加日程'}))
    await user.type(screen.getByLabelText('日程标题'),'腾讯产品二面')
    await user.type(screen.getByLabelText('开始时间'),'2026-10-30T15:00')
    await user.selectOptions(screen.getByLabelText('提醒时间'),'30')
    await user.type(screen.getByLabelText('腾讯会议链接'),'https://meeting.tencent.com/dm/abc')
    await user.click(screen.getByRole('button',{name:'保存到 CareerPilot'}))

    expect(fetchMock).toHaveBeenNthCalledWith(2,'/v1/me/journey',expect.objectContaining({ method:'POST' }))
    const createBody = JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))
    expect(createBody.start_at).toMatch(/^2026-10-30T15:00:00\+\d{2}:\d{2}$/)
    expect(await screen.findByText('日程已保存到 CareerPilot。')).toBeInTheDocument()
  })

  it('shows reminder and Tencent Meeting details on a saved local event', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({ hypotheses:[],journey:[{id:'event-1',title:'腾讯产品二面',due:'2026-10-30',state:'准备开始',related:'个人日程',start_at:'2026-10-30T15:00:00+08:00',end_at:'2026-10-30T16:00:00+08:00',reminder_minutes:30,meeting_url:'https://meeting.tencent.com/dm/abc',created_via:'chat'}],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} })))
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:/日历/}))

    expect(screen.getByText('提前 30 分钟提醒')).toBeInTheDocument()
    expect(screen.getByRole('link',{name:'加入腾讯会议'})).toHaveAttribute('href','https://meeting.tencent.com/dm/abc')
  })

  it('keeps a successful local save successful when the follow-up reload fails', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id:'event-1',title:'复盘',due:'2026-10-30',state:'准备开始',related:'个人日程' }), { status:201,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail:'reload failed' }), { status:500,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button',{name:'添加日程'}))
    await user.type(screen.getByLabelText('日程标题'),'复盘')
    await user.type(screen.getByLabelText('开始时间'),'2026-10-30T15:00')
    await user.click(screen.getByRole('button',{name:'保存到 CareerPilot'}))

    expect(await screen.findByText('日程已保存到 CareerPilot。')).toBeInTheDocument()
    expect(screen.queryByText('日程没有保存成功，请重试。')).not.toBeInTheDocument()
  })

  it('syncs the selected saved event time to Feishu preview', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[{id:'event-1',title:'腾讯产品二面',due:'2026-10-30',state:'准备开始',related:'个人日程',start_at:'2026-10-30T15:00:00+08:00',end_at:'2026-10-30T16:00:00+08:00'}],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ action_id:'a1',provider_id:'feishu',capability:'calendar.create',payload:{},preview_hash:'hash-1',requires_confirmation:true }), { status:201,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)
    await user.click(await screen.findByRole('button',{name:/日历/}))
    await user.click(screen.getByRole('button',{name:'同步“腾讯产品二面”到飞书'}))
    await user.click(screen.getByRole('button',{name:'生成预览'}))

    const body = JSON.parse(String((fetchMock.mock.calls[1]?.[1] as RequestInit).body))
    expect(body.payload.start).toBe('2026-10-30T15:00:00+08:00')
    expect(body.payload.end).toBe('2026-10-30T16:00:00+08:00')
  })
})
