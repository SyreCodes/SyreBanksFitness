import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CalendarDays, Plus } from 'lucide-react'
import { BookingCalendar, calendarBounds, useCalendarNavigation, type CalendarAvailability, type CalendarSlot } from '../../components/BookingCalendar'
import { Button, ErrorState, Field, Loading, Modal, PageHeader } from '../../components/ui'
import { api, ApiError } from '../../services/api'
import { bookingsInRange } from '../../services/bookings'
import { useAuth } from '../../services/auth'
import type { Booking, Client } from './types'
import { useList, useToast } from './shared'

export function Calendar() {
  const { user } = useAuth()
  const timezone = user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'Africa/Kigali'
  const navigation = useCalendarNavigation(timezone)
  const range = calendarBounds(navigation.anchor, navigation.view)
  const bounds = `start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}`
  const availability = useQuery<CalendarAvailability>({
    queryKey: ['bookings', 'availability', range.start, range.end],
    queryFn: () => api(`/bookings/availability?${bounds}&include_unavailable=true`),
    staleTime: 60_000,
  })
  const bookings = useQuery<{ items: Booking[]; total: number }>({
    queryKey: ['bookings', 'calendar', range.start, range.end],
    queryFn: () => bookingsInRange<Booking>(range.start, range.end),
    staleTime: 30_000,
  })
  const [selectedSlot, setSelectedSlot] = useState<CalendarSlot | null | undefined>(undefined)
  return <>
    <PageHeader title="Make time for progress." subtitle="Sessions and consultations in one calendar. Times are shown in your account timezone." eyebrow="Calendar" actions={<Button onClick={() => setSelectedSlot(null)}><Plus size={17} />Schedule session</Button>} />
    {availability.isPending || bookings.isPending ? <Loading label="Loading your calendar…" /> : availability.isError || bookings.isError ? <ErrorState error={availability.error ?? bookings.error} retry={() => { void availability.refetch(); void bookings.refetch() }} /> : <>
      <BookingCalendar navigation={navigation} slots={availability.data.items} bookings={bookings.data.items} timezone={timezone} rules={availability.data.rules} selectedSlot={selectedSlot} onSelectSlot={setSelectedSlot} />
      <div className="notice" style={{ marginTop: 18 }}><CalendarDays size={17} /><span>Choose an available time to schedule a session. Meeting details are shared by your coach when arranged.</span></div>
    </>}
    {selectedSlot !== undefined && <BookingCreate initialSlot={selectedSlot} slots={availability.data?.items ?? []} timezone={timezone} onClose={() => setSelectedSlot(undefined)} onRefresh={() => { void availability.refetch(); void bookings.refetch() }} />}
  </>
}

function BookingCreate({ initialSlot, slots, timezone, onClose, onRefresh }: {
  initialSlot: CalendarSlot | null
  slots: CalendarSlot[]
  timezone: string
  onClose: () => void
  onRefresh: () => void
}) {
  const clients = useList<Client>('/clients', 'clients')
  const queryClient = useQueryClient()
  const toast = useToast()
  const [type, setType] = useState<'consultation' | 'live_training'>('consultation')
  const slotKey = (item: CalendarSlot) => `${item.coach_id}|${item.starts_at}`
  const [selectedKey, setSelectedKey] = useState(initialSlot ? slotKey(initialSlot) : '')
  const openSlots = slots.filter(item => !item.status || item.status === 'AVAILABLE')
  const slot = openSlots.find(item => slotKey(item) === selectedKey) ?? null
  const showDate = (value: string) => new Intl.DateTimeFormat('en-US', { timeZone: timezone, weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
  const mutation = useMutation({
    mutationFn: (values: { client_id: string; coach_id: string; starts_at: string; ends_at: string; type: string }) => api('/bookings', { method: 'POST', body: JSON.stringify(values) }),
    onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['bookings'] }); void queryClient.invalidateQueries({ queryKey: ['admin-dashboard'] }); toast('Session booked successfully.'); onClose() },
    onError: onRefresh,
  })
  const conflict = mutation.error instanceof ApiError && ['BOOKING_CONFLICT', 'SLOT_NO_LONGER_AVAILABLE'].includes(mutation.error.code ?? '')
  return <Modal title="Schedule a coaching session" onClose={onClose}><form onSubmit={event => {
    event.preventDefault()
    if (!slot) return
    const values = Object.fromEntries(new FormData(event.currentTarget).entries())
    mutation.mutate({ client_id: String(values.client_id), coach_id: slot.coach_id, starts_at: slot.starts_at, ends_at: slot.ends_at, type })
  }}>
    <Field label="Client"><select name="client_id" required><option value="">Select client</option>{clients.data?.items.map(client => <option key={client.id} value={client.id}>{client.name}</option>)}</select></Field>
    {clients.isError && <div className="form-error" role="alert">Clients could not be loaded. <Button type="button" variant="secondary" onClick={() => { void clients.refetch() }}>Try again</Button></div>}
    <Field label="Available time"><select aria-label="Available time" required value={slot ? selectedKey : ''} onChange={event => { setSelectedKey(event.target.value); mutation.reset() }}><option value="">Select an available time</option>{openSlots.map(item => <option key={slotKey(item)} value={slotKey(item)}>{showDate(item.starts_at)} · {item.coach_name ?? 'Coach'}</option>)}</select></Field>
    {!openSlots.length && <p className="account-note">No open time appears in this period. Navigate to another date and choose an available slot.</p>}
    <Field label="Session type"><select value={type} onChange={event => setType(event.target.value as typeof type)}><option value="consultation">Coaching consultation</option><option value="live_training">Live training</option></select></Field>
    {slot && <dl className="booking-confirmation-details"><div><dt>Coach</dt><dd>{slot.coach_name ?? 'Coach'}</dd></div><div><dt>Start</dt><dd>{showDate(slot.starts_at)}</dd></div><div><dt>End</dt><dd>{showDate(slot.ends_at)}</dd></div><div><dt>Duration</dt><dd>{Math.round((new Date(slot.ends_at).getTime() - new Date(slot.starts_at).getTime()) / 60000)} minutes</dd></div><div><dt>Timezone</dt><dd>{timezone.replaceAll('_', ' ')}</dd></div><div><dt>Meeting method</dt><dd>Arranged with the client</dd></div></dl>}
    {mutation.isError && <div className="form-error" role="alert">{conflict ? 'This slot is no longer available. Choose another time from the updated calendar.' : mutation.error.message}</div>}
    <div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={mutation.isPending || !slot || clients.isPending || clients.isError}>{mutation.isPending ? 'Booking…' : 'Book session'}</Button></div>
  </form></Modal>
}
