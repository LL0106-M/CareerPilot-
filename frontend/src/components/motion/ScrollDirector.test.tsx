import { act, render } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { ScrollDirector } from './ScrollDirector'

function RouteButton() {
  const navigate = useNavigate()
  return <button onClick={() => navigate('/next')}>next</button>
}

describe('ScrollDirector', () => {
  it('updates the global scroll progress and resets scroll on navigation', () => {
    const scrollTo = vi.fn()
    vi.stubGlobal('scrollTo', scrollTo)
    Object.defineProperty(document.documentElement, 'scrollHeight', { configurable: true, value: 2000 })
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 1000 })
    Object.defineProperty(window, 'scrollY', { configurable: true, value: 500 })

    const view = render(<MemoryRouter><ScrollDirector /><RouteButton /></MemoryRouter>)
    act(() => window.dispatchEvent(new Event('scroll')))
    expect(document.documentElement.style.getPropertyValue('--page-scroll')).toBe('0.5000')

    view.getByRole('button', { name: 'next' }).click()
    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'instant' })
  })
})
