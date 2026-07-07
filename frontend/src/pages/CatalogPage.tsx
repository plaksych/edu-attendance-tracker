import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Discipline, Group, Teacher } from '../api/types'
import { Modal } from '../components/Modal'

type Tab = 'groups' | 'teachers' | 'disciplines'

const TABS: { key: Tab; label: string }[] = [
  { key: 'groups', label: 'Группы' },
  { key: 'teachers', label: 'Преподаватели' },
  { key: 'disciplines', label: 'Дисциплины' },
]

function StudentsCountCell({ group, onSaved }: { group: Group; onSaved: () => void }) {
  const [value, setValue] = useState(String(group.students_count))
  const [saving, setSaving] = useState(false)

  useEffect(() => setValue(String(group.students_count)), [group.students_count])

  const save = async () => {
    const parsed = Number(value)
    if (!Number.isInteger(parsed) || parsed < 0 || parsed === group.students_count) {
      setValue(String(group.students_count))
      return
    }
    setSaving(true)
    try {
      await api.updateGroup(group.id, { students_count: parsed })
      onSaved()
    } finally {
      setSaving(false)
    }
  }

  return (
    <input
      className="input num"
      style={{ width: 76 }}
      type="number"
      min={0}
      value={value}
      disabled={saving}
      onChange={(e) => setValue(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
      }}
    />
  )
}

function GroupFormModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({ name: '', course: 1, faculty: '', students_count: 0 })
  const [error, setError] = useState<string | null>(null)

  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      await api.createGroup({
        name: form.name.trim(),
        course: form.course,
        faculty: form.faculty.trim() || null,
        students_count: form.students_count,
      })
      onSaved()
      onClose()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <Modal title="Новая группа" onClose={onClose}>
      <form className="modal__form" onSubmit={submit}>
        {error && <div className="alert alert--error" style={{ margin: 0 }}>{error}</div>}
        <div className="field">
          <label>Название</label>
          <input
            className="input"
            required
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="ИС-31"
          />
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="field" style={{ flex: 1 }}>
            <label>Курс</label>
            <input
              className="input"
              type="number"
              min={1}
              max={6}
              value={form.course}
              onChange={(e) => setForm({ ...form, course: Number(e.target.value) })}
            />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Численность</label>
            <input
              className="input"
              type="number"
              min={0}
              value={form.students_count}
              onChange={(e) => setForm({ ...form, students_count: Number(e.target.value) })}
            />
          </div>
        </div>
        <div className="field">
          <label>Факультет</label>
          <input
            className="input"
            value={form.faculty}
            onChange={(e) => setForm({ ...form, faculty: e.target.value })}
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

export function CatalogPage() {
  const [tab, setTab] = useState<Tab>('groups')
  const [groups, setGroups] = useState<Group[]>([])
  const [teachers, setTeachers] = useState<Teacher[]>([])
  const [disciplines, setDisciplines] = useState<Discipline[]>([])
  const [error, setError] = useState<string | null>(null)
  const [showGroupForm, setShowGroupForm] = useState(false)

  const load = useCallback(() => {
    Promise.all([api.getGroups(), api.getTeachers(), api.getDisciplines()])
      .then(([groupsData, teachersData, disciplinesData]) => {
        setGroups(groupsData)
        setTeachers(teachersData)
        setDisciplines(disciplinesData)
      })
      .catch((e: Error) => setError(e.message))
  }, [])

  useEffect(load, [load])

  return (
    <>
      <header className="page-header">
        <div>
          <h1>Справочники</h1>
          <p>Численность группы участвует в расчёте процента посещаемости</p>
        </div>
        {tab === 'groups' && (
          <button className="btn" onClick={() => setShowGroupForm(true)}>
            Добавить группу
          </button>
        )}
      </header>

      {error && <div className="alert alert--error">{error}</div>}

      <div className="segmented section" style={{ marginBottom: 16 }}>
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? 'active' : ''} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'groups' && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Группа</th>
                <th>Курс</th>
                <th>Факультет</th>
                <th>Численность</th>
              </tr>
            </thead>
            <tbody>
              {groups.length === 0 && (
                <tr>
                  <td colSpan={4} className="table__empty">
                    Групп пока нет
                    <small>Они появятся при импорте расписания</small>
                  </td>
                </tr>
              )}
              {groups.map((group) => (
                <tr key={group.id}>
                  <td className="cell-main">{group.name}</td>
                  <td className="num">{group.course}</td>
                  <td>{group.faculty ?? '—'}</td>
                  <td>
                    <StudentsCountCell group={group} onSaved={load} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'teachers' && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>ФИО</th>
                <th>Кафедра</th>
                <th>Email</th>
              </tr>
            </thead>
            <tbody>
              {teachers.length === 0 && (
                <tr>
                  <td colSpan={3} className="table__empty">Преподавателей пока нет</td>
                </tr>
              )}
              {teachers.map((teacher) => (
                <tr key={teacher.id}>
                  <td className="cell-main">{teacher.full_name}</td>
                  <td>{teacher.department ?? '—'}</td>
                  <td>{teacher.email ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'disciplines' && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Дисциплина</th>
              </tr>
            </thead>
            <tbody>
              {disciplines.length === 0 && (
                <tr>
                  <td className="table__empty">Дисциплин пока нет</td>
                </tr>
              )}
              {disciplines.map((discipline) => (
                <tr key={discipline.id}>
                  <td>{discipline.name}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showGroupForm && <GroupFormModal onClose={() => setShowGroupForm(false)} onSaved={load} />}
    </>
  )
}
