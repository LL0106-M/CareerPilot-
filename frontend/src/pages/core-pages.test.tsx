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
  it('renders Home with companion entry, quick thought and Dreaming', () => {
    renderAt('/')
    expect(screen.getByRole('heading', { name: /You don't choose a future/ })).toBeInTheDocument()
    expect(screen.getByLabelText('记录一个小想法')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Dreaming' })).toBeInTheDocument()
  })

  it('keeps Dreaming as a dedicated page', () => {
    renderAt('/dreaming')
    expect(screen.getByRole('heading', { name: '让零散想法在夜里慢慢相遇' })).toBeInTheDocument()
    expect(screen.getAllByText(/条证据/).length).toBeGreaterThan(0)
  })

  it('lets the agent decide the chat support mode', () => {
    renderAt('/chat')
    expect(screen.getByText('泊泊会自己判断如何回应')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '倾听' })).not.toBeInTheDocument()
  })
})
