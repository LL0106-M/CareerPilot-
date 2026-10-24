export type DeadlineStatus = '招聘中' | '即将截止' | '已截止' | '时间未知'

export interface JobRecord {
  id: string
  companyType: '央企' | '地方国企' | '民营企业' | '外资企业' | '事业单位'
  company: string
  role: string
  roleType: '产品' | 'AI 产品' | '运营' | '技术' | '数据' | '管培生'
  location: string
  postedAt: string
  deadline: string
  deadlineStatus: DeadlineStatus
  source: string
  sourceUrl: string
  updatedAt: string
  description: string
  requirements: string[]
}

export interface JobFilters {
  query: string
  companyType: string
  company: string
  roleType: string
  deadlineStatus: string
}

export type PreparationPrimary = '面试' | '笔试'
export type PreparationSecondary = '面经' | '面试准备' | '考题' | '准备资料'

export interface PreparationMaterial {
  id: string
  title: string
  primaryCategory: PreparationPrimary
  secondaryCategory: PreparationSecondary
  company: string
  role: string
  source: '联网资料' | '后台资料' | '用户上传'
  format: 'PDF' | '网页' | 'DOCX'
  updatedAt: string
  indexed: boolean
  excerpt: string
}

export interface MaterialFilters {
  query: string
  primary: PreparationPrimary
  secondary: PreparationSecondary
  company: string
}

export interface PersonalDocument {
  id: string
  title: string
  category: '简历' | '项目与作品集' | '其他资料'
  format: 'PDF' | 'DOCX' | 'TXT'
  size: string
  uploadedAt: string
  status: '可检索' | '解析中' | '解析失败'
  retrievalEnabled: boolean
}

export interface DreamingInsight {
  id: string
  date: string
  title: string
  summary: string
  evidenceCount: number
  status: '待查看' | '已确认' | '继续观察'
  details?: Record<string, string>
}

export interface CareerHypothesis {
  id: string
  statement: string
  confidence: '低' | '中' | '高'
  status: '待确认' | '继续观察' | '已确认'
  evidence: string[]
  section?: 'interests' | 'strengths' | 'environment' | 'risks'
}

export interface JourneyItem {
  id: string
  title: string
  due: string
  state: '准备开始' | '进行中' | '等待结果' | '已完成'
  related: string
  hypothesisId?: string
  why?: string
  reflection?: string | null
}

export interface MemoryItem {
  id: string
  type: '长期目标' | '事实' | '偏好' | '情绪'
  content: string
  source: string
  createdAt: string
  compassSection?: 'interests' | 'strengths' | 'environment' | 'risks'
}

export interface DashboardState {
  hypotheses: CareerHypothesis[]
  journey: JourneyItem[]
  memories: MemoryItem[]
  dreaming: DreamingInsight[]
}
