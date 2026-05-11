import './Skeleton.css'

/**
 * Skeleton — placeholder shape shown while a widget is loading.
 *
 * Pattern: instead of a generic "Loading…" spinner, render a skeleton that
 * matches the shape of the eventual content. Reduces perceived latency and
 * stops the page from jumping when data arrives.
 *
 *   <SkeletonCard rows={5} />
 *   <SkeletonText width="60%" />
 *   <SkeletonBar height={28} />
 */
export function SkeletonBar({ height = 16, width = '100%', radius = 4 }) {
  return (
    <div
      className="skeleton skeleton-bar"
      style={{ height, width, borderRadius: radius }}
    />
  )
}

export function SkeletonText({ width = '70%' }) {
  return <SkeletonBar height={12} width={width} radius={3} />
}

export function SkeletonCard({ rows = 4, title = true }) {
  return (
    <div className="skeleton-card">
      {title && <SkeletonBar height={14} width="40%" />}
      <div style={{ height: 14 }} />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ marginBottom: 8 }}>
          <SkeletonBar height={10} width={`${60 + Math.random() * 35}%`} radius={3} />
        </div>
      ))}
    </div>
  )
}

export function SkeletonKpi() {
  return (
    <div className="skeleton-kpi">
      <SkeletonBar height={10} width="50%" />
      <div style={{ height: 8 }} />
      <SkeletonBar height={24} width="40%" />
      <div style={{ height: 6 }} />
      <SkeletonBar height={9}  width="60%" />
    </div>
  )
}

export default SkeletonCard
