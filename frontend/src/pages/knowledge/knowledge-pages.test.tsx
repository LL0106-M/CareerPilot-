import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { App } from '../../app/App'

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  )
}

describe('knowledge pages', () => {
  it('filters the jobs table by company type', async () => {
    const user = userEvent.setup()
    renderAt('/knowledge/jobs')

    await user.selectOptions(screen.getByLabelText('企业类型'), '央企')
    expect(screen.getByText('中国移动')).toBeInTheDocument()
    expect(screen.queryByText('腾讯')).not.toBeInTheDocument()
  })

  it('switches preparation categories', async () => {
    const user = userEvent.setup()
    renderAt('/knowledge/preparation')

    await user.click(screen.getByRole('button', { name: '笔试' }))
    await user.click(screen.getByRole('button', { name: '考题' }))
    expect(screen.getByText('国央企产品运营往年笔试题')).toBeInTheDocument()
  })

  it('opens personal document upload with all three categories', async () => {
    const user = userEvent.setup()
    renderAt('/knowledge/personal')

    await user.click(screen.getByRole('button', { name: '上传个人资料' }))
    for (const category of ['简历', '项目与作品集', '其他资料']) {
      expect(screen.getByRole('option', { name: category })).toBeInTheDocument()
    }
  })
})
