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
    await user.click(screen.getByRole('button',{name:/这很像我/}))
    expect(fetchMock).toHaveBeenNthCalledWith(2,'/v1/me/hypotheses/h1/decision',expect.objectContaining({method:'POST'}))
  })
})
