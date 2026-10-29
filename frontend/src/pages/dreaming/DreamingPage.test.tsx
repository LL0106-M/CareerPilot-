import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api, type DreamingResult } from '../../data/api'
import { DreamingPage } from './DreamingPage'

vi.mock('../../data/api', () => ({
  api: {
    getDreamingToday: vi.fn(), startDreaming: vi.fn(), getDreamingJob: vi.fn(),
    confirmDreamingHypothesis: vi.fn(),
  },
}))

const result: DreamingResult = {
  id: 'result-1', local_date: '2026-10-29', version: 1, updated_at: '2026-10-29T08:00:00Z',
  summary: '你持续在验证产品方向', wins: ['完成一次用户访谈'], ideas: ['做求职产品'],
  blockers: [], open_loops: ['还需验证付费意愿'], tomorrow_step: '再访谈一位用户',
  hypotheses: [{ statement: '你可能适合 AI 产品探索', confidence_band: 'medium', supporting_evidence_ids: ['e1'], open_questions: ['是否喜欢长期迭代？'] }],
}

describe('Dreaming page', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api.getDreamingToday).mockReset()
    vi.mocked(api.startDreaming).mockReset()
    vi.mocked(api.getDreamingJob).mockReset()
    vi.mocked(api.confirmDreamingHypothesis).mockReset()
  })

  it('starts a seven-day Dreaming and renders the completed result', async () => {
    vi.mocked(api.getDreamingToday).mockRejectedValue(new Error('not found'))
    vi.mocked(api.startDreaming).mockResolvedValue({ job_id: 'job-1', status: 'queued', local_date: '2026-10-29' })
    vi.mocked(api.getDreamingJob).mockResolvedValue({ job_id: 'job-1', status: 'completed', local_date: '2026-10-29', error: null, result })
    render(<DreamingPage />)
    await userEvent.click(await screen.findByRole('button', { name: '开始 Dreaming' }))
    expect(await screen.findByText('你持续在验证产品方向')).toBeInTheDocument()
    expect(screen.getByText('你可能适合 AI 产品探索')).toBeInTheDocument()
  })

  it('updates todays result and confirms a direction into Compass', async () => {
    vi.mocked(api.getDreamingToday).mockResolvedValue(result)
    vi.mocked(api.confirmDreamingHypothesis).mockResolvedValue({ memory_id: 'h1', status: 'confirmed' })
    render(<DreamingPage />)
    expect(await screen.findByRole('button', { name: '重新生成并更新今天的结果' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '确认并加入罗盘' }))
    await waitFor(() => expect(api.confirmDreamingHypothesis).toHaveBeenCalledWith('result-1', 0))
    expect(await screen.findByText('已加入罗盘')).toBeInTheDocument()
  })
})
