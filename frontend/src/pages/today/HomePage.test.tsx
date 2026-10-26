import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../../data/api'
import { TodayPage } from './TodayPage'

vi.mock('../../data/api', () => ({ api: { createIdea: vi.fn() } }))

describe('homepage', () => {
  beforeEach(() => vi.mocked(api.createIdea).mockReset())

  it('saves a quick thought only after an explicit click', async () => {
    vi.mocked(api.createIdea).mockResolvedValue({ id: 'idea-1', title: '想试试 AI 产品', stage: 'captured' })
    const user = userEvent.setup()
    render(<MemoryRouter><TodayPage /></MemoryRouter>)
    await user.type(screen.getByLabelText('记录一个小想法'), '想试试 AI 产品')
    expect(api.createIdea).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '收下这个想法' }))
    expect(api.createIdea).toHaveBeenCalledWith('想试试 AI 产品')
    expect(await screen.findByText('已经替你收好了。')).toBeInTheDocument()
  })

  it('keeps Dreaming and the product footer on the same scroll page', () => {
    render(<MemoryRouter><TodayPage /></MemoryRouter>)
    expect(screen.getByRole('heading', { name: 'Dreaming' })).toBeInTheDocument()
    expect(screen.getByRole('contentinfo')).toBeInTheDocument()
  })
})
