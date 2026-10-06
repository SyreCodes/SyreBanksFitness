import { beforeEach, expect, it, vi } from 'vitest'
import { bookingsInRange } from './bookings'

const mocks = vi.hoisted(() => ({ api: vi.fn() }))
vi.mock('./api', () => ({ api: mocks.api }))

beforeEach(() => mocks.api.mockReset())

it('loads every booking page in the visible period', async () => {
  mocks.api.mockResolvedValueOnce({ items: Array.from({ length: 100 }, (_, index) => ({ id: String(index) })), total: 101 })
  mocks.api.mockResolvedValueOnce({ items: [{ id: '100' }], total: 101 })
  const result = await bookingsInRange<{ id: string }>('2026-10-01T00:00:00Z', '2026-11-01T00:00:00Z')
  expect(result.items).toHaveLength(101)
  expect(mocks.api).toHaveBeenCalledTimes(2)
  expect(mocks.api.mock.calls[1][0]).toContain('offset=100')
})
