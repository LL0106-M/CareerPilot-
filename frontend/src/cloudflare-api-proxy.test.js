import { afterEach, describe, expect, it, vi } from 'vitest'

import { onRequest } from '../functions/v1/[[path]].js'

describe('Cloudflare API proxy', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('forwards the original method, body, query, and cookies to the configured backend', async () => {
    let forwardedRequest
    vi.stubGlobal('fetch', async (request) => {
      forwardedRequest = request
      return new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'set-cookie': 'careerpilot_owner=signed; Path=/; HttpOnly; Secure; SameSite=Lax',
        },
      })
    })

    const request = new Request('https://careerpilot.pages.dev/v1/me/dashboard?day=today', {
      method: 'POST',
      headers: {
        cookie: 'careerpilot_owner=signed',
        'content-type': 'application/json',
      },
      body: JSON.stringify({ refresh: true }),
    })

    const response = await onRequest({
      request,
      env: { API_ORIGIN: 'https://careerpilot-backend.ngrok-free.app/' },
      params: { path: ['me', 'dashboard'] },
    })

    expect(forwardedRequest.url).toBe(
      'https://careerpilot-backend.ngrok-free.app/v1/me/dashboard?day=today',
    )
    expect(forwardedRequest.method).toBe('POST')
    expect(forwardedRequest.headers.get('cookie')).toBe('careerpilot_owner=signed')
    expect(forwardedRequest.headers.get('ngrok-skip-browser-warning')).toBe('careerpilot')
    expect(await forwardedRequest.json()).toEqual({ refresh: true })
    expect(response.status).toBe(200)
    expect(response.headers.get('set-cookie')).toContain('careerpilot_owner=signed')
  })

  it('fails closed when API_ORIGIN is missing', async () => {
    const response = await onRequest({
      request: new Request('https://careerpilot.pages.dev/v1/chat'),
      env: {},
      params: { path: ['chat'] },
    })

    expect(response.status).toBe(500)
    expect(await response.text()).toBe('API_ORIGIN is not configured')
  })
})
