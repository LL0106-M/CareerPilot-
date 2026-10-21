import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from './App'

describe('CareerPilot app shell', () => {
  it('shows the brand and complete desktop navigation', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>,
    )

    expect(screen.getByRole('img', { name: 'CareerPilot' })).toBeInTheDocument()
    for (const label of ['今天', '对话', 'Dreaming', '罗盘', '航程', '知识库', '记忆']) {
      expect(screen.getByRole('link', { name: label })).toBeInTheDocument()
    }
  })
})
