// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { LocalRecognitionDialog } from '../src/components/LocalRecognitionDialog'

const recognition = vi.hoisted(() => ({ get: vi.fn(), release: vi.fn(), detect: vi.fn() }))
vi.mock('../src/lib/browserRecognition', () => ({ getBrowserRecognizer: recognition.get, releaseBrowserRecognizer: recognition.release }))

function pngFile(name = 'frame.png') {
  const file = new File(['test file'], name, { type: 'image/png' })
  Object.defineProperty(file, 'slice', { value: () => ({ arrayBuffer: async () => new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10]).buffer }) })
  return file
}

async function selectImage(width = 640, height = 480) {
  fireEvent.change(screen.getByLabelText('Фото или видео'), { target: { files: [pngFile()] } })
  const image = await screen.findByAltText('Выбранное изображение')
  Object.defineProperties(image, { naturalWidth: { value: width }, naturalHeight: { value: height } })
  fireEvent.load(image)
  return image
}

describe('local recognition dialog races and validation (mock worker)', () => {
  beforeEach(() => {
    recognition.get.mockReset().mockResolvedValue({ detect: recognition.detect })
    recognition.detect.mockReset()
    recognition.release.mockReset()
    let sequence = 0
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => `blob:http://localhost/${++sequence}`) })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  })
  afterEach(() => cleanup())

  it('does not load runtime/model on open or file selection', async () => {
    render(<LocalRecognitionDialog onClose={vi.fn()} />)
    expect(recognition.get).not.toHaveBeenCalled()
    await selectImage()
    expect(recognition.get).not.toHaveBeenCalled()
    expect(screen.getByRole('status').textContent).toBe('Готово к обработке')
    expect(screen.getByRole('button', { name: 'Распознать' }).hasAttribute('disabled')).toBe(false)
  })

  it('rejects oversized dimensions and releases the object URL', async () => {
    render(<LocalRecognitionDialog onClose={vi.fn()} />)
    await selectImage(5000, 5000)
    expect(screen.getByRole('alert').textContent).toContain('16 Мп')
    expect(screen.queryByAltText('Выбранное изображение')).toBeNull()
    expect(URL.revokeObjectURL).toHaveBeenCalled()
    expect(recognition.get).not.toHaveBeenCalled()
  })

  it('handles decode errors without enabling inference', async () => {
    render(<LocalRecognitionDialog onClose={vi.fn()} />)
    const image = await selectImage()
    fireEvent.error(image)
    expect(screen.getByRole('alert').textContent).toContain('повреждено')
    expect(screen.getByRole('button', { name: 'Повторить' }).hasAttribute('disabled')).toBe(true)
    expect(recognition.get).not.toHaveBeenCalled()
  })

  it('can stop during initialization and ignores its late completion', async () => {
    let resolve!: (value: object) => void
    recognition.get.mockReturnValue(new Promise((done) => { resolve = done }))
    render(<LocalRecognitionDialog onClose={vi.fn()} />)
    await selectImage()
    fireEvent.click(screen.getByRole('button', { name: 'Распознать' }))
    expect(screen.getByRole('status').textContent).toBe('Подготовка модели')
    fireEvent.click(screen.getByRole('button', { name: 'Остановить' }))
    await act(async () => resolve({ detect: recognition.detect }))
    expect(recognition.detect).not.toHaveBeenCalled()
    expect(screen.getByRole('status').textContent).toBe('Обработка остановлена')
  })

  it('allows retry after init failure and never displays a fixture', async () => {
    recognition.get.mockRejectedValueOnce(new Error('Model HTTP 503'))
    render(<LocalRecognitionDialog onClose={vi.fn()} />)
    await selectImage()
    fireEvent.click(screen.getByRole('button', { name: 'Распознать' }))
    await screen.findByText('Model HTTP 503')
    expect(screen.queryByText('Найдено в кадре')).toBeNull()
    recognition.detect.mockRejectedValueOnce(new Error('No supported output'))
    fireEvent.click(screen.getByRole('button', { name: 'Повторить' }))
    await screen.findByText('No supported output')
    expect(recognition.get).toHaveBeenCalledTimes(2)
    expect(screen.queryByText('Найдено в кадре')).toBeNull()
  })

  it('ignores an old result after file replacement and frees resources on unmount', async () => {
    let resolve!: (value: object) => void
    recognition.detect.mockReturnValue(new Promise((done) => { resolve = done }))
    const view = render(<LocalRecognitionDialog onClose={vi.fn()} />)
    await selectImage()
    fireEvent.click(screen.getByRole('button', { name: 'Распознать' }))
    await waitFor(() => expect(recognition.detect).toHaveBeenCalledOnce())
    await selectImage()
    await act(async () => resolve({ boxes: [{ x: 1, y: 1, width: 10, height: 10, confidence: 0.9 }] }))
    expect(screen.queryByText('Найдено в кадре')).toBeNull()
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    expect(recognition.release.mock.calls.length).toBeGreaterThanOrEqual(3)
  })

  it('labels actual-result fields as browser inference and exports provenance rather than accuracy', async () => {
    recognition.detect.mockResolvedValue({
      boxes: [], averageConfidence: null, elapsedMs: 12, provenance: 'browser_inference',
      model: 'test-only-mocked-model', modelSha256: 'test-only', runtime: 'mock transport',
      sourceWidth: 640, sourceHeight: 480, confidenceThreshold: 0.35,
      nmsIouThreshold: 0.45, processedAt: '2026-09-23T00:00:00Z',
    })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined)
    const view = render(<LocalRecognitionDialog onClose={vi.fn()} />)
    await selectImage()
    fireEvent.click(screen.getByRole('button', { name: 'Распознать' }))
    await screen.findByText('Найдено в кадре')
    expect(screen.getByText(/Это не точность подсчёта/)).toBeTruthy()
    expect(screen.getByRole('status').textContent).toBe('Обработано в браузере')
    fireEvent.click(screen.getByRole('button', { name: 'Скачать локальный результат JSON' }))
    const blob = vi.mocked(URL.createObjectURL).mock.calls.at(-1)![0] as Blob
    const reader = new FileReader()
    const content = new Promise<string>((resolve) => { reader.onload = () => resolve(String(reader.result)) })
    reader.readAsText(blob)
    const report = JSON.parse(await content)
    expect(report).toMatchObject({ provenance: 'browser_inference', count: 0, quality: { confidenceIsAccuracy: false, classroomAccuracy: 'not_evaluated' } })
    view.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2)
    click.mockRestore()
  })
})
