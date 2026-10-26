import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('CareerPilot app shell', () => {
  it('shows the brand and the five approved primary destinations', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole('img', { name: 'CareerPilot' }).length).toBeGreaterThan(0)
    for (const label of ['首页', '对话', '罗盘', '航程', '知识库']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
    expect(screen.queryByRole('link', { name: '记忆' })).not.toBeInTheDocument()
  })

  it('routes the root URL to the homepage', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <App />
      </MemoryRouter>,
    )
    expect(screen.getByRole('main')).toBeInTheDocument()
  })
})
