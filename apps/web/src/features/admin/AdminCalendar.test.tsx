import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AdminToastProvider } from './shared'
import { Calendar } from './AdminCalendar'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../../services/api', async importOriginal => {
  const original = await importOriginal<typeof import('../../services/api')>()
  return { ...original, api: mocks.api }
})
vi.mock('../../services/auth', () => ({ useAuth: () => ({ user: { timezone: 'UTC' } }) }))

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-05T10:00:00Z'))
  mocks.api.mockReset()
  HTMLDialogElement.prototype.showModal = function () { this.open = true }
  HTMLDialogElement.prototype.close = function () { this.open = false }
})
afterEach(() => { vi.useRealTimers(); cleanup() })

it('schedules a client into a published slot without converting a local input by a fixed offset', async () => {
  const slot = { coach_id: 'coach-1', coach_name: 'Coach Syre', starts_at: '2026-10-06T09:00:00Z', ends_at: '2026-10-06T10:00:00Z', status: 'AVAILABLE' }
  mocks.api.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith('/bookings/availability')) return { items: [slot], total: 1, timezone: 'Africa/Kigali', rules: { hours: [9], duration_minutes: 60 } }
    if (path.startsWith('/bookings?')) return { items: [], total: 0 }
    if (path === '/clients') return { items: [{ id: 'client-1', name: 'Client One' }], total: 1 }
    if (path === '/bookings' && options?.method === 'POST') return { id: 'booking-1', ...JSON.parse(options.body as string), status: 'CONFIRMED' }
    throw new Error(`Unexpected request: ${path}`)
  })
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={query}><AdminToastProvider><Calendar /></AdminToastProvider></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('gridcell', { name: /Tuesday, October 6, 2026/ }))
  fireEvent.click(screen.getByRole('button', { name: /Available.*Select time/ }))
  expect(screen.getByRole('dialog')).toBeInTheDocument()
  await screen.findByRole('option', { name: 'Client One' })
  fireEvent.change(await screen.findByRole('combobox', { name: 'Client' }), { target: { value: 'client-1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Book session' }))
  await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/bookings', expect.objectContaining({ method: 'POST' })))
  await screen.findByText('Session booked successfully.')
  expect(mocks.api).toHaveBeenCalledWith('/bookings', expect.objectContaining({ method: 'POST', body: expect.stringContaining('"starts_at":"2026-10-06T09:00:00Z"') }))
})
