import { useEffect, useState } from 'react'
import { isStaticData } from '../api/client'
import { managementApi, type SystemStatus } from '../api/management'
import { StatCard } from '../components/StatCard'
import { IconRefresh } from '../components/icons'

export function SystemPage() {
  const [data, setData] = useState<SystemStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  useEffect(() => {
    if (isStaticData) return
    let active = true
    setData(null); setError(null)
    managementApi.system().then(value => { if (active) setData(value) }).catch(e => { if (active) setError(e.message) })
    return () => { active = false }
  }, [revision])
  return <>
    <header className="page-header"><div><h1>Состояние системы</h1><p>{isStaticData ? 'Статическая витрина не подключена к серверу' : 'Последний полученный ответ сервера'}</p></div>{!isStaticData && <button className="btn btn--ghost" onClick={() => setRevision(n => n + 1)}><IconRefresh />Обновить</button>}</header>
    {isStaticData ? <p className="empty">Статус инфраструктуры недоступен в учебном примере.</p> : error ? <p role="alert" className="alert alert--error">{error}</p> : !data ? <p className="loading" role="status">Проверка состояния…</p> : <>
      <div className="grid grid--stats"><StatCard label="База данных" value={data.database === 'ready' ? 'Доступна' : 'Недоступна'} tone="teal" /><StatCard label="Хранилище" value={data.storage === 'ready' ? 'Доступно' : 'Недоступно'} tone="blue" /><StatCard label="Камерный профиль" value={data.camera_enabled ? 'Включён' : 'Отключён'} tone="amber" /><StatCard label="Среда" value={data.environment} tone="green" /></div>
      <section className="section"><h2>Очередь распознавания</h2><div className="table-wrap"><table className="table"><thead><tr><th>Состояние</th><th>Заданий</th></tr></thead><tbody>{Object.entries(data.recognition_queue).map(([state, count]) => <tr key={state}><td>{{ pending: 'В очереди', processing: 'Обработка', retry_wait: 'Ожидает повтора', completed: 'Готово', failed: 'Ошибка', cancelled: 'Отменено' }[state] ?? state}</td><td>{count}</td></tr>)}{!Object.keys(data.recognition_queue).length && <tr><td colSpan={2}>Нет заданий</td></tr>}</tbody></table></div></section>
      <dl className="session-meta"><div><dt>Последняя отметка обработки</dt><dd>{data.last_job_heartbeat ? new Date(data.last_job_heartbeat).toLocaleString('ru-RU', { timeZone: data.timezone }) : 'Нет отметки'}</dd></div><div><dt>Часовой пояс</dt><dd>{data.timezone}</dd></div><div><dt>Резервное восстановление</dt><dd>{data.backup_status === 'not_verified' ? 'Не проверено' : data.backup_status}</dd></div></dl>
    </>}
  </>
}
