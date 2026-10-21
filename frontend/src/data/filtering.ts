import type {
  JobFilters,
  JobRecord,
  MaterialFilters,
  PreparationMaterial,
} from './types'

const matches = (selected: string, value: string) => selected === '全部' || selected === value

export function filterJobs(jobs: JobRecord[], filters: JobFilters): JobRecord[] {
  const query = filters.query.trim().toLocaleLowerCase('zh-CN')
  return jobs.filter((job) => {
    const text = `${job.company} ${job.role} ${job.location}`.toLocaleLowerCase('zh-CN')
    return (
      (!query || text.includes(query)) &&
      matches(filters.companyType, job.companyType) &&
      matches(filters.company, job.company) &&
      matches(filters.roleType, job.roleType) &&
      matches(filters.deadlineStatus, job.deadlineStatus)
    )
  })
}

export function filterMaterials(
  materials: PreparationMaterial[],
  filters: MaterialFilters,
): PreparationMaterial[] {
  const query = filters.query.trim().toLocaleLowerCase('zh-CN')
  return materials.filter((material) => {
    const text = `${material.title} ${material.role} ${material.excerpt}`.toLocaleLowerCase('zh-CN')
    return (
      (!query || text.includes(query)) &&
      material.primaryCategory === filters.primary &&
      material.secondaryCategory === filters.secondary &&
      matches(filters.company, material.company)
    )
  })
}
