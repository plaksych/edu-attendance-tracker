import type { ReactNode } from 'react'
import { useEffect, useId, useRef } from 'react'
import { IconClose } from './icons'

interface Props {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

export function Modal({ title, onClose, children, wide = false }: Props) {
  const titleId = useId()
  const ref = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  close.current = onClose
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    ref.current?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current()
      if (event.key === 'Tab') {
        const elements = [...(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') ?? [])].filter(el => el.getClientRects().length > 0)
        const first = elements[0], last = elements[elements.length - 1]
        if (!first) { event.preventDefault(); return }
        if (event.shiftKey && (document.activeElement === first || document.activeElement === ref.current)) { event.preventDefault(); last.focus() }
        else if (!event.shiftKey && (document.activeElement === last || document.activeElement === ref.current)) { event.preventDefault(); first.focus() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; previous?.focus() }
  }, [])

  return (
    <div
      className="modal-overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div ref={ref} tabIndex={-1} className={`modal${wide ? ' modal--wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal__heading"><h2 id={titleId} className="modal__title">{title}</h2><button type="button" className="icon-button" aria-label="Закрыть диалог" onClick={onClose}><IconClose /></button></div>
        {children}
      </div>
    </div>
  )
}
