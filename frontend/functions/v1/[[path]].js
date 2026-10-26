function backendOrigin(value) {
  if (!value) return null

  try {
    const url = new URL(value)
    if (!['http:', 'https:'].includes(url.protocol)) return null
    if (url.username || url.password) return null
    return url.origin
  } catch {
    return null
  }
}

export async function onRequest(context) {
  const origin = backendOrigin(context.env.API_ORIGIN)
  if (!origin) {
    return new Response('API_ORIGIN is not configured', { status: 500 })
  }

  const path = Array.isArray(context.params.path)
    ? context.params.path.join('/')
    : context.params.path
  const incomingUrl = new URL(context.request.url)
  const upstreamUrl = new URL(`/v1/${path || ''}`, origin)
  upstreamUrl.search = incomingUrl.search

  const headers = new Headers(context.request.headers)
  headers.delete('host')
  headers.set('ngrok-skip-browser-warning', 'careerpilot')

  const hasBody = !['GET', 'HEAD'].includes(context.request.method)
  const body = hasBody ? await context.request.arrayBuffer() : undefined

  const upstreamRequest = new Request(upstreamUrl, {
    method: context.request.method,
    headers,
    body,
    redirect: 'manual',
  })

  return fetch(upstreamRequest)
}
