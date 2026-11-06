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
  memory_provider_status: string
  dreaming_status: string
  memory_ids: string[]
  citation_ids: string[]
  citation_warnings: string[]
  direction_signal?: DirectionSignal
  compass_update_batch?: CompassUpdateBatch
}

export interface CompassUpdateItem {
  id: string
  kind: 'direction' | 'company' | 'business' | 'role' | 'location' | 'constraint' | 'profile' | 'evidence'
  value: string
  explicitness: 'explicit' | 'implicit'
  status: 'applied' | 'pending' | 'undone'
  source_quote: string
}

export interface CompassUpdateBatch {
  id: string
  run_id: string
  conversation_id: string
  direction_id?: string | null
  branch_id?: string | null
  source_quote: string
  status: 'committed' | 'undone'
  created_at: string
  items: CompassUpdateItem[]
}

export interface DirectionSignal {
  id: string
  label: string
  explicitness: 'implicit' | 'explicit'
  source_quote: string
  reason: string
  confidence: number
  suggested_action: 'ask_to_add' | 'add_to_compass'
  status: 'pending' | 'accepted'
}

export interface DashboardDirection {
  id: string
  label: string
  status: 'confirmed' | 'paused' | 'archived'
  source_signal_id: string
  source_kind: 'conversation' | 'idea' | 'manual'
  source_quote: string
  reason: string
  confidence: number
}

export interface DirectionBranch {
  id: string
  direction_id: string
  company: string
  business: string
  role: string
  location: string
  status: 'active' | 'paused' | 'archived'
}

export interface JourneyBranch {
  id: string
  journey_id: string
  compass_branch_id?: string | null
  kind: 'common' | 'target'
  title: string
  status: 'draft' | 'active' | 'paused' | 'completed' | 'archived'
  rationale: string
  company?: string
  business?: string
  role?: string
  location?: string
}

export interface DirectionSummary {
  direction_id: string
  reason: string
  unknown_question: string
  recent_change: string
  next_validation: string
  updated_at: string
}

export interface DashboardJourney {
  id: string
  direction_id: string
  title: string
  status: 'active' | 'paused' | 'completed'
  why: string
  created_at?: string
  updated_at?: string
}

export interface KnowledgeCollectionJob {
  id: string
  direction_id: string
  journey_id?: string | null
  purpose: 'job_opportunity' | 'interview_archive' | 'learning_resource'
  query: string
  status: 'queued' | 'collecting' | 'completed' | 'partial' | 'failed'
  attempts: number
}

export interface DirectionJourneyStart {
  journey: DashboardJourney
  tasks: JourneyItem[]
  branches?: JourneyBranch[]
  collection_jobs: KnowledgeCollectionJob[]
}

export interface FuturePath {
  kind: 'continue' | 'adjacent' | 'unexpected'
  label: string
  title: string
  summary: string
  signals: string[]
  tension: string
  question: string
}

export interface FutureLetter {
  id: string
  journey_id: string
  message: string
  paths: FuturePath[]
  created_at: string
  takeaway?: { path_kind: FuturePath['kind']; question: string; created_at: string } | null
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
  directions?: DashboardDirection[]
  direction_signals?: DirectionSignal[]
  journeys?: DashboardJourney[]
  collection_jobs?: KnowledgeCollectionJob[]
  compass_update_batches?: CompassUpdateBatch[]
  direction_branches?: DirectionBranch[]
  journey_branches?: JourneyBranch[]
  direction_summaries?: DirectionSummary[]
  career_profile?: Array<{ id: string; category: string; value: string; status: string }>
  direction_evidence?: Array<{ id: string; direction_id: string; branch_id?: string | null; kind: string; content: string; source_quote?: string | null; source_kind: string }>
}

export type CanonicalMemoryType = 'fact' | 'preference' | 'goal' | 'constraint' | 'idea' | 'experience' | 'decision' | 'hypothesis'
export type CanonicalMemoryStatus = 'candidate' | 'active' | 'paused' | 'superseded' | 'deleted'

export interface CanonicalMemory {
  id: string
  type: CanonicalMemoryType
  content: string
  status: CanonicalMemoryStatus
  sensitivity: 'normal' | 'private' | 'sensitive'
  origin: 'user_explicit' | 'agent_extracted' | 'dreaming' | 'imported'
  source_type: 'conversation' | 'manual' | 'integration' | 'dreaming' | 'migration'
  source_reference: string | null
  confidence: 'low' | 'medium' | 'high'
  importance: number
  version: number
  created_at: string
  updated_at: string
  last_used_at: string | null
  expires_at: string | null
  deleted_at: string | null
  metadata: Record<string, unknown>
}

export interface DreamingHypothesis {
  statement: string
  confidence_band: 'low' | 'medium' | 'high'
  supporting_evidence_ids: string[]
  open_questions: string[]
}

export interface DreamingResult {
  id: string
  local_date: string
  version: number
  updated_at: string
  summary: string
  wins: string[]
  ideas: string[]
  blockers: string[]
  open_loops: string[]
  tomorrow_step: string | null
  hypotheses: DreamingHypothesis[]
}

export interface DreamingJob {
  job_id: string
  status: 'queued' | 'processing' | 'completed' | 'failed'
  local_date: string
  error?: string | null
  result?: DreamingResult | null
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

export interface InterviewArchiveResource {
  id: string
  title: string
  publisher: string
  year?: string | null
  round?: string | null
  trust: 'official' | 'first_party' | 'experience' | 'unverified'
  url: string
  excerpt: string
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

export interface CollectedJobSource {
  id: string
  title: string
  publisher: string
  url: string
  description: string
  updated_at: string
  source_type: string
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
  acceptDirectionSignal(id: string) {
    return request<DashboardDirection>(`/v1/me/direction-signals/${encodeURIComponent(id)}/accept`, {
      method: 'POST',
    })
  },
  undoCompassUpdate(id: string) {
    return request<{ status: 'undone' }>(`/v1/me/compass-updates/${encodeURIComponent(id)}/undo`, {
      method: 'POST',
    })
  },
  correctCompassUpdateItem(batchId: string, itemId: string, value: string) {
    return request<CompassUpdateBatch>(
      `/v1/me/compass-updates/${encodeURIComponent(batchId)}/items/${encodeURIComponent(itemId)}`,
      { method: 'PATCH', body: JSON.stringify({ value }) },
    )
  },
  startDirectionJourney(id: string) {
    return request<DirectionJourneyStart>(`/v1/me/directions/${encodeURIComponent(id)}/journey`, {
      method: 'POST',
    })
  },
  activateJourneyBranch(journeyId: string, branchId: string) {
    return request<DirectionJourneyStart>(
      `/v1/me/journeys/${encodeURIComponent(journeyId)}/branches/${encodeURIComponent(branchId)}/activate`,
      { method: 'POST' },
    )
  },
  getMemories() {
    return request<{ items: CanonicalMemory[] }>('/v1/me/memories')
  },
  updateMemory(id: string, expectedVersion: number, content: string) {
    return request<CanonicalMemory>(`/v1/me/memories/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ expected_version: expectedVersion, content }),
    })
  },
  transitionMemory(id: string, operation: 'confirm' | 'pause' | 'resume', expectedVersion: number) {
    return request<CanonicalMemory>(`/v1/me/memories/${encodeURIComponent(id)}/${operation}`, {
      method: 'POST',
      body: JSON.stringify({ expected_version: expectedVersion }),
    })
  },
  deleteMemory(id: string, expectedVersion: number) {
    return request<CanonicalMemory>(`/v1/me/memories/${encodeURIComponent(id)}?expected_version=${expectedVersion}`, {
      method: 'DELETE',
    })
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
  startDreaming() {
    return request<DreamingJob>('/v1/me/dreaming', { method: 'POST' })
  },
  getDreamingToday() {
    return request<DreamingResult>('/v1/me/dreaming/today')
  },
  getDreamingJob(jobId: string) {
    return request<DreamingJob>(`/v1/me/dreaming/jobs/${encodeURIComponent(jobId)}`)
  },
  confirmDreamingHypothesis(resultId: string, index: number) {
    return request<{ memory_id: string; status: string }>(`/v1/me/dreaming/results/${encodeURIComponent(resultId)}/hypotheses/${index}/confirm`, { method: 'POST' })
  },
  decideHypothesis(id: string, decision: 'confirm' | 'uncertain') {
    return request<{ status: string }>(`/v1/me/hypotheses/${encodeURIComponent(id)}/decision`, {
      method: 'POST',
      body: JSON.stringify({ decision }),
    })
  },
  createJourneyEvent(input: {
    title: string
    start_at: string
    end_at?: string
    reminder_minutes?: number
    meeting_url?: string
    notes?: string
  }) {
    return request<JourneyItem>('/v1/me/journey', {
      method: 'POST',
      body: JSON.stringify(input),
    })
  },
  updateJourneyTask(id: string, state: JourneyItem['state'], reflection?: string) {
    return request<{ status: string }>(`/v1/me/journey/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      body: JSON.stringify({ state, reflection: reflection || null }),
    })
  },
  generateFutureLetter(journeyId: string, message = '两年后的我会怎样？') {
    return request<FutureLetter>(`/v1/me/journeys/${encodeURIComponent(journeyId)}/future-letter`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    })
  },
  async getFutureLetter(journeyId: string) {
    try {
      return await request<FutureLetter>(`/v1/me/journeys/${encodeURIComponent(journeyId)}/future-letter`)
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 404) return undefined
      throw reason
    }
  },
  confirmFutureTakeaway(journeyId: string, letterId: string, path: FuturePath) {
    return request<{ path_kind: FuturePath['kind']; question: string; created_at: string }>(
      `/v1/me/journeys/${encodeURIComponent(journeyId)}/future-letter/takeaway`,
      { method: 'POST', body: JSON.stringify({ letter_id: letterId, path_kind: path.kind, question: path.question }) },
    )
  },
  getJobs(filters: { companyType?: string; company?: string } = {}) {
    const query = toQuery({ company_type: filters.companyType, company: filters.company })
    return request<{ items: ApiJob[]; collected_sources?: CollectedJobSource[] }>(`/v1/knowledge/jobs${query}`)
  },
  getPreparation() {
    return request<{ items: PreparationResource[] }>('/v1/knowledge/preparation')
  },
  refreshJobs() {
    return request<{ processed: number; saved: number; collection_jobs: KnowledgeCollectionJob[] }>(
      '/v1/knowledge/jobs/refresh', { method: 'POST' },
    )
  },
  getLearningResources() {
    return request<{ items: PreparationResource[] }>('/v1/knowledge/learning')
  },
  refreshLearningResources() {
    return request<{ processed: number; saved: number; collection_jobs: KnowledgeCollectionJob[] }>(
      '/v1/knowledge/learning/refresh', { method: 'POST' },
    )
  },
  getInterviewArchive() {
    return request<{ items: InterviewArchiveResource[] }>('/v1/knowledge/interview-archive')
  },
  refreshInterviewArchive() {
    return request<{ processed: number; saved: number; collection_jobs: KnowledgeCollectionJob[] }>(
      '/v1/knowledge/interview-archive/refresh', { method: 'POST' },
    )
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
