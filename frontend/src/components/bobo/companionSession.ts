const COMPANION_CONVERSATION_KEY = 'careerpilot.companionConversationId'

export function getCompanionConversationId() {
  if (typeof window === 'undefined') return undefined
  return window.localStorage.getItem(COMPANION_CONVERSATION_KEY) || undefined
}

export function saveCompanionConversationId(id: string) {
  if (typeof window !== 'undefined') window.localStorage.setItem(COMPANION_CONVERSATION_KEY, id)
}

export function clearCompanionConversationId() {
  if (typeof window !== 'undefined') window.localStorage.removeItem(COMPANION_CONVERSATION_KEY)
}
