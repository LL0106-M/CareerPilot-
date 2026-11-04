import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { CompassPage } from './CompassPage'

afterEach(() => vi.unstubAllGlobals())

describe('Compass', () => {
  it('loads one direction at a time and confirms explicitly', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[{id:'h1',content:'适合有边界但能创造的环境',status:'candidate'}],journey:[],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({status:'ok'}), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[{id:'h1',content:'适合有边界但能创造的环境',status:'已确认'}],journey:[],ideas:[],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><CompassPage /></MemoryRouter>)
    expect(await screen.findByText('适合有边界但能创造的环境')).toBeInTheDocument()
    await user.click(screen.getByRole('button',{name:/加入罗盘/}))
    expect(fetchMock).toHaveBeenNthCalledWith(2,'/v1/me/hypotheses/h1/decision',expect.objectContaining({method:'POST'}))
  })

  it('keeps a captured idea as a fragment and continues it in chat', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ hypotheses:[],journey:[],ideas:[{id:'i1',memory_id:'i1',title:'做一个面试复盘工具',raw_text:'做一个面试复盘工具',stage:'captured'}],dreaming:[],memories:[] }), { status:200,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter><CompassPage /></MemoryRouter>)

    const link = await screen.findByRole('link',{name:'展开“做一个面试复盘工具”'})
    expect(link).toHaveAttribute('href','/chat')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('projects confirmed directions returned by the backend', async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({
      hypotheses:[], journey:[], ideas:[], dreaming:[], memories:[], direction_signals:[],
      directions:[{id:'d1',label:'用户确认的方向',status:'confirmed',source_signal_id:'s1',source_kind:'conversation',source_quote:'我确定要推进这个方向',reason:'用户明确表达',confidence:0.99}],
    }), { status:200,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch',fetchMock)

    render(<MemoryRouter><CompassPage /></MemoryRouter>)

    expect(await screen.findByText('用户确认的方向')).toBeInTheDocument()
    expect(screen.getByText('“我确定要推进这个方向”')).toBeInTheDocument()
    expect(screen.queryByText('验证行动已加入航程。')).not.toBeInTheDocument()
  })

  it('starts a journey only after a second explicit confirmation', async () => {
    const dashboard = {
      hypotheses:[], journey:[], journeys:[], collection_jobs:[], ideas:[], dreaming:[], memories:[],
      directions:[{id:'d1',label:'新能源产品经理',status:'confirmed',source_signal_id:'s1',source_kind:'conversation',source_quote:'我想申请新能源产品经理',reason:'明确申请意图',confidence:0.98}],
    }
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboard), { status:200,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ journey:{id:'j1',direction_id:'d1',title:'新能源产品经理',status:'active',why:'从确认方向开始'},tasks:[],collection_jobs:[] }), { status:201,headers:{'Content-Type':'application/json'} }))
      .mockResolvedValueOnce(new Response(JSON.stringify({...dashboard, journeys:[{id:'j1',direction_id:'d1',title:'新能源产品经理',status:'active',why:'从确认方向开始'}]}), { status:200,headers:{'Content-Type':'application/json'} }))
    vi.stubGlobal('fetch',fetchMock)
    const user = userEvent.setup()
    render(<MemoryRouter><CompassPage /></MemoryRouter>)

    await user.click(await screen.findByRole('button',{name:'开始航程'}))
    expect(screen.getByRole('dialog',{name:'确认开始航程'})).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await user.click(screen.getByRole('button',{name:'确认开始'}))

    expect(fetchMock).toHaveBeenNthCalledWith(2,'/v1/me/directions/d1/journey',expect.objectContaining({method:'POST'}))
    expect(await screen.findByRole('link',{name:'查看航程'})).toHaveAttribute('href','/journey')
  })

  it('shows an existing journey without offering a duplicate start action', async () => {
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({
      hypotheses:[], journey:[], ideas:[], dreaming:[], memories:[],
      journeys:[{id:'j1',direction_id:'d1',title:'新能源产品经理',status:'active',why:'从确认方向开始'}],
      directions:[{id:'d1',label:'新能源产品经理',status:'confirmed',source_signal_id:'s1',source_kind:'conversation',source_quote:'我想申请新能源产品经理',reason:'明确申请意图',confidence:0.98}],
    }), { status:200,headers:{'Content-Type':'application/json'} })))
    render(<MemoryRouter><CompassPage /></MemoryRouter>)

    expect(await screen.findByRole('link',{name:'查看航程'})).toBeInTheDocument()
    expect(screen.queryByRole('button',{name:'开始航程'})).not.toBeInTheDocument()
  })
})
