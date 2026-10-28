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
})
