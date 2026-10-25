import type { JobRecord, JourneyItem, PersonalDocument } from './types'

export interface ChatRequest {
  message: string
  conversation_id?: string
}

export interface ChatResponse {
  conversation_id: string
  run_id: string
  result_status: 'completed' | 'partial' | 'blocked' | 'failed' | 'cancelled'
  reply: string
  support_mode: string
  primary_intent: string
  retrieval_sources: string[]
  memory_read_status: string
  memory_write_status: string
  dreaming_status: string
  memory_ids: string[]
  citation_ids: string[]
  citation_warnings: string[]
}

export interface DashboardHypothesis {
  id: string
  content?: string
  statement?: string
  confidence?: string
  status: string
  section?: string
  evidence?: string[]
}

export interface DashboardIdea {
  id: string
  title: string
  raw_text?: string
  content?: string
  stage: string
  version?: number
  created_at?: string
}

export interface DreamingReview {
  id?: string
  local_date?: string
  date?: string
  summary?: string
  title?: string
  observations?: unknown[]
}

export interface DashboardResponse {
  hypotheses: DashboardHypothesis[]
  journey: JourneyItem[]
  ideas: DashboardIdea[]
  dreaming: DreamingReview[]
  memories: unknown[]
}

export interface ApiJob {
  id: string
  company_type?: string
  company?: string
  company_name?: string
  role?: string
  job_title?: string
  role_type?: string
  job_type?: string
  location?: string
  posted_at?: string
  deadline?: string
  deadline_status?: string
  source?: string
  source_url?: string
  updated_at?: string
  description?: string
  requirements?: string[]
}

export interface ApiDocument {
  id: string
  title: string
  category: string
  file_format: string
  size_text: string
  uploaded_at: string
  status: string
  retrieval_enabled: boolean
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  let response: Response
  try {
    response = await fetch(path, { ...init, headers, credentials: 'include' })
  } catch {
    throw new ApiError(0, '暂时无法连接 CareerPilot 服务，请稍后重试。')
  }
  if (!response.ok) {
    let message = `请求失败（${response.status}）`
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) message = body.detail
    } catch {
      // Keep the status-based message when a proxy returns a non-JSON body.
    }
    throw new ApiError(response.status, message)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

function toQuery(params: Record<string, string | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value && value !== '全部') search.set(key, value)
  })
  const query = search.toString()
  return query ? `?${query}` : ''
}

export const api = {
  chat(body: ChatRequest) {
    return request<ChatResponse>('/v1/chat', { method: 'POST', body: JSON.stringify(body) })
  },
  getDashboard() {
    return request<DashboardResponse>('/v1/me/dashboard')
  },
  createIdea(text: string) {
    const title = text.length > 200 ? `${text.slice(0, 197)}…` : text
    return request<DashboardIdea>('/v1/me/ideas', {
      method: 'POST',
      body: JSON.stringify({
        raw_text: text,
        title,
        authorization: 'granted',
        sensitivity: 'normal',
      }),
    })
  },
  decideHypothesis(id: string, decision: 'confirm' | 'uncertain') {
    return request<{ status: string }>(`/v1/me/hypotheses/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    })
  },
  createVerificationTask(id: string) {
    return request<JourneyItem>(`/v1/me/hypotheses/${encodeURIComponent(id)}/verification-task`, { method: 'POST' })
  },
  updateJourneyTask(id: string, state: JourneyItem['state'], reflection?: string) {
    return request<{ status: string }>(`/v1/me/journey/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ state, reflection: reflection || null }),
    })
  },
  getJobs(filters: { companyType?: string; company?: string } = {}) {
    const query = toQuery({ company_type: filters.companyType, company: filters.company })
    return request<{ items: ApiJob[] }>(`/v1/knowledge/jobs${query}`)
  },
  getPreparation() {
    return request<{ items: Record<string, unknown>[] }>('/v1/knowledge/preparation')
  },
  getDocuments() {
    return request<{ items: ApiDocument[] }>('/v1/me/documents')
  },
  deleteDocument(id: string) {
    return request<{ status: string }>(`/v1/me/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },
  previewAction(providerId: string, capability: string, payload: Record<string, unknown>) {
    return request<Record<string, unknown>>('/v1/me/actions/preview', {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId, capability, payload }),
    })
  },
}

export function mapApiJob(job: ApiJob): JobRecord {
  return {
    id: job.id,
    companyType: (job.company_type || '未知') as JobRecord['companyType'],
    company: job.company || job.company_name || '未命名企业',
    role: job.role || job.job_title || '未命名岗位',
    roleType: (job.role_type || job.job_type || '其他') as JobRecord['roleType'],
    location: job.location || '未公开',
    postedAt: job.posted_at || '未公开',
    deadline: job.deadline || '未公开',
    deadlineStatus: (job.deadline_status || '时间未知') as JobRecord['deadlineStatus'],
    source: job.source || '来源网页',
    sourceUrl: job.source_url || '',
    updatedAt: job.updated_at || '',
    description: job.description || '',
    requirements: job.requirements || [],
  }
}

export function mapApiDocument(doc: ApiDocument): PersonalDocument {
  return {
    id: doc.id,
    title: doc.title,
    category: doc.category as PersonalDocument['category'],
    format: doc.file_format.toUpperCase() as PersonalDocument['format'],
    size: doc.size_text,
    uploadedAt: doc.uploaded_at,
    status: doc.status as PersonalDocument['status'],
    retrievalEnabled: doc.retrieval_enabled,
  }
}
