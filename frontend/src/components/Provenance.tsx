import { isStaticData } from '../api/client'
export type Provenance = 'demo_fixture' | 'browser_inference' | 'server_inference'
const labels: Record<Provenance, string> = {
  demo_fixture: 'Учебный пример', browser_inference: 'Обработано в браузере', server_inference: 'Обработано на сервере',
}
export function ProvenanceBadge({ source }: { source?: Provenance }) {
  const actual = source ?? (isStaticData ? 'demo_fixture' : undefined)
  return <span className={`provenance ${actual === 'demo_fixture' ? 'provenance--demo' : ''}`}>{actual ? labels[actual] : 'Источник не указан'}</span>
}
