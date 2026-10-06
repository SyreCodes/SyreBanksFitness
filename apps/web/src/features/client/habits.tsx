import { Check, Plus } from 'lucide-react'
import { clientCopy } from './clientCopy'
import { ClientCard, ClientEmpty, ClientError, ClientHeader, ClientLoading, ClientNotice, SectionHeading } from './common'
import { clientKeys, useClientMutation, useClientQuery } from './data'
import type { Habit, HabitLog, Page } from './types'
import { localDate } from './validation'

export function DailyHabits({ compact = false }: { compact?: boolean }) {
  const habits = useClientQuery<Page<Habit>>(clientKeys.habits, '/habits')
  const logs = useClientQuery<Page<HabitLog>>(clientKeys.habitLogs, '/habits/logs')
  const log = useClientMutation<{ id: string; completed: boolean }, HabitLog>(input => `/habits/${input.id}/log`, { body: input => ({ date: localDate(), completed: input.completed }), keys: [clientKeys.habitLogs] })
  if (habits.isPending || logs.isPending) return <ClientLoading />
  if (habits.isError || logs.isError) return <ClientError error={habits.error ?? logs.error} retry={() => { void habits.refetch(); void logs.refetch() }} />
  if (!habits.data.items.length) return <ClientEmpty title="Your habits start here." description="Your coach will assign daily habits to support your goals." />
  const today = logs.data.items.filter(item => item.date === localDate())
  const complete = habits.data.items.filter(habit => today.some(item => item.habit_id === habit.id && item.completed)).length
  const displayed = compact ? habits.data.items.slice(0, 4) : habits.data.items
  return <><div className="client-habit-list">{displayed.map(habit => {
    const completed = today.some(item => item.habit_id === habit.id && item.completed)
    return <div className="client-habit-row" key={habit.id}><button className={`client-check ${completed ? 'checked' : ''}`} aria-label={`${completed ? 'Mark incomplete' : 'Complete'}: ${habit.name}`} aria-pressed={completed} disabled={log.isPending} onClick={() => log.mutate({ id: habit.id, completed: !completed })}>{completed ? <Check size={15} /> : <Plus size={13} />}</button><div className={completed ? 'done' : ''}><h3>{habit.name}</h3><p>{habit.description || 'Your daily commitment'}</p></div></div>
  })}</div><div className="client-habit-progress"><div className="client-progress-track"><span style={{ width: `${complete / habits.data.items.length * 100}%` }} /></div><span>{complete} of {habits.data.items.length} complete</span></div>{log.isError && <ClientNotice danger>{log.error.message}</ClientNotice>}</>
}

export function HabitsPage() { return <><ClientHeader {...clientCopy.habits} /><ClientCard><SectionHeading title="Today’s habits" detail={new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })} /><DailyHabits /></ClientCard></> }
