import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../services/api'

export function useResource<T>(loader: () => Promise<T>, key = '') {
  const fn = useRef(loader)
  fn.current = loader
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [revision, setRevision] = useState(0)
  const reload = useCallback(() => setRevision(n => n + 1), [])
  useEffect(() => {
    let active = true
    setLoading(true); setError('')
    fn.current().then(value => { if (active) setData(value) }).catch(e => { if (active) setError(errorMessage(e)) }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [key, revision])
  return { data, error, loading, reload }
}
