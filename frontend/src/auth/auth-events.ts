export const AUTH_EXPIRED_EVENT = 'careerpilot:auth-expired'

export function announceAuthExpired() {
  window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT))
}
