import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQuery } from '@tanstack/react-query'
import { CalendarDays, Check, MessageCircle, Send } from 'lucide-react'
import { BookingCalendar, calendarBounds, useCalendarNavigation, type CalendarAvailability, type CalendarSlot } from '../../components/BookingCalendar'
import { Modal } from '../../components/ui'
import { api, ApiError } from '../../services/api'
import { bookingsInRange } from '../../services/bookings'
import { useAuth } from '../../services/auth'
import { clientCopy } from './clientCopy'
import { ClientCard, ClientEmpty, ClientError, ClientHeader, ClientLoading, ClientNotice, FieldLabel, formatDate, formatDateTime, SectionHeading } from './common'
import { clientKeys, useClientMutation, useClientQuery } from './data'
import type { Booking, Checkin, Contact, Message, Page } from './types'

const checkinSchema = z.object({
  energy: z.number().int().min(1).max(5), sleep: z.number().int().min(1).max(5), adherence: z.number().int().min(1).max(5),
  weight_kg: z.number().finite().min(20).max(400).optional(),
  wins: z.string().max(3000), challenges: z.string().max(3000), notes: z.string().max(3000),
})
type CheckinForm = z.infer<typeof checkinSchema>

export function CheckinsPage() {
  const history = useClientQuery<Page<Checkin>>(clientKeys.checkins, '/checkins')
  const save = useClientMutation<{ answers: Omit<CheckinForm, 'notes'>; notes: string }, Checkin>('/checkins', { keys: [clientKeys.checkins] })
  const form = useForm<CheckinForm>({ resolver: zodResolver(checkinSchema), defaultValues: { energy: 3, sleep: 3, adherence: 3, wins: '', challenges: '', notes: '' } })
  return <><ClientHeader {...clientCopy.checkins} /><div className="client-grid"><ClientCard><SectionHeading title="How has your week been?" detail="A few honest answers help your coach support you." /><form className="client-form" onSubmit={form.handleSubmit(({ notes, ...answers }) => save.mutate({ answers, notes }, { onSuccess: () => form.reset() }))}><div className="client-form-grid">{(['energy', 'sleep', 'adherence'] as const).map(name => <FieldLabel key={name} title={name === 'energy' ? 'Energy levels' : name === 'sleep' ? 'Sleep quality' : 'Following your plan'}><select {...form.register(name, { valueAsNumber: true })} aria-label={name}>{[1, 2, 3, 4, 5].map(value => <option value={value} key={value}>{value} / 5 — {['Very low', 'Low', 'Okay', 'Good', 'Excellent'][value - 1]}</option>)}</select></FieldLabel>)}<FieldLabel title="Current weight (optional, kg)"><input type="number" inputMode="decimal" step="0.1" min="20" max="400" {...form.register('weight_kg', { setValueAs: (value: string) => value === '' ? undefined : Number(value) })} /></FieldLabel></div>{form.formState.errors.weight_kg && <p className="client-form-error" role="alert">Enter a weight between 20 and 400 kg, or leave it blank.</p>}<FieldLabel title="What went well?"><textarea {...form.register('wins')} placeholder="A workout you enjoyed, a habit that stuck, a small win…" maxLength={3000} /></FieldLabel><FieldLabel title="What was challenging?"><textarea {...form.register('challenges')} placeholder="Energy, schedule, an exercise, or something else…" maxLength={3000} /></FieldLabel><FieldLabel title="Anything else your coach should know?"><textarea {...form.register('notes')} placeholder="Questions, concerns, or support you need." maxLength={3000} /></FieldLabel>{save.isError && <ClientNotice danger>{save.error.message}</ClientNotice>}{save.isSuccess && <ClientNotice>Your check-in is saved and ready for your coach to review.</ClientNotice>}<button className="client-button" disabled={save.isPending} type="submit">{save.isPending ? 'Submitting…' : 'Send check-in'}<Send size={15} /></button></form></ClientCard><ClientCard><SectionHeading title="Your check-in history" />{history.isPending ? <ClientLoading /> : history.isError ? <ClientError error={history.error} retry={() => { void history.refetch() }} /> : !history.data.items.length ? <ClientEmpty title="Your first check-in makes a difference." description="Share your week and your coach can help you move forward." /> : history.data.items.map(item => <div className="client-list-row" key={item.id}><div><h3>Check-in · {formatDate(item.created_at)}</h3><p>Energy {String(item.answers.energy ?? '—')}/5 · Sleep {String(item.answers.sleep ?? '—')}/5</p>{typeof item.answers.wins === 'string' && item.answers.wins && <p style={{ marginTop: 7 }}>Your wins: {item.answers.wins}</p>}{item.coach_feedback && <ClientNotice><strong>Coach’s feedback</strong><br />{item.coach_feedback}</ClientNotice>}</div><span className={`client-status ${item.status === 'REVIEWED' ? 'completed' : ''}`}>{item.status === 'REVIEWED' ? 'Reviewed' : 'Submitted'}</span></div>)}</ClientCard></div></>
}

export function MessagesPage() {
  const { user } = useAuth()
  const contacts = useClientQuery<Page<Contact>>(['client', 'contacts'], '/messages/contacts')
  const messages = useClientQuery<Page<Message>>(clientKeys.messages, '/messages')
  const [selected, setSelected] = useState('')
  const recipient = selected || contacts.data?.items[0]?.id || ''
  const form = useForm<{ body: string }>({ defaultValues: { body: '' } })
  const send = useClientMutation<{ recipient_id: string; body: string }, Message>('/messages', { keys: [clientKeys.messages] })
  const conversation = messages.data?.items.filter(item => item.sender_id === recipient || item.recipient_id === recipient).sort((a, b) => a.created_at.localeCompare(b.created_at)) ?? []
  const contact = contacts.data?.items.find(item => item.id === recipient)
  return <><ClientHeader {...clientCopy.messages} /><ClientCard>{contacts.isPending || messages.isPending ? <ClientLoading /> : contacts.isError || messages.isError ? <ClientError error={contacts.error ?? messages.error} retry={() => { void contacts.refetch(); void messages.refetch() }} /> : !contacts.data.items.length ? <ClientEmpty title="Your coach will be here soon." description="Messaging becomes available when a coach is assigned to you. Complete your assessment to get started." /> : <><div className="client-section-heading"><div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><span className="client-inline-icon"><MessageCircle size={21} /></span><div><h2>{contact?.name || 'Your coach'}</h2><p>Your private coaching conversation</p></div></div>{contacts.data.items.length > 1 && <label className="client-field"><span>Conversation</span><select value={recipient} onChange={event => setSelected(event.target.value)}>{contacts.data.items.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>}</div><div className="client-message-list" aria-label="Message history">{!conversation.length ? <ClientEmpty title="Start a conversation." description="Your coach is here to help. Share a question or a quick update." /> : conversation.map(message => <div className={`client-message ${message.sender_id === user?.id ? 'mine' : ''}`} key={message.id}><p>{message.body}</p><small>{message.sender_id === user?.id ? 'You' : contact?.name} · {formatDateTime(message.created_at)}</small></div>)}</div><form className="client-compose" onSubmit={form.handleSubmit(values => send.mutate({ recipient_id: recipient, body: values.body.trim() }, { onSuccess: () => form.reset() }))}><FieldLabel title="Your message"><textarea {...form.register('body', { required: 'Write a message first.', maxLength: { value: 5000, message: 'Keep your message below 5,000 characters.' }, validate: value => Boolean(value.trim()) || 'Write a message first.' })} placeholder="Write to your coach…" maxLength={5000} /></FieldLabel><button type="submit" className="client-button" disabled={send.isPending || !recipient}>{send.isPending ? 'Sending…' : 'Send message'}<Send size={15} /></button></form>{form.formState.errors.body && <p className="client-form-error" role="alert">{form.formState.errors.body.message}</p>}{send.isError && <ClientNotice danger>{send.error.message}</ClientNotice>}</>}</ClientCard></>
}

type BookInput = { coach_id: string; starts_at: string; ends_at: string; type: 'consultation' | 'live_training'; notes?: string }
export function BookingsPage() {
  const { user } = useAuth()
  const timezone = user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'Africa/Kigali'
  const navigation = useCalendarNavigation(timezone)
  const range = calendarBounds(navigation.anchor, navigation.view)
  const bounds = `start=${encodeURIComponent(range.start)}&end=${encodeURIComponent(range.end)}`
  const availability = useQuery<CalendarAvailability>({
    queryKey: [...clientKeys.availability, range.start, range.end],
    queryFn: () => api(`/bookings/availability?${bounds}&include_unavailable=true`),
    staleTime: 60_000,
  })
  const bookings = useQuery<Page<Booking>>({
    queryKey: [...clientKeys.bookings, range.start, range.end],
    queryFn: () => bookingsInRange<Booking>(range.start, range.end),
    staleTime: 30_000,
  })
  const [selected, setSelected] = useState<CalendarSlot | null>(null)
  const [type, setType] = useState<'consultation' | 'live_training'>('consultation')
  const [notes, setNotes] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const book = useClientMutation<BookInput, Booking>('/bookings', { keys: [clientKeys.bookings, clientKeys.availability] })
  const cancel = useClientMutation<string, Booking>(id => `/bookings/${id}`, { method: 'PATCH', body: () => ({ status: 'CANCELLED' }), keys: [clientKeys.bookings, clientKeys.availability] })
  const slotDate = selected ? new Intl.DateTimeFormat('en-US', { timeZone: timezone, weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' }).format(new Date(selected.starts_at)) : ''
  const slotTime = (value: string) => new Intl.DateTimeFormat('en-GB', { timeZone: timezone, hour: '2-digit', minute: '2-digit' }).format(new Date(value))
  const conflict = book.error instanceof ApiError && ['BOOKING_CONFLICT', 'SLOT_NO_LONGER_AVAILABLE'].includes(book.error.code ?? '')
  return <>
    <ClientHeader {...clientCopy.bookings} />
    {confirmation && <ClientNotice><Check size={14} />{confirmation}</ClientNotice>}
    {availability.isPending || bookings.isPending ? <ClientCard><ClientLoading /></ClientCard> : availability.isError || bookings.isError ? <ClientCard><ClientError error={availability.error ?? bookings.error} retry={() => { void availability.refetch(); void bookings.refetch() }} /></ClientCard> : <>
      <BookingCalendar navigation={navigation} slots={availability.data.items} bookings={bookings.data.items} timezone={timezone} rules={availability.data.rules} selectedSlot={selected} isClient onSelectSlot={slot => { setSelected(slot); setConfirmation(''); book.reset() }} />
      <ClientCard className="client-bookings-list"><SectionHeading title="Your sessions this period" detail="Booked and cancelled sessions remain in your history." />{!bookings.data.items.length ? <ClientEmpty title="Your calendar is clear." description="Choose an available time above to schedule a session." /> : bookings.data.items.map(item => <div className="client-session" key={item.id}><div className="client-date-tile"><span>{new Date(item.starts_at).toLocaleDateString(undefined, { month: 'short', timeZone: timezone })}</span><strong>{new Date(item.starts_at).toLocaleDateString(undefined, { day: 'numeric', timeZone: timezone })}</strong></div><div><h3>{item.status.toUpperCase() === 'CANCELLED' ? 'Cancelled session' : 'Coaching session'}</h3><p>{new Date(item.starts_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZone: timezone, timeZoneName: 'short' })}</p>{item.notes && <p>{item.notes}</p>}{item.meeting_url && <a href={item.meeting_url} target="_blank" rel="noreferrer" className="client-button secondary small" style={{ marginTop: 10 }}>Join session</a>}{item.status.toUpperCase() !== 'CANCELLED' && new Date(item.starts_at) > new Date() && <button className="client-button secondary small" style={{ marginTop: 10 }} disabled={cancel.isPending} onClick={() => cancel.mutate(item.id, { onSuccess: () => setConfirmation('Session cancelled.') })}>Cancel session</button>}</div><span className={`client-status ${item.status.toLowerCase()}`}>{item.status}</span></div>)}{cancel.isError && <ClientNotice danger>{cancel.error.message}</ClientNotice>}</ClientCard>
    </>}
    {selected && <Modal title="Book session" onClose={() => { setSelected(null); book.reset() }}><form className="client-form booking-confirmation" onSubmit={event => { event.preventDefault(); book.mutate({ coach_id: selected.coach_id, starts_at: selected.starts_at, ends_at: selected.ends_at, type, notes }, { onSuccess: () => { setSelected(null); setNotes(''); setConfirmation('Session booked successfully. Your calendar is up to date.') }, onError: () => { void availability.refetch(); void bookings.refetch() } }) }}>
      <FieldLabel title="Session type"><select value={type} onChange={event => setType(event.target.value as typeof type)}><option value="consultation">Coaching consultation</option><option value="live_training">Live training</option></select></FieldLabel>
      <dl className="booking-confirmation-details"><div><dt>Coach</dt><dd>{selected.coach_name ?? 'Your coach'}</dd></div><div><dt>Date</dt><dd>{slotDate}</dd></div><div><dt>Start time</dt><dd>{slotTime(selected.starts_at)}</dd></div><div><dt>End time</dt><dd>{slotTime(selected.ends_at)}</dd></div><div><dt>Duration</dt><dd>{Math.round((new Date(selected.ends_at).getTime() - new Date(selected.starts_at).getTime()) / 60000)} minutes</dd></div><div><dt>Timezone</dt><dd>{timezone.replaceAll('_', ' ')}</dd></div><div><dt>Meeting method</dt><dd>Your coach will confirm the details</dd></div></dl>
      <FieldLabel title="What would you like to focus on? (optional)"><textarea value={notes} onChange={event => setNotes(event.target.value)} maxLength={3000} /></FieldLabel>
      {book.isError && <ClientNotice danger>{conflict ? 'This slot is no longer available. Choose another time from the updated calendar.' : book.error.message}</ClientNotice>}
      <div className="client-form-actions"><button className="client-button" disabled={book.isPending || conflict} type="submit">{book.isPending ? 'Booking…' : 'Book session'}<CalendarDays size={16} /></button><button type="button" className="client-button secondary" onClick={() => { setSelected(null); book.reset() }}>{conflict ? 'Choose another time' : 'Cancel'}</button></div>
    </form></Modal>}
  </>
}
