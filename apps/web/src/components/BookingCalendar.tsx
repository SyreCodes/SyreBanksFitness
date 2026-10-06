import { useMemo, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import './BookingCalendar.css'

export type CalendarView = 'month' | 'week' | 'day'
export type CalendarSlot = {
  coach_id: string
  coach_name?: string
  starts_at: string
  ends_at: string
  status?: 'AVAILABLE' | 'BOOKED' | 'BLOCKED' | 'PAST'
  reason?: string
  booked_by_me?: boolean
  booking_id?: string
  timezone?: string
}
export type CalendarBooking = {
  id: string
  coach_id?: string
  client_name?: string
  starts_at: string
  ends_at?: string
  type?: string
  status: string
}
export type CalendarRules = {
  timezone?: string
  weekdays?: number[]
  hours?: number[]
  duration_minutes?: number
  blocked_dates?: string[]
  vacation_ranges?: { start_date: string; end_date: string }[]
  minimum_notice_minutes?: number
  max_advance_days?: number
  cancellation_notice_hours?: number
}
export type CalendarAvailability = {
  items: CalendarSlot[]
  total: number
  timezone?: string
  viewer_timezone?: string
  rules?: CalendarRules
  coach_rules?: Record<string, CalendarRules>
}

function utcDay(key: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
}
function keyFromUtcDay(date: Date): string { return date.toISOString().slice(0, 10) }
export function shiftDay(key: string, amount: number): string {
  const date = utcDay(key)
  date.setUTCDate(date.getUTCDate() + amount)
  return keyFromUtcDay(date)
}
export function dateKey(value: string | Date, timezone: string): string {
  const date = typeof value === 'string' ? new Date(value) : value
  let formatter = dateFormatters.get(timezone)
  if (!formatter) {
    formatter = new Intl.DateTimeFormat('en-US', { timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit' })
    dateFormatters.set(timezone, formatter)
  }
  const parts = formatter.formatToParts(date)
  const valueFor = (type: string) => parts.find(part => part.type === type)?.value ?? ''
  return `${valueFor('year')}-${valueFor('month')}-${valueFor('day')}`
}
const dateFormatters = new Map<string, Intl.DateTimeFormat>()
function startOfWeek(key: string, monday = false): string {
  const weekday = utcDay(key).getUTCDay()
  return shiftDay(key, -((weekday + (monday ? 6 : 0)) % 7))
}
export function monthDays(anchor: string): string[] {
  const first = startOfWeek(`${anchor.slice(0, 7)}-01`)
  return Array.from({ length: 42 }, (_, index) => shiftDay(first, index))
}
export function visibleDays(anchor: string, view: CalendarView): string[] {
  if (view === 'month') return monthDays(anchor)
  if (view === 'week') {
    const first = startOfWeek(anchor, true)
    return Array.from({ length: 7 }, (_, index) => shiftDay(first, index))
  }
  return [anchor]
}
export function calendarBounds(anchor: string, view: CalendarView): { start: string; end: string } {
  const days = visibleDays(anchor, view)
  // The extra UTC day at each edge covers every IANA timezone without relying on
  // the browser's local timezone when requesting a calendar period.
  return {
    start: utcDay(shiftDay(days[0], -1)).toISOString(),
    end: utcDay(shiftDay(days[days.length - 1], 2)).toISOString(),
  }
}
function movePeriod(anchor: string, view: CalendarView, direction: number): string {
  if (view === 'month') {
    const day = Number(anchor.slice(8))
    const date = utcDay(`${anchor.slice(0, 7)}-01`)
    date.setUTCMonth(date.getUTCMonth() + direction)
    const lastDay = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).getUTCDate()
    date.setUTCDate(Math.min(day, lastDay))
    return keyFromUtcDay(date)
  }
  return shiftDay(anchor, direction * (view === 'week' ? 7 : 1))
}
export function useCalendarNavigation(timezone: string, initialView: CalendarView = 'month') {
  const [anchor, setAnchor] = useState(() => dateKey(new Date(), timezone))
  const [view, setView] = useState<CalendarView>(initialView)
  const [selectedDay, setSelectedDay] = useState(anchor)
  const navigate = (direction: number) => {
    const next = movePeriod(anchor, view, direction)
    setAnchor(next)
    setSelectedDay(next)
  }
  const today = () => {
    const next = dateKey(new Date(), timezone)
    setAnchor(next)
    setSelectedDay(next)
  }
  const selectDay = (day: string) => { setSelectedDay(day); setAnchor(day) }
  return { anchor, view, selectedDay, setView, navigate, today, selectDay }
}
export type CalendarNavigation = ReturnType<typeof useCalendarNavigation>

function dayLabel(key: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('en-US', { ...options, timeZone: 'UTC' }).format(utcDay(key))
}
function periodTitle(anchor: string, view: CalendarView): string {
  if (view === 'month') return dayLabel(anchor, { month: 'long', year: 'numeric' })
  if (view === 'day') return dayLabel(anchor, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
  const days = visibleDays(anchor, 'week')
  const first = days[0], last = days[6]
  const firstLabel = dayLabel(first, { month: 'short', day: 'numeric', ...(first.slice(0, 4) !== last.slice(0, 4) ? { year: 'numeric' } : {}) })
  const lastLabel = dayLabel(last, { month: 'short', day: 'numeric', year: 'numeric' })
  return `${firstLabel} – ${lastLabel}`
}
function timeLabel(value: string, timezone: string): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
function minutesInTimezone(value: string | Date, timezone: string): number {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(typeof value === 'string' ? new Date(value) : value)
  return Number(parts.find(part => part.type === 'hour')?.value ?? 0) * 60 + Number(parts.find(part => part.type === 'minute')?.value ?? 0)
}
function displayType(value?: string): string {
  return value === 'live_training' ? 'Live training' : value === 'consultation' ? 'Consultation' : 'Coaching session'
}
function blockedTitle(reason?: string): string {
  if (reason === 'VACATION') return 'Coach away'
  if (reason === 'NOTICE') return 'Booking notice required'
  if (reason === 'HORIZON') return 'Beyond booking window'
  return 'Blocked by coach'
}
type CalendarEntry = { key: string; slot?: CalendarSlot; booking?: CalendarBooking; starts_at: string; ends_at: string; state: 'available' | 'selected' | 'mine' | 'booked' | 'blocked' | 'past' | 'pending'; title: string }
function calendarEntries(slots: CalendarSlot[], bookings: CalendarBooking[], selectedSlot: CalendarSlot | null, isClient: boolean): CalendarEntry[] {
  const active = bookings.filter(booking => booking.status.toUpperCase() !== 'CANCELLED')
  const bookingBySlot = new Map(active.map(booking => [`${booking.coach_id ?? ''}:${booking.starts_at}`, booking]))
  const entries: CalendarEntry[] = slots.map(slot => {
    const booking = bookingBySlot.get(`${slot.coach_id}:${slot.starts_at}`) ?? bookingBySlot.get(`:${slot.starts_at}`)
    const booked = slot.status === 'BOOKED' || Boolean(booking)
    let state: CalendarEntry['state'] = 'available'
    if (booked && booking?.status.toUpperCase() === 'PENDING') state = 'pending'
    else if (booked) state = (isClient && (slot.booked_by_me || Boolean(booking))) ? 'mine' : 'booked'
    else if (slot.status === 'BLOCKED') state = 'blocked'
    else if (slot.status === 'PAST') state = 'past'
    else if (selectedSlot?.coach_id === slot.coach_id && selectedSlot.starts_at === slot.starts_at) state = 'selected'
    const title = state === 'mine' ? 'Your session' : state === 'booked' ? (booking?.client_name ?? 'Booked') : state === 'pending' ? 'Pending confirmation' : state === 'blocked' ? blockedTitle(slot.reason) : state === 'past' ? 'Past time' : slot.coach_name ? `Available · ${slot.coach_name}` : 'Available'
    return { key: `${slot.coach_id}:${slot.starts_at}`, slot, booking, starts_at: slot.starts_at, ends_at: slot.ends_at, state, title }
  })
  for (const booking of active) {
    if (entries.some(entry => entry.booking?.id === booking.id || (entry.starts_at === booking.starts_at && (!booking.coach_id || entry.slot?.coach_id === booking.coach_id)))) continue
    entries.push({ key: booking.id, booking, starts_at: booking.starts_at, ends_at: booking.ends_at ?? new Date(new Date(booking.starts_at).getTime() + 3_600_000).toISOString(), state: booking.status.toUpperCase() === 'PENDING' ? 'pending' : isClient ? 'mine' : 'booked', title: isClient ? 'Your session' : (booking.client_name ?? displayType(booking.type)) })
  }
  return entries.sort((a, b) => a.starts_at.localeCompare(b.starts_at))
}
function positionDayEntries(entries: CalendarEntry[]): { entry: CalendarEntry; column: number; columns: number }[] {
  const positioned: { entry: CalendarEntry; column: number; columns: number }[] = []
  let group: CalendarEntry[] = []
  let groupEnd = 0
  const finish = () => {
    if (!group.length) return
    const ends: number[] = []
    const placed = group.map(entry => {
      const start = new Date(entry.starts_at).getTime()
      const end = new Date(entry.ends_at).getTime()
      const reusable = ends.findIndex(value => value <= start)
      const column = reusable === -1 ? ends.length : reusable
      ends[column] = end
      return { entry, column }
    })
    positioned.push(...placed.map(item => ({ ...item, columns: ends.length })))
    group = []
  }
  for (const entry of entries) {
    const start = new Date(entry.starts_at).getTime()
    if (group.length && start >= groupEnd) finish()
    group.push(entry)
    groupEnd = Math.max(groupEnd, new Date(entry.ends_at).getTime())
  }
  finish()
  return positioned
}
function stateLabel(entry: CalendarEntry): string {
  if (entry.state === 'mine') return 'Booked by you'
  if (entry.state === 'booked') return 'Booked / unavailable'
  if (entry.state === 'blocked') return blockedTitle(entry.slot?.reason)
  if (entry.state === 'past') return 'Past time'
  if (entry.state === 'pending') return 'Pending confirmation'
  if (entry.state === 'selected') return 'Selected'
  return 'Available'
}

export function BookingCalendar({ navigation, slots, bookings, timezone, rules, selectedSlot = null, onSelectSlot, isClient = false }: {
  navigation: CalendarNavigation
  slots: CalendarSlot[]
  bookings: CalendarBooking[]
  timezone: string
  rules?: CalendarRules
  selectedSlot?: CalendarSlot | null
  onSelectSlot?: (slot: CalendarSlot) => void
  isClient?: boolean
}) {
  const entries = useMemo(() => calendarEntries(slots, bookings, selectedSlot, isClient), [slots, bookings, selectedSlot, isClient])
  const { anchor, view, selectedDay } = navigation
  const today = dateKey(new Date(), timezone)
  const month = monthDays(anchor)
  const visible = visibleDays(anchor, view)
  const entriesByDay = useMemo(() => {
    const grouped = new Map<string, CalendarEntry[]>()
    for (const entry of entries) {
      const day = dateKey(entry.starts_at, timezone)
      grouped.set(day, [...(grouped.get(day) ?? []), entry])
    }
    return grouped
  }, [entries, timezone])
  const byDay = (day: string) => entriesByDay.get(day) ?? []
  const hours = rules?.hours?.length ? rules.hours : []
  const eventHours = entries.filter(entry => visible.includes(dateKey(entry.starts_at, timezone))).map(entry => Math.floor(minutesInTimezone(entry.starts_at, timezone) / 60))
  const startHour = hours.length || eventHours.length ? Math.max(0, Math.min(...hours, ...eventHours) - 1) : 6
  const endHour = hours.length || eventHours.length ? Math.min(24, Math.max(...hours.map(hour => hour + Math.ceil((rules?.duration_minutes ?? 60) / 60)), ...eventHours.map(hour => hour + 1)) + 1) : 22
  const gridHeight = (endHour - startHour) * 56
  const currentMinutes = minutesInTimezone(new Date(), timezone)

  function entryNode(entry: CalendarEntry, compact = false) {
    const text = `${timeLabel(entry.starts_at, timezone)}–${timeLabel(entry.ends_at, timezone)} ${entry.title}. ${stateLabel(entry)}`
    const content = <><span className="booking-event-time">{timeLabel(entry.starts_at, timezone)}–{timeLabel(entry.ends_at, timezone)}</span><strong>{compact ? stateLabel(entry) : entry.title}</strong>{!compact && <small>{stateLabel(entry)}</small>}</>
    return entry.slot && (entry.state === 'available' || entry.state === 'selected') && onSelectSlot
      ? <button type="button" key={entry.key} className={`booking-calendar-event state-${entry.state}`} aria-label={`${text}. Select time`} onClick={() => onSelectSlot(entry.slot!)}>{content}</button>
      : <div key={entry.key} className={`booking-calendar-event state-${entry.state}`} aria-label={text}>{content}</div>
  }

  return <section className={`booking-calendar calendar-view-${view}`} aria-label="Booking calendar">
    <div className="booking-calendar-toolbar">
      <div className="booking-calendar-navigation">
        <button type="button" aria-label="Previous period" onClick={() => navigation.navigate(-1)}><ChevronLeft size={17} /></button>
        <button type="button" onClick={navigation.today}>Today</button>
        <button type="button" aria-label="Next period" onClick={() => navigation.navigate(1)}><ChevronRight size={17} /></button>
      </div>
      <h2 aria-live="polite">{periodTitle(anchor, view)}</h2>
      <div className="booking-calendar-views" aria-label="Calendar view">
        {(['month', 'week', 'day'] as const).map(option => <button type="button" key={option} className={view === option ? 'active' : ''} aria-pressed={view === option} onClick={() => navigation.setView(option)}>{option[0].toUpperCase() + option.slice(1)}</button>)}
      </div>
    </div>
    <p className="booking-calendar-timezone">Times shown in <strong>{timezone.replaceAll('_', ' ')}</strong></p>
    <div className="booking-calendar-legend" aria-label="Calendar status key"><span className="state-available">Available</span><span className="state-mine">Booked by you</span><span className="state-booked">Booked / unavailable</span><span className="state-blocked">Blocked by coach</span><span className="state-past">Past time</span></div>
    <div className="booking-month" role="grid" aria-label={`${dayLabel(anchor, { month: 'long', year: 'numeric' })} month calendar`}>
      <div className="booking-month-weekdays" role="row">{['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(name => <span role="columnheader" key={name}>{name}</span>)}</div>
      <div className="booking-month-days">{Array.from({ length: 6 }, (_, week) => <div className="booking-month-row" role="row" key={week}>{month.slice(week * 7, week * 7 + 7).map(day => {
        const dayEntries = byDay(day)
        const available = dayEntries.filter(entry => entry.state === 'available' || entry.state === 'selected').length
        const booked = dayEntries.filter(entry => entry.state === 'booked' || entry.state === 'mine').length
        const blocked = dayEntries.filter(entry => entry.state === 'blocked').length
        const description = `${dayLabel(day, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}; ${available} available, ${booked} booked${blocked ? `, ${blocked} blocked` : ''}`
        return <button type="button" role="gridcell" key={day} className={`booking-month-day${day.slice(0, 7) !== anchor.slice(0, 7) ? ' outside' : ''}${day === today ? ' today' : ''}${day === selectedDay ? ' selected' : ''}${dayEntries.length ? ' has-sessions' : ''}`} aria-label={description} aria-selected={day === selectedDay} onClick={() => navigation.selectDay(day)}>
          <span className="booking-day-number">{Number(day.slice(8))}{day === today && <small>Today</small>}</span>
          <span className="booking-day-events">{dayEntries.slice(0, 2).map(entry => <span className={`booking-day-chip state-${entry.state}`} key={entry.key}>{timeLabel(entry.starts_at, timezone)} {entry.state === 'available' ? 'Available' : entry.state === 'mine' ? 'Yours' : entry.state === 'booked' ? 'Booked' : entry.state === 'blocked' ? 'Blocked' : 'Past'}</span>)}{dayEntries.length > 2 && <span className="booking-day-more">+{dayEntries.length - 2} more</span>}</span>
          <span className="booking-day-count">{dayEntries.length ? `${available} open · ${booked} booked` : 'No sessions'}</span>
        </button>
      })}</div>)}</div>
    </div>
    {view !== 'month' && <div className={`booking-time-grid booking-time-grid-${view}`} aria-label={`${view} time grid`}>
      <div className="booking-time-head"><span>Time</span>{visible.map(day => <strong className={day === today ? 'today' : ''} key={day}>{dayLabel(day, { weekday: 'short', month: 'short', day: 'numeric' })}</strong>)}</div>
      <div className="booking-time-body">
        <div className="booking-time-axis" style={{ height: gridHeight }}>{Array.from({ length: endHour - startHour + 1 }, (_, index) => <span key={index} style={{ top: index * 56 }}>{String(startHour + index).padStart(2, '0')}:00</span>)}</div>
        {visible.map(day => <div className={`booking-time-day${day === today ? ' today' : ''}`} key={day} style={{ height: gridHeight }} aria-label={dayLabel(day, { weekday: 'long', month: 'long', day: 'numeric' })}>
          {Array.from({ length: endHour - startHour + 1 }, (_, index) => <span className="booking-hour-line" key={index} style={{ top: index * 56 }} />)}
          {positionDayEntries(byDay(day)).map(({ entry, column, columns }) => {
            const start = minutesInTimezone(entry.starts_at, timezone)
            const duration = Math.max(30, (new Date(entry.ends_at).getTime() - new Date(entry.starts_at).getTime()) / 60000)
            return <div className="booking-time-position" key={entry.key} style={{ top: Math.max(0, (start - startHour * 60) * 56 / 60), height: Math.max(30, duration * 56 / 60), left: `calc(${column * 100 / columns}% + 3px)`, width: `calc(${100 / columns}% - 6px)` }}>{entryNode(entry)}</div>
          })}
          {day === today && currentMinutes >= startHour * 60 && currentMinutes <= endHour * 60 && <div className="booking-current-time" style={{ top: (currentMinutes - startHour * 60) * 56 / 60 }}><span>Now</span></div>}
        </div>)}
      </div>
    </div>}
    <div className="booking-day-agenda">
      <div className="booking-agenda-heading"><h3>{dayLabel(selectedDay, { weekday: 'long', month: 'long', day: 'numeric' })}</h3><span>{byDay(selectedDay).length} session times</span></div>
      {byDay(selectedDay).length ? <div className="booking-agenda-list">{byDay(selectedDay).map(entry => entryNode(entry, true))}</div> : <p className="booking-agenda-empty">No published session times on this day.</p>}
    </div>
  </section>
}
