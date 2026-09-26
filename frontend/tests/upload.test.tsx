// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { RecognitionPage } from '../src/pages/RecognitionPage'
import { api } from '../src/api/client'
import { managementApi } from '../src/api/management'
import type { RecognitionUpload } from '../src/api/types'

afterEach(() => { cleanup(); vi.restoreAllMocks() })
function prepare() {
  vi.spyOn(api, 'getRecognitionUploads').mockResolvedValue([])
  vi.spyOn(api, 'getRecognitionEvaluationSummary').mockResolvedValue({ checked_materials: 0, within_tolerance_count: 0, mean_absolute_error: null, median_absolute_error: null, max_absolute_error: null, mean_relative_error: null })
  vi.spyOn(managementApi, 'capabilities').mockResolvedValue({ profile: 'server_inference', formats: ['png'], max_size_bytes: 1000, max_pixels: 1000000, max_duration_seconds: 10, max_video_dimension: 1920, sample_rate_fps: { min: .1, max: 10 }, confidence: { min: .05, max: .95 } })
  render(<MemoryRouter><RecognitionPage /></MemoryRouter>)
  fireEvent.click(screen.getByRole('button', { name: 'Добавить материал' }))
}
it('waits for capabilities, rejects oversized file, and never submits it', async () => {
  const upload = vi.spyOn(api, 'uploadRecognition')
  prepare()
  await waitFor(() => expect(screen.getByLabelText('Видео или изображение')).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Видео или изображение'), { target: { files: [new File(['x'.repeat(1001)], 'frame.png')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Отправить' }))
  await screen.findByText(/Допустимый размер/)
  expect(upload).not.toHaveBeenCalled()
})
it('reuses the idempotency key after an uncertain network result', async () => {
  const upload = vi.spyOn(api, 'uploadRecognition').mockRejectedValueOnce(new Error('Соединение прервано')).mockResolvedValueOnce({ id: 1, job: { id: 1, status: 'pending', result: null, confidence_threshold: .35 }, filename: 'frame.png', size_bytes: 4, media_type: 'image' } as RecognitionUpload)
  vi.spyOn(api, 'getRecognitionUploadMedia').mockResolvedValue({ source_url: null, annotated_url: null, source_unavailable_reason: null, annotated_unavailable_reason: null, expires_in_seconds: 0 })
  vi.spyOn(managementApi, 'history').mockResolvedValue({ jobs: [], corrections: [] })
  prepare()
  await waitFor(() => expect(screen.getByLabelText('Видео или изображение')).toBeEnabled())
  fireEvent.change(screen.getByLabelText('Видео или изображение'), { target: { files: [new File(['test'], 'frame.png')] } })
  fireEvent.click(screen.getByRole('button', { name: 'Отправить' }))
  await screen.findByText('Соединение прервано')
  expect(upload).toHaveBeenCalledOnce()
  const key = upload.mock.calls[0][0].idempotency_key
  fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Отправить' }))
  await waitFor(() => expect(upload).toHaveBeenCalledTimes(2))
  expect(upload.mock.calls[1][0].idempotency_key).toBe(key)
  expect(key).toMatch(/^[a-f\d-]{36}$/)
})
