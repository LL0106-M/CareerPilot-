import '@testing-library/jest-dom/vitest'
import React from 'react'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(cleanup)

vi.mock('framer-motion', () => ({
  motion: new Proxy({}, {
    get: (_target, tag: string) => React.forwardRef<HTMLElement, Record<string, unknown>>(
      ({ animate: _animate, transition: _transition, whileHover: _whileHover, whileTap: _whileTap, ...props }, ref) =>
        React.createElement(tag, { ...props, ref }),
    ),
  }),
  useReducedMotion: () => true,
}))

// jsdom exposes scrollTo but throws "not implemented" when route transitions
// reset the viewport. Keep the browser behavior covered by ScrollDirector's
// focused test while giving page-level tests a stable DOM implementation.
Object.defineProperty(window, 'scrollTo', {
  configurable: true,
  writable: true,
  value: vi.fn(),
})
