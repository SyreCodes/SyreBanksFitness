import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BookingsPage } from './coaching'
import { ApiError } from '../../services/api'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('../../services/api', async importOriginal => {
  const original = await importOriginal<typeof import('../../services/api')>()
  return { ...original, api: mocks.api }
})
vi.mock('../../services/auth', () => ({ useAuth: () => ({ user: { timezone: 'UTC' } }) }))

const slot = { coach_id: 'coach-1', coach_name: 'Coach Syre', starts_at: '2026-10-06T09:00:00Z', ends_at: '2026-10-06T10:00:00Z', status: 'AVAILABLE' }

function renderPage() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={query}><BookingsPage /></QueryClientProvider>)
}

describe('client calendar booking', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-05T10:00:00Z'))
    mocks.api.mockReset()
    HTMLDialogElement.prototype.showModal = function () { this.open = true }
    HTMLDialogElement.prototype.close = function () { this.open = false }
  })
  afterEach(() => { vi.useRealTimers(); cleanup() })

  it('opens a confirmation modal and updates the calendar after booking', async () => {
    let booked = false
    mocks.api.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.startsWith('/bookings/availability')) return { items: [{ ...slot, status: booked ? 'BOOKED' : 'AVAILABLE', booked_by_me: booked }], total: 1, timezone: 'UTC', rules: { hours: [9], duration_minutes: 60 } }
      if (path.startsWith('/bookings?')) return { items: booked ? [{ id: 'booking-1', ...slot, status: 'CONFIRMED' }] : [], total: booked ? 1 : 0 }
      if (path === '/bookings' && options?.method === 'POST') { booked = true; return { id: 'booking-1', ...JSON.parse(options.body as string), status: 'CONFIRMED' } }
      throw new Error(`Unexpected request: ${path}`)
    })
    renderPage()
    await screen.findByRole('gridcell', { name: /Tuesday, October 6, 2026/ })
    fireEvent.click(screen.getByRole('gridcell', { name: /Tuesday, October 6, 2026/ }))
    fireEvent.click(screen.getByRole('button', { name: /Available.*Select time/ }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Coach Syre')).toBeInTheDocument()
    expect(screen.getByText('60 minutes')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Book session' }))
    await screen.findByText(/Session booked successfully/)
    await waitFor(() => expect(screen.getByRole('gridcell', { name: /Tuesday, October 6, 2026; 0 available, 1 booked/ })).toBeInTheDocument())
    expect(mocks.api).toHaveBeenCalledWith('/bookings', expect.objectContaining({ method: 'POST', body: expect.stringContaining('"coach_id":"coach-1"') }))
  })

  it('keeps the modal open and explains a slot conflict', async () => {
    mocks.api.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.startsWith('/bookings/availability')) return { items: [slot], total: 1, timezone: 'UTC', rules: { hours: [9], duration_minutes: 60 } }
      if (path.startsWith('/bookings?')) return { items: [], total: 0 }
      if (path === '/bookings' && options?.method === 'POST') throw new ApiError('This slot is no longer available', 409, 'BOOKING_CONFLICT')
      throw new Error(`Unexpected request: ${path}`)
    })
    renderPage()
    await screen.findByRole('gridcell', { name: /Tuesday, October 6, 2026/ })
    fireEvent.click(screen.getByRole('gridcell', { name: /Tuesday, October 6, 2026/ }))
    fireEvent.click(screen.getByRole('button', { name: /Available.*Select time/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Book session' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('This slot is no longer available. Choose another time from the updated calendar.')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})
