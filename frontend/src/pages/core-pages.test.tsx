import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from '../app/App'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('core pages', () => {
  it('renders Today with a Dreaming summary and today direction', () => {
    renderAt('/today')
    expect(screen.getByRole('heading', { name: '早上好，今天想从哪里继续？' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '今日航向' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '昨夜的 Dreaming' })).toBeInTheDocument()
  })

  it('keeps Dreaming as a dedicated page', () => {
    renderAt('/dreaming')
    expect(screen.getByRole('heading', { name: '让零散想法在夜里慢慢相遇' })).toBeInTheDocument()
    expect(screen.getAllByText(/条证据/).length).toBeGreaterThan(0)
  })

  it('renders the four explicit chat support modes', () => {
    renderAt('/chat')
    for (const mode of ['倾听', '梳理', '探索', '行动']) {
      expect(screen.getByRole('button', { name: mode })).toBeInTheDocument()
    }
  })
})
