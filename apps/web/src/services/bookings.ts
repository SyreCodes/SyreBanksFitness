import { api, type ListResult } from './api'

export async function bookingsInRange<T>(start: string, end: string): Promise<ListResult<T>> {
  const items: T[] = []
  let total = 0
  while (true) {
    const params = new URLSearchParams({ start, end, limit: '100', offset: String(items.length) })
    const page = await api<ListResult<T>>(`/bookings?${params}`)
    total = page.total
    items.push(...page.items)
    if (!page.items.length || items.length >= total) return { items, total }
  }
}
