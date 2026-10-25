import { useCallback, useEffect, useState } from 'react'

import { api, type DashboardResponse } from '../data/api'

export function useDashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const reload = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await api.getDashboard())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void reload() }, [reload])
  return { data, error, loading, reload, setData }
}
