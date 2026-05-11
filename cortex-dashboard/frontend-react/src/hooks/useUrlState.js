import { useEffect, useState, useCallback } from 'react'

/**
 * useUrlState — sync a piece of state with a URL search parameter.
 *
 * Pattern: store only the minimal "filter criteria" in URL, derive everything
 * else on render. Makes the dashboard URL shareable, the filter set survives
 * a page refresh, and the browser's back/forward buttons act like an undo
 * stack for the user.
 *
 * Native URLSearchParams — no React Router or nuqs dependency.
 *
 *   const [tab, setTab] = useUrlState('tab', 'overview')
 *   const [status, setStatus] = useUrlState('status', 'ALL')
 *
 * Set value to the defaultValue to remove the key from the URL (keeps it tidy).
 */
export default function useUrlState(key, defaultValue) {
  const read = () => {
    const params = new URLSearchParams(window.location.search)
    return params.get(key) ?? defaultValue
  }

  const [value, setValue] = useState(read)

  // Listen for browser back/forward
  useEffect(() => {
    const onPop = () => setValue(read())
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  const update = useCallback((next) => {
    const params = new URLSearchParams(window.location.search)
    if (next === defaultValue || next === '' || next == null) {
      params.delete(key)
    } else {
      params.set(key, next)
    }
    const search = params.toString()
    const url = search ? `${window.location.pathname}?${search}` : window.location.pathname
    window.history.replaceState(null, '', url)
    setValue(next == null ? defaultValue : next)
  }, [key, defaultValue])

  return [value, update]
}


/**
 * useDebounce — return `value` but delayed by `delay` ms.
 *
 * Pattern: use this on search inputs so we only filter / re-render / API-call
 * after the user has stopped typing for 300 ms. Avoids re-rendering a 100-row
 * table on every keystroke.
 *
 *   const [q, setQ] = useState('')
 *   const dq = useDebounce(q, 300)
 *   const filtered = useMemo(() => rows.filter(...dq...), [rows, dq])
 */
export function useDebounce(value, delay = 300) {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
