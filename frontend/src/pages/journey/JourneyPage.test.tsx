import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { JourneyPage } from './JourneyPage'

afterEach(() => vi.unstubAllGlobals())

describe('Journey', () => {
  it('restores the saved future letter after re-entering and refreshes it only on click', async () => {
    const dashboard = {
      hypotheses:[], ideas:[], dreaming:[], memories:[],
      journeys:[{id:'j1',direction_id:'d1',title:'AI 产品经理',status:'active',why:'验证真实匹配'}],
      journey:[{id:'t1',title:'完成岗位拆解',due:'第 1 步',state:'进行中',related:'AI 产品经理',journey_id:'j1',direction_id:'d1',why:'验证岗位匹配'}],
    }
    const savedLetter = {
      id:'letter-saved',journey_id:'j1',message:'两年后的我会怎样？',created_at:'2026-11-05T00:00:00Z',
      paths:[
        {kind:'continue',label:'沿着这条路',title:'保存的回信',summary:'这封回信来自上次访问',signals:['完成岗位拆解'],tension:'选择变窄',question:'还想继续吗？'},
        {kind:'adjacent',label:'换一条相邻的路',title:'相邻转向',summary:'已有能力换了场景',signals:[],tension:'重新证明',question:'什么能力可以带过去？'},
        {kind:'unexpected',label:'意外的第三条路',title:'作品打开入口',summary:'一次公开输出带来连接',signals:[],tension:'更不可控',question:'先公开什么？'},
      ],
    }
    const refreshedLetter = {
      ...savedLetter,
      id:'letter-refreshed',
      paths:savedLetter.paths.map((path,index) => index === 0 ? {...path,title:'再次点击后的新回信'} : path),
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = String(input)
      if (path === '/v1/me/dashboard') return new Response(JSON.stringify(dashboard),{status:200,headers:{'Content-Type':'application/json'}})
      if (path === '/v1/me/journeys/j1/future-letter' && init?.method === 'POST') return new Response(JSON.stringify(refreshedLetter),{status:201,headers:{'Content-Type':'application/json'}})
      if (path === '/v1/me/journeys/j1/future-letter') return new Response(JSON.stringify(savedLetter),{status:200,headers:{'Content-Type':'application/json'}})
      return new Response(JSON.stringify({detail:'not found'}),{status:404,headers:{'Content-Type':'application/json'}})
    })
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()

    const firstVisit = render(<MemoryRouter><JourneyPage /></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'保存的回信'})).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([,init]) => init?.method === 'POST')).toHaveLength(0)
    firstVisit.unmount()

    render(<MemoryRouter><JourneyPage /></MemoryRouter>)
    expect(await screen.findByRole('heading',{name:'保存的回信'})).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([,init]) => init?.method === 'POST')).toHaveLength(0)

    await user.click(screen.getByRole('button',{name:'给未来的我写一句话'}))
    expect(await screen.findByRole('heading',{name:'再次点击后的新回信'})).toBeInTheDocument()
    expect(fetchMock.mock.calls.filter(([,init]) => init?.method === 'POST')).toHaveLength(1)
  })

  it('opens a three-path future letter without replacing the current route', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        hypotheses:[], ideas:[], dreaming:[], memories:[],
        journeys:[{id:'j1',direction_id:'d1',title:'AI 产品经理',status:'active',why:'验证真实匹配'}],
        journey:[
          {id:'t1',title:'完成岗位拆解',due:'第 1 步',state:'进行中',related:'AI 产品经理',journey_id:'j1',direction_id:'d1',why:'验证岗位匹配'},
          {id:'t2',title:'联系一位从业者',due:'第 2 步',state:'准备开始',related:'AI 产品经理',journey_id:'j1',direction_id:'d1'},
        ],
      }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({detail:'future letter not found'}), {status:404,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        id:'letter-1',journey_id:'j1',message:'两年后的我会怎样？',created_at:'2026-11-05T00:00:00Z',
        paths:[
          {kind:'continue',label:'沿着这条路',title:'继续走深',summary:'主线逐渐清晰',signals:['完成岗位拆解'],tension:'选择变窄',question:'还想继续吗？'},
          {kind:'adjacent',label:'换一条相邻的路',title:'相邻转向',summary:'已有能力换了场景',signals:['联系一位从业者'],tension:'重新证明',question:'什么能力可以带过去？'},
          {kind:'unexpected',label:'意外的第三条路',title:'作品打开入口',summary:'一次公开输出带来连接',signals:[],tension:'更不可控',question:'先公开什么？'},
        ],
      }), { status:201,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({path_kind:'adjacent',question:'什么能力可以带过去？',created_at:'2026-11-05T00:01:00Z'}), {status:201,headers:{'Content-Type':'application/json'}}))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:'给未来的我写一句话'}))

    expect(await screen.findByRole('heading',{name:'两年后的我，回信了'})).toBeInTheDocument()
    expect(screen.getAllByText('完成岗位拆解').length).toBeGreaterThan(0)
    expect(document.querySelectorAll('.journey-route li')).toHaveLength(2)
    await user.click(screen.getByRole('tab',{name:/换一条相邻的路/}))
    expect(screen.getByRole('heading',{name:'相邻转向'})).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'带回一个问题'}))
    expect(screen.getByText('只带回这个问题，不会创建任务或记忆。')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:/确认带回/}))
    expect(await screen.findByRole('button',{name:/已带回航程/})).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(3,'/v1/me/journeys/j1/future-letter',expect.objectContaining({method:'POST'}))
    expect(fetchMock).toHaveBeenNthCalledWith(4,'/v1/me/journeys/j1/future-letter/takeaway',expect.objectContaining({method:'POST'}))
  })

  it('renders a direction journey and its three collection states from dashboard data', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({
      hypotheses:[], ideas:[], dreaming:[], memories:[],
      journeys:[{id:'j1',direction_id:'d1',title:'新能源产品经理',status:'active',why:'从确认方向开始'}],
      journey:[
        {id:'t1',title:'查看当前岗位画像与可信招聘信息',due:'第 1 步',state:'准备开始',related:'新能源产品经理',journey_id:'j1',direction_id:'d1',step_kind:'role_profile',collection_job_id:'c1'},
        {id:'t2',title:'查看往年题目与面经证据',due:'第 2 步',state:'准备开始',related:'新能源产品经理',journey_id:'j1',direction_id:'d1',step_kind:'interview_archive',collection_job_id:'c2'},
        {id:'t3',title:'选择学习资源补齐准备重点',due:'第 3 步',state:'准备开始',related:'新能源产品经理',journey_id:'j1',direction_id:'d1',step_kind:'learning_resource',collection_job_id:'c3'},
      ],
      collection_jobs:[
        {id:'c1',direction_id:'d1',purpose:'job_opportunity',query:'新能源产品经理',status:'collecting',attempts:1},
        {id:'c2',direction_id:'d1',journey_id:'j1',purpose:'interview_archive',query:'新能源产品经理',status:'queued',attempts:0},
        {id:'c3',direction_id:'d1',journey_id:'j1',purpose:'learning_resource',query:'新能源产品经理',status:'completed',attempts:1},
      ],
    }), { status:200,headers:{'Content-Type':'application/json'} })))

    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    expect(await screen.findByRole('button',{name:/新能源产品经理/})).toBeInTheDocument()
    expect(screen.getByText('岗位信息 · 收集中')).toBeInTheDocument()
    expect(screen.getByText('往年题目 · 等待收集')).toBeInTheDocument()
    expect(screen.getByText('学习资源 · 已完成')).toBeInTheDocument()
    expect(document.querySelectorAll('.collection-status-card')).toHaveLength(3)
    const route = document.querySelector('ol.journey-route')
    expect(route).toBeInTheDocument()
    expect(route?.querySelectorAll('li')).toHaveLength(3)
    expect(route?.querySelector('[class*="stop-"]')).not.toBeInTheDocument()
    expect(screen.getByRole('button',{name:/添加日程/})).toBeInTheDocument()
  })

  it('navigates one job direction by company and business line', async () => {
    const dashboard = {
      hypotheses:[], ideas:[], dreaming:[], memories:[], collection_jobs:[],
      journeys:[
        {id:'j-current',direction_id:'d-current',title:'AI 产品经理',status:'active',why:'验证方向'},
        {id:'j-old',direction_id:'d-old',title:'AI 产品经理',status:'active',why:'历史同名方向'},
      ],
      journey_branches:[
        {id:'jb-current-common',journey_id:'j-current',kind:'common',title:'通用主线',status:'active',rationale:'共同基础',company:'',business:'',role:'',location:''},
        {id:'jb-old-common',journey_id:'j-old',kind:'common',title:'通用主线',status:'active',rationale:'共同基础',company:'',business:'',role:'',location:''},
        {id:'jb-jd-retail',journey_id:'j-current',compass_branch_id:'b1',kind:'target',title:'京东｜京东零售',status:'draft',rationale:'确认后开始差异准备',company:'京东',business:'京东零售',role:'AI 产品经理',location:'北京'},
        {id:'jb-jd-logistics',journey_id:'j-current',compass_branch_id:'b2',kind:'target',title:'京东｜京东物流',status:'active',rationale:'物流业务准备',company:'京东',business:'京东物流',role:'AI 产品经理',location:'北京'},
        {id:'jb-tencent',journey_id:'j-old',compass_branch_id:'b3',kind:'target',title:'腾讯｜混元',status:'active',rationale:'混元业务准备',company:'腾讯',business:'混元',role:'AI 产品经理',location:'深圳'},
      ],
      journey:[
        {id:'t-current',title:'准备 AI 产品项目案例',due:'第 1 步',state:'准备开始',related:'AI 产品经理',journey_id:'j-current',direction_id:'d-current',journey_branch_id:'jb-current-common',scope:'common',step_kind:'role_profile'},
        {id:'t-old',title:'旧的通用任务',due:'第 1 步',state:'准备开始',related:'AI 产品经理',journey_id:'j-old',direction_id:'d-old',journey_branch_id:'jb-old-common',scope:'common',step_kind:'role_profile'},
        {id:'t-logistics',title:'拆解京东物流业务',due:'目标第 1 步',state:'准备开始',related:'京东物流',journey_id:'j-current',direction_id:'d-current',journey_branch_id:'jb-jd-logistics',scope:'branch_specific'},
        {id:'t-tencent',title:'拆解混元业务',due:'目标第 1 步',state:'准备开始',related:'混元',journey_id:'j-old',direction_id:'d-old',journey_branch_id:'jb-tencent',scope:'branch_specific'},
      ],
    }
    const activated = {
      ...dashboard,
      journey_branches: dashboard.journey_branches.map((item) => item.id === 'jb-jd-retail' ? {...item,status:'active'} : item),
      journey:[...dashboard.journey,{id:'t-retail',title:'拆解京东零售的真实业务差异',due:'目标第 1 步',state:'准备开始',related:'京东零售',journey_id:'j-current',direction_id:'d-current',journey_branch_id:'jb-jd-retail',scope:'branch_specific'}],
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboard),{status:200,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({detail:'future letter not found'}),{status:404,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify({journey:activated.journeys[0],tasks:activated.journey,branches:activated.journey_branches,collection_jobs:[]}),{status:201,headers:{'Content-Type':'application/json'}}))
      .mockResolvedValueOnce(new Response(JSON.stringify(activated),{status:200,headers:{'Content-Type':'application/json'}}))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    const directionNavigation = await screen.findByRole('navigation',{name:'选择岗位方向'})
    expect(within(directionNavigation).getAllByRole('button')).toHaveLength(1)
    expect(within(directionNavigation).getByRole('button',{name:/01.*AI 产品经理/})).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'综合路径'})).not.toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'通用主线'})).not.toBeInTheDocument()

    const companyNavigation = screen.getByRole('navigation',{name:'选择目标公司'})
    expect(within(companyNavigation).getByRole('button',{name:'京东'})).toBeInTheDocument()
    expect(within(companyNavigation).getByRole('button',{name:'腾讯'})).toBeInTheDocument()
    const businessNavigation = screen.getByRole('navigation',{name:'选择业务线'})
    expect(within(businessNavigation).getByRole('button',{name:/京东零售/})).toBeInTheDocument()
    expect(within(businessNavigation).getByRole('button',{name:/京东物流/})).toBeInTheDocument()
    expect(screen.getByLabelText('当前航程目标')).toHaveTextContent('AI 产品经理/京东/京东零售')
    expect(screen.getByText('尚未开始准备')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'开始准备这个目标'}))
    expect(screen.getByRole('dialog',{name:'确认开始目标分支'})).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:'确认开始准备'}))
    expect(await screen.findByText('拆解京东零售的真实业务差异')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenNthCalledWith(3,'/v1/me/journeys/j-current/branches/jb-jd-retail/activate',expect.objectContaining({method:'POST'}))
  })

  it('shows one collection status per purpose for the selected target journey', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({
      hypotheses:[], ideas:[], dreaming:[], memories:[],
      journeys:[
        {id:'j-jd',direction_id:'d-jd',title:'AI 产品经理',status:'active',why:'京东方向'},
        {id:'j-tencent',direction_id:'d-tencent',title:'AI 产品经理',status:'active',why:'腾讯方向'},
      ],
      journey_branches:[
        {id:'jb-jd',journey_id:'j-jd',compass_branch_id:'b-jd',kind:'target',title:'京东｜京东零售',status:'active',rationale:'京东准备',company:'京东',business:'京东零售',role:'AI 产品经理',location:'北京'},
        {id:'jb-tencent',journey_id:'j-tencent',compass_branch_id:'b-tencent',kind:'target',title:'腾讯｜混元',status:'active',rationale:'腾讯准备',company:'腾讯',business:'混元',role:'AI 产品经理',location:'深圳'},
      ],
      journey:[
        {id:'t-jd',title:'准备京东案例',due:'第 1 步',state:'准备开始',related:'AI 产品经理',journey_id:'j-jd',direction_id:'d-jd',journey_branch_id:'jb-jd',scope:'branch_specific'},
        {id:'t-tencent',title:'准备腾讯案例',due:'第 1 步',state:'准备开始',related:'AI 产品经理',journey_id:'j-tencent',direction_id:'d-tencent',journey_branch_id:'jb-tencent',scope:'branch_specific'},
      ],
      collection_jobs:[
        {id:'jd-role',direction_id:'d-jd',purpose:'job_opportunity',query:'京东 AI 产品经理',status:'queued',attempts:0},
        {id:'jd-interview',direction_id:'d-jd',journey_id:'j-jd',purpose:'interview_archive',query:'京东 AI 产品经理',status:'collecting',attempts:1},
        {id:'jd-learning',direction_id:'d-jd',journey_id:'j-jd',purpose:'learning_resource',query:'京东 AI 产品经理',status:'queued',attempts:0},
        {id:'tx-role',direction_id:'d-tencent',purpose:'job_opportunity',query:'腾讯 AI 产品经理',status:'completed',attempts:1},
        {id:'tx-interview',direction_id:'d-tencent',journey_id:'j-tencent',purpose:'interview_archive',query:'腾讯 AI 产品经理',status:'completed',attempts:1},
        {id:'tx-learning',direction_id:'d-tencent',journey_id:'j-tencent',purpose:'learning_resource',query:'腾讯 AI 产品经理',status:'completed',attempts:1},
      ],
    }), {status:200,headers:{'Content-Type':'application/json'}})))

    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    expect(await screen.findByLabelText('当前航程目标')).toHaveTextContent('AI 产品经理/京东/京东零售')
    expect(document.querySelectorAll('.collection-status-card')).toHaveLength(3)
    expect(screen.getAllByText('岗位信息 · 等待收集')).toHaveLength(1)
    expect(screen.getAllByText('往年题目 · 收集中')).toHaveLength(1)
    expect(screen.getAllByText('学习资源 · 等待收集')).toHaveLength(1)
    expect(screen.queryByText('岗位信息 · 已完成')).not.toBeInTheDocument()
  })

  it('shows a pending business line when the stored value is only AI', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({
      hypotheses:[], ideas:[], dreaming:[], memories:[], collection_jobs:[],
      journeys:[{id:'j1',direction_id:'d1',title:'AI 产品经理',status:'active',why:'验证方向'}],
      journey_branches:[
        {id:'jb1',journey_id:'j1',compass_branch_id:'b1',kind:'target',title:'京东｜AI',status:'active',rationale:'继续确认业务线',company:'京东',business:'AI',role:'AI 产品经理',location:'北京'},
      ],
      journey:[
        {id:'t1',title:'确认具体业务线',due:'第 1 步',state:'准备开始',related:'AI 产品经理',journey_id:'j1',direction_id:'d1',journey_branch_id:'jb1',scope:'branch_specific'},
      ],
    }), {status:200,headers:{'Content-Type':'application/json'}})))

    render(<MemoryRouter><JourneyPage /></MemoryRouter>)

    expect(await screen.findByRole('button',{name:'业务线待确认'})).toBeInTheDocument()
    expect(screen.getByLabelText('当前航程目标')).toHaveTextContent('AI 产品经理/京东/业务线待确认')
    expect(screen.queryByText(/\/AI$/)).not.toBeInTheDocument()
  })

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
