import { describe, expect, it } from 'vitest'

import { demoJobs, demoMaterials } from './demoRepository'
import { filterJobs, filterMaterials } from './filtering'

describe('knowledge filtering', () => {
  it('combines company type, role type and active status', () => {
    const result = filterJobs(demoJobs, {
      query: '',
      companyType: '央企',
      company: '全部',
      roleType: '产品',
      deadlineStatus: '招聘中',
    })

    expect(result.map((job) => job.company)).toEqual(['中国移动'])
  })

  it('keeps the filters and returns an empty list when nothing matches', () => {
    const result = filterJobs(demoJobs, {
      query: '不存在的岗位',
      companyType: '全部',
      company: '全部',
      roleType: '全部',
      deadlineStatus: '全部',
    })

    expect(result).toEqual([])
  })

  it('filters interview experience separately from written preparation', () => {
    expect(
      filterMaterials(demoMaterials, {
        query: '',
        primary: '面试',
        secondary: '面经',
        company: '全部',
      }).every((item) => item.secondaryCategory === '面经'),
    ).toBe(true)

    expect(
      filterMaterials(demoMaterials, {
        query: '',
        primary: '笔试',
        secondary: '准备资料',
        company: '全部',
      }).every((item) => item.primaryCategory === '笔试'),
    ).toBe(true)
  })
})
