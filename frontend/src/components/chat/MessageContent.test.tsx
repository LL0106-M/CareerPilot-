import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MessageContent } from './MessageContent'


describe('MessageContent', () => {
  it('renders short paragraphs, restrained bold text, headings, and bullet lists', () => {
    const { container } = render(
      <MessageContent content={'## 先看这里\n\n这是第一段。\n\n**关键区分**\n\n- 当前事实\n- 暂时判断'} />,
    )

    expect(screen.getByRole('heading', { name: '先看这里' })).toBeInTheDocument()
    expect(screen.getByText('这是第一段。').tagName).toBe('P')
    expect(screen.getByText('关键区分').tagName).toBe('STRONG')
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(container.querySelectorAll('p')).toHaveLength(2)
  })

  it('keeps HTML-looking model output as inert text', () => {
    const { container } = render(
      <MessageContent content={'<script>alert("no")</script>\n\n**安全文本**'} />,
    )

    expect(screen.getByText('<script>alert("no")</script>')).toBeInTheDocument()
    expect(container.querySelector('script')).not.toBeInTheDocument()
    expect(screen.getByText('安全文本').tagName).toBe('STRONG')
  })
})
