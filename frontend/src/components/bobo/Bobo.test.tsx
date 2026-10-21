import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Bobo } from './Bobo'

describe('Bobo', () => {
  it.each([
    ['idle', '泊泊正在陪伴你'],
    ['listen', '泊泊正在倾听'],
    ['organize', '泊泊正在帮你梳理'],
    ['explore', '泊泊正在和你探索'],
    ['act', '泊泊准备和你行动'],
    ['thinking', '泊泊正在思考'],
    ['dreaming', '泊泊正在 Dreaming'],
  ] as const)('maps %s to an accessible state', (mood, label) => {
    render(<Bobo mood={mood} />)
    const figure = screen.getByRole('img', { name: label })
    expect(figure).toHaveAttribute('data-mood', mood)
  })
})
