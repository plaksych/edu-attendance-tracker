// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SchedulePage } from '../src/pages/SchedulePage'
import { api } from '../src/api/client'
import { managementApi } from '../src/api/management'
vi.mock('../src/auth/SessionProvider', () => ({ useSession: () => ({ user: { role: 'operator' } }) }))
afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('previews XLSX without applying, then explicitly confirms once', async () => {
  vi.spyOn(api, 'getGroups').mockResolvedValue([])
  vi.spyOn(api, 'getSchedule').mockResolvedValue([])
  const preview = vi.spyOn(managementApi, 'previewSchedule').mockResolvedValue({ preview_id: 'preview-1', expires_at: '2099-01-01T12:00:00Z', created: 2, skipped: 0, errors: [], rows: [] })
  const confirm = vi.spyOn(managementApi, 'confirmSchedule').mockResolvedValue({ created: 2, skipped: 0, errors: [] })
  const { container } = render(<SchedulePage />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['xlsx'], 'schedule.xlsx')] } })
  await screen.findByRole('dialog', { name: 'Предпросмотр импорта' })
  expect(preview).toHaveBeenCalledOnce()
  expect(confirm).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Подтвердить импорт' }))
  await waitFor(() => expect(confirm).toHaveBeenCalledWith('preview-1'))
  await screen.findByText(/Импорт завершён/)
  expect(confirm).toHaveBeenCalledOnce()
})

it('blocks confirmation when preview has row errors', async () => {
  vi.spyOn(api, 'getGroups').mockResolvedValue([])
  vi.spyOn(api, 'getSchedule').mockResolvedValue([])
  vi.spyOn(managementApi, 'previewSchedule').mockResolvedValue({ preview_id: 'preview-2', expires_at: '2099-01-01T12:00:00Z', created: 0, skipped: 0, errors: ['Строка 4: конфликт аудитории'], rows: [] })
  const { container } = render(<SchedulePage />)
  fireEvent.change(container.querySelector('input[type=file]')!, { target: { files: [new File(['xlsx'], 'schedule.xlsx')] } })
  await screen.findByText('Строка 4: конфликт аудитории')
  expect(screen.getByRole('button', { name: 'Подтвердить импорт' })).toBeDisabled()
})
