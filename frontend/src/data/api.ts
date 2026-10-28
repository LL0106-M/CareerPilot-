import type { JobRecord, JourneyItem, PersonalDocument } from './types'
import { announceAuthExpired } from '../auth/auth-events'

export interface Account {
  id: string
  username: string
  email: string
}

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

export interface ConversationSummary {
  id: string
  title: string
  updated_at: string
  message_count: number
}

export interface ConversationDetail {
  id: string
  title: string
  updated_at: string
  messages: Array<{ role: 'user' | 'agent'; content: string }>
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
  role_family?: string
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

export interface PreparationResource {
  id: string
  title: string
  publisher: string
  category: string
  format: string
  url: string
  description: string
  updated_at: string
  source_type: string
}

export interface ActionPreview {
  action_id: string
  provider_id: string
  capability: string
  payload: Record<string, unknown>
  preview_hash: string
  requires_confirmation: boolean
}

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function responseError(response: Response, path: string): Promise<ApiError> {
  let message = `请求失败（${response.status}）`
  try {
    const body = await response.json() as { detail?: unknown }
    if (typeof body.detail === 'string') message = body.detail
    else if (Array.isArray(body.detail)) message = '请检查填写内容后重试。'
  } catch {
    // Keep the status-based message when a proxy returns a non-JSON body.
  }
  if (response.status === 401 && path !== '/v1/auth/me' && path !== '/v1/auth/login') announceAuthExpired()
  return new ApiError(response.status, message)
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
    throw await responseError(response, path)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

async function streamChat(
  body: ChatRequest,
  onDelta: (text: string) => void,
): Promise<ChatResponse> {
  let response: Response
  try {
    response = await fetch('/v1/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      credentials: 'include',
      body: JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, '暂时无法连接 CareerPilot 服务，请稍后重试。')
  }
  if (!response.ok) {
    throw await responseError(response, '/v1/chat/stream')
  }
  if (!response.body) throw new ApiError(0, '服务没有返回可读取的回复。')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed: ChatResponse | undefined

  const consumeFrame = (frame: string) => {
    let eventName = 'message'
    const dataLines: string[] = []
    frame.split(/\r?\n/).forEach((line) => {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    })
    if (dataLines.length === 0) return
    const payload = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
    if (eventName === 'delta' && typeof payload.text === 'string') onDelta(payload.text)
    if (eventName === 'completed') completed = payload as unknown as ChatResponse
    if (eventName === 'error') {
      throw new ApiError(0, typeof payload.message === 'string' ? payload.message : '回复中断，请重试。')
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    let boundary = buffer.search(/\r?\n\r?\n/)
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary)
      const separator = buffer.slice(boundary).match(/^\r?\n\r?\n/)?.[0] || '\n\n'
      buffer = buffer.slice(boundary + separator.length)
      if (frame.trim()) consumeFrame(frame)
      boundary = buffer.search(/\r?\n\r?\n/)
    }
    if (done) break
  }
  if (buffer.trim()) consumeFrame(buffer)
  if (!completed) throw new ApiError(0, '回复在完成前中断，请重试。')
  return completed
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
  getCurrentAccount() {
    return request<Account>('/v1/auth/me')
  },
  requestVerificationCode(email: string) {
    return request<{ status: string; expires_at: string; retry_after_seconds: number }>('/v1/auth/verification-codes', {
      method: 'POST', body: JSON.stringify({ email }),
    })
  },
  register(input: { username: string; email: string; verificationCode: string; password: string }) {
    return request<Account>('/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ username: input.username, email: input.email, verification_code: input.verificationCode, password: input.password }),
    })
  },
  login(identifier: string, password: string, rememberMe: boolean) {
    return request<Account>('/v1/auth/login', {
      method: 'POST', body: JSON.stringify({ identifier, password, remember_me: rememberMe }),
    })
  },
  logout() {
    return request<{ status: string }>('/v1/auth/logout', { method: 'POST' })
  },
  chat(body: ChatRequest) {
    return request<ChatResponse>('/v1/chat', { method: 'POST', body: JSON.stringify(body) })
  },
  chatStream(body: ChatRequest, onDelta: (text: string) => void) {
    return streamChat(body, onDelta)
  },
  getConversations() {
    return request<{ items: ConversationSummary[] }>('/v1/me/conversations')
  },
  getConversation(id: string) {
    return request<ConversationDetail>(`/v1/me/conversations/${encodeURIComponent(id)}`)
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
  createIdeaVerificationTask(id: string) {
    return request<JourneyItem>(`/v1/me/ideas/${encodeURIComponent(id)}/verification-task`, { method: 'POST' })
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
    return request<{ items: PreparationResource[] }>('/v1/knowledge/preparation')
  },
  getDocuments() {
    return request<{ items: ApiDocument[] }>('/v1/me/documents')
  },
  deleteDocument(id: string) {
    return request<{ status: string }>(`/v1/me/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },
  uploadDocument(file: File, category: PersonalDocument['category']) {
    const format = file.name.split('.').pop()?.toUpperCase() || ''
    const params = new URLSearchParams({ title: file.name, category, file_format: format })
    return request<ApiDocument>(`/v1/me/documents?${params.toString()}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: file,
    })
  },
  previewAction(providerId: string, capability: string, payload: Record<string, unknown>) {
    return request<ActionPreview>('/v1/me/actions/preview', {
      method: 'POST',
      body: JSON.stringify({ provider_id: providerId, capability, payload }),
    })
  },
  confirmAction(actionId: string, previewHash: string) {
    return request<{ action_id: string; confirmation_token: string; preview_hash: string }>(`/v1/me/actions/${encodeURIComponent(actionId)}/confirm`, {
      method: 'POST',
      body: JSON.stringify({ preview_hash: previewHash }),
    })
  },
  applyAction(actionId: string, confirmationToken: string, previewHash: string, idempotencyKey: string) {
    return request<{ status: string; external_reference?: string }>(`/v1/me/actions/${encodeURIComponent(actionId)}/apply`, {
      method: 'POST',
      body: JSON.stringify({ confirmation_token: confirmationToken, preview_hash: previewHash, idempotency_key: idempotencyKey }),
    })
  },
}

export function mapApiJob(job: ApiJob): JobRecord {
  return {
    id: job.id,
    companyType: (job.company_type || '未知') as JobRecord['companyType'],
    company: job.company || job.company_name || '未命名企业',
    role: job.role || job.job_title || '未命名岗位',
    roleType: (job.role_type || job.job_type || job.role_family || '其他') as JobRecord['roleType'],
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
