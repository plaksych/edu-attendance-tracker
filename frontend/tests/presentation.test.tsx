// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { api } from '../src/api/client'
import { staticApi } from '../src/api/staticClient'
import { PresentationControls, presentationSteps } from '../src/components/PresentationControls'
import { DEMO_DATE } from '../src/lib/format'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

function Location() {
  const location = useLocation()
  return <output data-testid="location">{location.pathname}{location.search}</output>
}
function mount() {
  render(<MemoryRouter initialEntries={[`/sessions?date=${DEMO_DATE}&group=1&q=test`]}><PresentationControls onActiveChange={vi.fn()} /><Location /></MemoryRouter>)
}
async function start() {
  const sessions = await staticApi.getSessions(DEMO_DATE)
  // This is deliberately not a fixture ID: live mode must use the API response.
  vi.spyOn(api, 'getSessions').mockResolvedValue([{ ...sessions[0], id: 867 }])
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Режим показа' }))
  await screen.findByText('1 / 4 · Обзор')
}

it('sorts deterministically and carries the selected session group into analytics', async () => {
  const sessions = await staticApi.getSessions(DEMO_DATE)
  const steps = presentationSteps([...sessions].reverse(), DEMO_DATE)
  expect(steps[2].to).toBe(`/sessions/${sessions[0].id}?date=${DEMO_DATE}`)
  expect(steps[3].to).toContain(`group=${sessions[0].schedule.group.id}`)
  expect(steps[3].to).toContain('from=2026-09-10&to=2026-09-23')
})

it('uses an empty-session list instead of inventing a session ID', () => {
  const steps = presentationSteps([], DEMO_DATE)
  expect(steps[2]).toEqual({ label: 'Занятия: нет данных', to: `/sessions?date=${DEMO_DATE}` })
  expect(steps[3].to).not.toContain('group=')
})

it('navigates forward/back using the API ID and exits on the current screen', async () => {
  await start()
  expect(api.getSessions).toHaveBeenCalledWith(DEMO_DATE)
  expect(screen.getByRole('button', { name: 'Назад' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Далее' }))
  expect(screen.getByTestId('location')).toHaveTextContent('/recognition')
  fireEvent.click(screen.getByRole('button', { name: 'Далее' }))
  expect(screen.getByTestId('location')).toHaveTextContent('/sessions/867?date=2026-09-23')
  fireEvent.click(screen.getByRole('button', { name: 'Назад' }))
  expect(screen.getByTestId('location')).toHaveTextContent('/recognition')
  fireEvent.click(screen.getByRole('button', { name: 'Выйти из показа' }))
  expect(screen.getByRole('button', { name: 'Режим показа' })).toBeInTheDocument()
  expect(screen.getByTestId('location')).toHaveTextContent('/recognition')
})

it('restores the original route and filters on return to work', async () => {
  await start()
  fireEvent.click(screen.getByRole('button', { name: 'Вернуться к работе' }))
  expect(screen.getByTestId('location')).toHaveTextContent(`/sessions?date=${DEMO_DATE}&group=1&q=test`)
})

it('exits with Escape but gives a nested dialog priority', async () => {
  await start()
  const modal = document.createElement('div')
  modal.setAttribute('role', 'dialog')
  document.body.append(modal)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.getByRole('region', { name: 'Навигация показа' })).toBeInTheDocument()
  modal.remove()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('region', { name: 'Навигация показа' })).not.toBeInTheDocument()
})

it('does not replace an API failure with demo data', async () => {
  vi.spyOn(api, 'getSessions').mockRejectedValue(new Error('Сервис недоступен'))
  mount()
  fireEvent.click(screen.getByRole('button', { name: 'Режим показа' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен')
  expect(screen.getByTestId('location')).toHaveTextContent('/sessions?date=')
  expect(screen.queryByRole('region', { name: 'Навигация показа' })).not.toBeInTheDocument()
})

it('keeps the sequence usable when fullscreen is refused', async () => {
  const enabled = Object.getOwnPropertyDescriptor(document, 'fullscreenEnabled')
  Object.defineProperty(document, 'fullscreenEnabled', { configurable: true, value: true })
  const request = vi.fn().mockRejectedValue(new Error('Denied'))
  Object.defineProperty(document.documentElement, 'requestFullscreen', { configurable: true, value: request })
  try {
    await start()
    fireEvent.click(screen.getByRole('button', { name: 'Полный экран' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Показ продолжается в окне')
    expect(screen.getByRole('button', { name: 'Далее' })).toBeEnabled()
  } finally {
    if (enabled) Object.defineProperty(document, 'fullscreenEnabled', enabled)
    else Reflect.deleteProperty(document, 'fullscreenEnabled')
    Reflect.deleteProperty(document.documentElement, 'requestFullscreen')
  }
})
