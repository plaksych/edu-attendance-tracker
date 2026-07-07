import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { AggregationMode, Camera, CameraRole, Classroom } from '../api/types'
import { Modal } from '../components/Modal'

const MODE_LABELS: Record<AggregationMode, string> = {
  single: 'одна камера',
  maximum: 'максимум (зоны пересекаются)',
  sum: 'сумма (зоны раздельные)',
  primary_backup: 'основная + резервная',
}

const ROLE_LABELS: Record<CameraRole, string> = {
  primary: 'основная',
  secondary: 'вторая',
  backup: 'резервная',
}

interface CameraFormState {
  id: number | null
  name: string
  rtsp_url: string
  capture_group: string
  enabled: boolean
}

const EMPTY_CAMERA: CameraFormState = {
  id: null,
  name: '',
  rtsp_url: '',
  capture_group: 'default',
  enabled: true,
}

interface AssignRow {
  camera_id: number | ''
  role: CameraRole
}

function CameraFormModal({
  initial,
  onClose,
  onSaved,
}: {
  initial: CameraFormState
  onClose: () => void
  onSaved: () => void
}) {
  const [form, setForm] = useState(initial)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const isNew = form.id === null

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      if (isNew) {
        await api.createCamera({
          name: form.name.trim(),
          rtsp_url: form.rtsp_url.trim(),
          capture_group: form.capture_group.trim() || 'default',
          enabled: form.enabled,
        })
      } else {
        await api.updateCamera(form.id!, {
          name: form.name.trim(),
          capture_group: form.capture_group.trim() || 'default',
          enabled: form.enabled,
          // адрес меняется только если поле заполнено
          ...(form.rtsp_url.trim() ? { rtsp_url: form.rtsp_url.trim() } : {}),
        })
      }
      onSaved()
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={isNew ? 'Новая камера' : 'Изменить камеру'} onClose={onClose}>
      <form className="modal__form" onSubmit={submit}>
        {error && <div className="alert alert--error" style={{ margin: 0 }}>{error}</div>}
        <div className="field">
          <label>Имя камеры</label>
          <input
            className="input"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="cam-302-front"
          />
        </div>
        <div className="field">
          <label>{isNew ? 'RTSP-адрес' : 'Новый RTSP-адрес (пусто — без изменений)'}</label>
          <input
            className="input"
            required={isNew}
            value={form.rtsp_url}
            onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
            placeholder="rtsp://user:password@192.168.1.10:554/stream1"
          />
        </div>
        <div className="field">
          <label>Capture-группа (сетевая зона)</label>
          <input
            className="input"
            value={form.capture_group}
            onChange={(e) => setForm({ ...form, capture_group: e.target.value })}
            placeholder="default"
          />
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13.5 }}>
          <span className="switch">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
            />
            <span className="switch__track" />
          </span>
          Камера участвует в замерах
        </label>
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn" disabled={saving}>
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function AssignModal({
  classroom,
  cameras,
  onClose,
  onSaved,
}: {
  classroom: Classroom
  cameras: Camera[]
  onClose: () => void
  onSaved: () => void
}) {
  const [rows, setRows] = useState<AssignRow[]>(() => {
    const current = classroom.cameras.map((link) => ({
      camera_id: link.camera.id as number | '',
      role: link.role,
    }))
    return current.length > 0 ? current : [{ camera_id: '', role: 'primary' }]
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  // Камера занята, если уже привязана к другой аудитории
  const takenElsewhere = new Set(
    cameras
      .filter(
        (c) => c.classroom_number !== null && c.classroom_number !== classroom.number,
      )
      .map((c) => c.id),
  )

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload = rows
        .filter((row): row is { camera_id: number; role: CameraRole } => row.camera_id !== '')
        .map((row, index) => ({
          camera_id: row.camera_id,
          role: row.role,
          priority: index + 1,
        }))
      await api.assignClassroomCameras(classroom.id, payload)
      onSaved()
      onClose()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={`Камеры аудитории ${classroom.number}`} onClose={onClose}>
      <form className="modal__form" onSubmit={submit}>
        {error && <div className="alert alert--error" style={{ margin: 0 }}>{error}</div>}
        {rows.map((row, index) => (
          <div key={index} style={{ display: 'flex', gap: 8 }}>
            <select
              className="select"
              style={{ flex: 1 }}
              value={row.camera_id}
              onChange={(e) => {
                const next = [...rows]
                next[index] = {
                  ...row,
                  camera_id: e.target.value === '' ? '' : Number(e.target.value),
                }
                setRows(next)
              }}
            >
              <option value="">— не выбрана —</option>
              {cameras.map((camera) => (
                <option
                  key={camera.id}
                  value={camera.id}
                  disabled={takenElsewhere.has(camera.id)}
                >
                  {camera.name}
                  {takenElsewhere.has(camera.id) ? ` (занята: ${camera.classroom_number})` : ''}
                </option>
              ))}
            </select>
            <select
              className="select"
              value={row.role}
              onChange={(e) => {
                const next = [...rows]
                next[index] = { ...row, role: e.target.value as CameraRole }
                setRows(next)
              }}
            >
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        ))}
        <div style={{ display: 'flex', gap: 8 }}>
          {rows.length < 2 && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => setRows([...rows, { camera_id: '', role: 'secondary' }])}
            >
              + вторая камера
            </button>
          )}
          {rows.length === 2 && (
            <button
              type="button"
              className="btn btn--ghost btn--sm"
              onClick={() => setRows(rows.slice(0, 1))}
            >
              Убрать вторую
            </button>
          )}
        </div>
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn" disabled={saving}>
            {saving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </div>
      </form>
    </Modal>
  )
}

function ClassroomFormModal({
  onClose,
  onSaved,
}: {
  onClose: () => void
  onSaved: () => void
}) {
  const [number, setNumber] = useState('')
  const [capacity, setCapacity] = useState('')
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      await api.createClassroom({
        number: number.trim(),
        capacity: capacity ? Number(capacity) : null,
      })
      onSaved()
      onClose()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <Modal title="Новая аудитория" onClose={onClose}>
      <form className="modal__form" onSubmit={submit}>
        {error && <div className="alert alert--error" style={{ margin: 0 }}>{error}</div>}
        <div className="field">
          <label>Номер аудитории</label>
          <input className="input" required value={number} onChange={(e) => setNumber(e.target.value)} />
        </div>
        <div className="field">
          <label>Вместимость</label>
          <input
            className="input"
            type="number"
            min={1}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
        </div>
        <div className="modal__actions">
          <button type="button" className="btn btn--ghost" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="btn">
            Создать
          </button>
        </div>
      </form>
    </Modal>
  )
}

export function CamerasPage() {
  const [classrooms, setClassrooms] = useState<Classroom[] | null>(null)
  const [cameras, setCameras] = useState<Camera[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [cameraForm, setCameraForm] = useState<CameraFormState | null>(null)
  const [assignFor, setAssignFor] = useState<Classroom | null>(null)
  const [showClassroomForm, setShowClassroomForm] = useState(false)

  const load = useCallback(() => {
    Promise.all([api.getClassrooms(), api.getCameras()])
      .then(([classroomsData, camerasData]) => {
        setClassrooms(classroomsData)
        setCameras(camerasData)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(load, [load])

  const changeMode = async (classroom: Classroom, mode: AggregationMode) => {
    try {
      await api.updateClassroom(classroom.id, { aggregation_mode: mode })
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const toggleCamera = async (camera: Camera) => {
    try {
      await api.updateCamera(camera.id, { enabled: !camera.enabled })
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const removeCamera = async (camera: Camera) => {
    if (!window.confirm(`Удалить камеру ${camera.name}?`)) return
    try {
      await api.deleteCamera(camera.id)
      load()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Аудитории и камеры</h1>
          <p>Привязка камер, роли и режим объединения результатов</p>
        </div>
        <div className="page-header__actions">
          <button className="btn btn--ghost" onClick={() => setShowClassroomForm(true)}>
            Добавить аудиторию
          </button>
          <button className="btn" onClick={() => setCameraForm(EMPTY_CAMERA)}>
            Добавить камеру
          </button>
        </div>
      </header>

      {error && <div className="alert alert--error">{error}</div>}

      <section className="section">
        <h2>Аудитории</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Аудитория</th>
                <th>Вместимость</th>
                <th>Камеры</th>
                <th>Режим объединения</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {classrooms === null && (
                <tr>
                  <td colSpan={5} className="table__empty">Загрузка…</td>
                </tr>
              )}
              {classrooms?.length === 0 && (
                <tr>
                  <td colSpan={5} className="table__empty">
                    Аудиторий пока нет
                    <small>Они появятся при импорте расписания или добавьте вручную</small>
                  </td>
                </tr>
              )}
              {classrooms?.map((classroom) => (
                <tr key={classroom.id}>
                  <td className="cell-main">{classroom.number}</td>
                  <td className="num">{classroom.capacity ?? '—'}</td>
                  <td>
                    {classroom.cameras.length === 0 ? (
                      <span style={{ color: 'var(--text-faint)' }}>нет камер</span>
                    ) : (
                      classroom.cameras.map((link) => (
                        <span
                          key={link.camera.id}
                          className={`pill ${link.enabled ? 'pill--blue' : 'pill--gray'}`}
                          style={{ marginRight: 6 }}
                          title={ROLE_LABELS[link.role]}
                        >
                          {link.camera.name}
                          {!link.enabled && ' (выкл)'}
                        </span>
                      ))
                    )}
                  </td>
                  <td>
                    <select
                      className="select"
                      value={classroom.aggregation_mode}
                      onChange={(e) => changeMode(classroom, e.target.value as AggregationMode)}
                    >
                      {Object.entries(MODE_LABELS).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn--ghost btn--sm" onClick={() => setAssignFor(classroom)}>
                      Камеры…
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h2>Камеры</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Имя</th>
                <th>Адрес</th>
                <th>Capture-группа</th>
                <th>Аудитория</th>
                <th>Активна</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {cameras === null && (
                <tr>
                  <td colSpan={6} className="table__empty">Загрузка…</td>
                </tr>
              )}
              {cameras?.length === 0 && (
                <tr>
                  <td colSpan={6} className="table__empty">
                    Камеры не добавлены
                    <small>Добавьте камеру и привяжите её к аудитории</small>
                  </td>
                </tr>
              )}
              {cameras?.map((camera) => (
                <tr key={camera.id}>
                  <td className="cell-main">{camera.name}</td>
                  <td style={{ fontFamily: 'ui-monospace, monospace', fontSize: 12.5 }}>
                    {camera.rtsp_url}
                  </td>
                  <td>{camera.capture_group}</td>
                  <td>{camera.classroom_number ?? '—'}</td>
                  <td>
                    <span className="switch">
                      <input
                        type="checkbox"
                        checked={camera.enabled}
                        onChange={() => toggleCamera(camera)}
                      />
                      <span className="switch__track" />
                    </span>
                  </td>
                  <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button
                      className="btn btn--ghost btn--sm"
                      style={{ marginRight: 6 }}
                      onClick={() =>
                        setCameraForm({
                          id: camera.id,
                          name: camera.name,
                          rtsp_url: '',
                          capture_group: camera.capture_group,
                          enabled: camera.enabled,
                        })
                      }
                    >
                      Изменить
                    </button>
                    <button className="btn btn--danger-ghost btn--sm" onClick={() => removeCamera(camera)}>
                      Удалить
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {cameraForm && (
        <CameraFormModal initial={cameraForm} onClose={() => setCameraForm(null)} onSaved={load} />
      )}
      {assignFor && cameras && (
        <AssignModal
          classroom={assignFor}
          cameras={cameras}
          onClose={() => setAssignFor(null)}
          onSaved={load}
        />
      )}
      {showClassroomForm && (
        <ClassroomFormModal onClose={() => setShowClassroomForm(false)} onSaved={load} />
      )}
    </>
  )
}
