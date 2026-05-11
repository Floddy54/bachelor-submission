/**
 * useCsvExport — shared CSV export helper.
 *
 * Pattern: one helper, every tab uses it, every export looks the same to
 * the user (filename, escape rules, header behaviour).
 *
 *   downloadCsv('incidents.csv', items, ['id', 'severity', 'title'])
 *
 * If columns is omitted, all keys from the first row are exported.
 */
export function downloadCsv(filename, rows, columns) {
  if (!Array.isArray(rows) || rows.length === 0) return false
  const keys = columns ?? Object.keys(rows[0])
  const escape = v => {
    if (v == null) return ''
    const s = typeof v === 'object' ? JSON.stringify(v) : String(v)
    return `"${s.replace(/"/g, '""')}"`
  }
  const csv = [
    keys.join(','),
    ...rows.map(r => keys.map(k => escape(r[k])).join(',')),
  ].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 100)
  return true
}

export default downloadCsv
