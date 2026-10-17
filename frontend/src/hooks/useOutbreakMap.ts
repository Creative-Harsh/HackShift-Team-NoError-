import { useCallback, useEffect, useState } from 'react'
import { endpoints, errorMessage } from '../services/api'
import type { OutbreakFilters, OutbreakMapData } from '../types'

/** One cancellable request at a time, with a fresh snapshot every 20 seconds. */
export function useOutbreakMap(filters: OutbreakFilters) {
  const key = JSON.stringify(filters)
  const [snapshot, setSnapshot] = useState<{ key: string; value: OutbreakMapData } | null>(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision(value => value + 1), [])
  useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    const load = async () => {
      setRefreshing(true)
      try {
        const value = await endpoints.outbreakMap(JSON.parse(key) as OutbreakFilters, controller.signal)
        if (!controller.signal.aborted) { setSnapshot({ key, value }); setError('') }
      } catch (failure) {
        if (!controller.signal.aborted) setError(errorMessage(failure))
      } finally {
        if (!controller.signal.aborted) { setRefreshing(false); timer = setTimeout(load, 20000) }
      }
    }
    setError('')
    void load()
    return () => { controller.abort(); if (timer) clearTimeout(timer) }
  }, [key, revision])
  const data = snapshot?.key === key ? snapshot.value : null
  return { data, error, refreshing, loading: !data && !error, refresh }
}
