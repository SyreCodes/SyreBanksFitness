import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { BookingCalendar, calendarBounds, monthDays, useCalendarNavigation, type CalendarSlot } from './BookingCalendar'

const slot: CalendarSlot = { coach_id: 'coach-1', coach_name: 'Coach Syre', starts_at: '2026-10-06T09:00:00Z', ends_at: '2026-10-06T10:00:00Z', status: 'AVAILABLE' }

function Harness({ onSelect = () => undefined }: { onSelect?: (slot: CalendarSlot) => void }) {
  const navigation = useCalendarNavigation('UTC')
  return <BookingCalendar navigation={navigation} slots={[slot]} bookings={[]} timezone="UTC" rules={{ hours: [9, 10], duration_minutes: 60 }} onSelectSlot={onSelect} />
}

describe('booking calendar', () => {
  beforeEach(() => { vi.useFakeTimers({ toFake: ['Date'] }); vi.setSystemTime(new Date('2026-10-05T10:00:00Z')) })
  afterEach(() => { vi.useRealTimers(); cleanup() })

  it('renders a Sunday-first seven-column month with muted adjacent days and a selected-day agenda', () => {
    render(<Harness />)
    expect(screen.getByRole('heading', { name: 'October 2026' })).toBeInTheDocument()
    expect(screen.getAllByRole('columnheader').map(node => node.textContent)).toEqual(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
    expect(screen.getAllByRole('gridcell')).toHaveLength(42)
    expect(monthDays('2026-10-05')[0]).toBe('2026-09-27')
    expect(screen.getByRole('gridcell', { name: /Monday, October 5, 2026/ })).toHaveClass('today')
    expect(screen.getByRole('gridcell', { name: /Sunday, September 27, 2026/ })).toHaveClass('outside')
    fireEvent.click(screen.getByRole('gridcell', { name: /Tuesday, October 6, 2026/ }))
    expect(screen.getByRole('heading', { name: 'Tuesday, October 6' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /09:00–10:00.*Available.*Select time/ })).toBeInTheDocument()
  })

  it('navigates previous, next and Today across month, week and day time grids', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Previous period' }))
    expect(screen.getByRole('heading', { name: 'September 2026' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next period' }))
    expect(screen.getByRole('heading', { name: 'October 2026' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Week' }))
    expect(screen.getByRole('heading', { name: 'Oct 5 – Oct 11, 2026' })).toBeInTheDocument()
    expect(screen.getByLabelText('week time grid')).toBeInTheDocument()
    expect(screen.getByText('09:00')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Next period' }))
    expect(screen.getByRole('heading', { name: 'Oct 12 – Oct 18, 2026' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Today' }))
    expect(screen.getByRole('heading', { name: 'Oct 5 – Oct 11, 2026' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Day' }))
    expect(screen.getByRole('heading', { name: 'Monday, October 5, 2026' })).toBeInTheDocument()
    expect(screen.getByLabelText('day time grid')).toBeInTheDocument()
  })

  it('sends timezone-safe bounded requests and selects an available slot', () => {
    const onSelect = vi.fn()
    render(<Harness onSelect={onSelect} />)
    expect(calendarBounds('2026-10-05', 'month')).toEqual({ start: '2026-09-26T00:00:00.000Z', end: '2026-11-09T00:00:00.000Z' })
    fireEvent.click(screen.getByRole('gridcell', { name: /Tuesday, October 6, 2026/ }))
    fireEvent.click(screen.getByRole('button', { name: /09:00–10:00.*Available.*Select time/ }))
    expect(onSelect).toHaveBeenCalledWith(slot)
  })
})
