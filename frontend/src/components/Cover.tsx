import { useEffect, useState } from 'react'
import { initials } from '../format'

interface CoverProps {
  src: string | null
  name: string
  className?: string
  eager?: boolean
}

export function Cover({ src, name, className = '', eager = false }: CoverProps) {
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [src])

  if (!src || failed) {
    return (
      <div className={`cover-fallback ${className}`} aria-hidden="true">
        <span>{initials(name)}</span>
      </div>
    )
  }

  return (
    <img
      className={className}
      src={src}
      alt={`Jaquette de ${name}`}
      loading={eager ? 'eager' : 'lazy'}
      onError={() => setFailed(true)}
    />
  )
}
