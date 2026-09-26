// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { SystemPage } from '../src/pages/SystemPage'
import { managementApi } from '../src/api/management'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('shows actual server states without claiming verified backups or worker activity', async () => {
  vi.spyOn(managementApi, 'system').mockResolvedValue({ database: 'ready', storage: 'unavailable', recognition_queue: { failed: 2 }, last_job_heartbeat: null, timezone: 'Europe/Moscow', environment: 'test', camera_enabled: false, backup_status: 'not_verified' })
  render(<SystemPage />)
  await screen.findByText('Недоступно')
  expect(screen.getByText('Не проверено')).toBeInTheDocument()
  expect(screen.getByText('Нет отметки')).toBeInTheDocument()
  expect(screen.getByRole('cell', { name: '2' })).toBeInTheDocument()
})

it('surfaces request errors and retries explicitly', async () => {
  const request = vi.spyOn(managementApi, 'system').mockRejectedValue(new Error('Сервис недоступен'))
  render(<SystemPage />)
  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')
  request.mockResolvedValue({ database: 'ready', storage: 'ready', recognition_queue: {}, last_job_heartbeat: null, timezone: 'Europe/Moscow', environment: 'test', camera_enabled: false, backup_status: 'not_verified' })
  fireEvent.click(screen.getByRole('button', { name: 'Обновить' }))
  await screen.findByText('Нет заданий')
  expect(request).toHaveBeenCalledTimes(2)
})
