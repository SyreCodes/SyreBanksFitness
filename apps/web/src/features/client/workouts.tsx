import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Check, Clock3, Dumbbell, Pause, Play, RotateCcw, Timer, Trophy } from 'lucide-react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../../services/auth'
import { api } from '../../services/api'
import { ExerciseDemonstration } from '../public/ExerciseDemonstration'
import { clientCopy } from './clientCopy'
import { ClientCard, ClientEmpty, ClientError, ClientHeader, ClientLoading, ClientNotice, formatDate, SectionHeading } from './common'
import { clientKeys, useClientMutation, useClientQuery } from './data'
import type { Assignment, Page, Prescription, Workout, WorkoutSession } from './types'
import { makeLoggedSet } from './validation'
import type { LoggedSet } from './validation'

type SetValue = LoggedSet & { completed: true }
type WorkoutPayload = { assignment_id: string; workout_id: string; notes?: string; duration_minutes: number; sets: SetValue[]; completed: true }
type ExerciseDemo = { id: string; video_url?: string; video_media_id?: string | null }

async function loadExerciseDemonstrations(exerciseIds: string[]): Promise<Record<string, ExerciseDemo>> {
  const needed = new Set(exerciseIds)
  const found: Record<string, ExerciseDemo> = {}
  let offset = 0
  while (needed.size) {
    const page = await api<Page<ExerciseDemo>>(`/exercises?limit=100&offset=${offset}`)
    for (const exercise of page.items) if (needed.delete(exercise.id)) found[exercise.id] = exercise
    offset += page.items.length
    if (!page.items.length || offset >= page.total) break
  }
  return found
}

function RestTimer({ seconds, running, onPause, onReset }: { seconds: number; running: boolean; onPause: () => void; onReset: () => void }) {
  return <div className="client-timer" role="timer" aria-label="Rest timer"><Timer size={21} /><div><strong>{String(Math.floor(seconds / 60)).padStart(2, '0')}:{String(seconds % 60).padStart(2, '0')}</strong><p>{seconds === 0 ? 'Ready for your next set' : 'Take your rest'}</p></div><button className="client-button secondary small" onClick={onPause} aria-label={running ? 'Pause timer' : 'Resume timer'}>{running ? <Pause size={14} /> : <Play size={14} />}</button><button className="client-button secondary small" style={{ marginLeft: 0 }} onClick={onReset} aria-label="Reset rest timer"><RotateCcw size={14} /></button></div>
}

function SetRow({ exercise, number, saved, onLog }: { exercise: Prescription; number: number; saved?: SetValue; onLog: (set?: SetValue) => void }) {
  const [reps, setReps] = useState(saved?.reps.toString() ?? '')
  const [weight, setWeight] = useState(saved?.weight_kg.toString() ?? exercise.weight_kg?.toString() ?? '0')
  const [rpe, setRpe] = useState(saved?.rpe?.toString() ?? '')
  const [error, setError] = useState('')
  function update(field: 'reps' | 'weight' | 'rpe', value: string) { if (saved) onLog(); if (field === 'reps') setReps(value); if (field === 'weight') setWeight(value); if (field === 'rpe') setRpe(value); setError('') }
  function toggle() {
    if (saved) { onLog(); return }
    try { onLog({ ...makeLoggedSet(exercise.exercise_id, number, { reps, weight_kg: weight, rpe }), completed: true }); setError('') }
    catch { setError('Enter reps (1–200), weight (0–1000 kg), and optional RPE (1–10).') }
  }
  return <><div className="client-set-row"><span>{number}</span><input className="client-set-input" aria-label={`${exercise.name} set ${number} repetitions`} inputMode="numeric" type="number" min="1" max="200" value={reps} placeholder={exercise.reps} onChange={event => update('reps', event.target.value)} /><input className="client-set-input" aria-label={`${exercise.name} set ${number} weight in kg`} inputMode="decimal" type="number" step="0.5" min="0" max="1000" value={weight} onChange={event => update('weight', event.target.value)} /><input className="client-set-input" aria-label={`${exercise.name} set ${number} RPE`} inputMode="decimal" type="number" step="0.5" min="1" max="10" value={rpe} placeholder="—" onChange={event => update('rpe', event.target.value)} /><button className={`client-check ${saved ? 'checked' : ''}`} aria-label={`${saved ? 'Unmark' : 'Log'} ${exercise.name} set ${number}`} aria-pressed={Boolean(saved)} onClick={toggle}><Check size={18} /></button></div>{error && <p className="client-form-error" role="alert">{error}</p>}</>
}

function WorkoutLogger({ assignment, workout, onClose }: { assignment: Assignment; workout: Workout; onClose: () => void }) {
  const { user } = useAuth()
  const exerciseIds = workout.exercises.map(exercise => exercise.exercise_id)
  const demonstrations = useQuery({
    queryKey: ['client', 'exercise-demonstrations', ...[...exerciseIds].sort()],
    queryFn: () => loadExerciseDemonstrations(exerciseIds),
    enabled: exerciseIds.length > 0,
  })
  const storageKey = `sbf:workout:${user?.id}:${assignment.id}:${workout.id}`
  const [sets, setSets] = useState<Record<string, SetValue>>(() => { try { return JSON.parse(sessionStorage.getItem(storageKey) ?? '{}') as Record<string, SetValue> } catch { return {} } })
  const [notes, setNotes] = useState('')
  const [startedAt] = useState(() => Date.now())
  const [rest, setRest] = useState(0)
  const [restDefault, setRestDefault] = useState(60)
  const [running, setRunning] = useState(false)
  const save = useClientMutation<WorkoutPayload, WorkoutSession>('/workouts/sessions', { keys: [clientKeys.sessions] })
  useEffect(() => { sessionStorage.setItem(storageKey, JSON.stringify(sets)) }, [sets, storageKey])
  useEffect(() => { if (!running || rest <= 0) return; const interval = window.setInterval(() => setRest(value => Math.max(0, value - 1)), 1000); return () => window.clearInterval(interval) }, [running, rest])
  function logSet(exercise: Prescription, number: number, set?: SetValue) {
    const key = `${exercise.exercise_id}:${number}`
    setSets(current => { const next = { ...current }; if (set) next[key] = set; else delete next[key]; return next })
    if (set) { const duration = exercise.rest_seconds ?? 60; setRestDefault(duration); setRest(duration); setRunning(true) }
  }
  function finish() { save.mutate({ assignment_id: assignment.id, workout_id: workout.id, sets: Object.values(sets), completed: true, notes, duration_minutes: Math.max(1, Math.round((Date.now() - startedAt) / 60000)) }, { onSuccess: () => { sessionStorage.removeItem(storageKey); setSets({}) } }) }
  if (save.isSuccess) return <ClientCard><ClientEmpty title="Session complete. Good work." description="Your workout and logged sets are saved. Your coach can review your results." action={<button className="client-button" onClick={onClose}><Trophy size={17} />Back to your plan</button>} /></ClientCard>
  const prescribed = workout.exercises.reduce((total, exercise) => total + exercise.sets, 0)
  return <ClientCard><SectionHeading title={workout.name} detail={`${assignment.snapshot.name} · ${Object.keys(sets).length} / ${prescribed} sets logged`} /><ClientNotice>Check off each set after you perform it. Your checked sets are saved to your coach when you finish this session.</ClientNotice><RestTimer seconds={rest} running={running && rest > 0} onPause={() => setRunning(value => !value)} onReset={() => { setRest(restDefault); setRunning(true) }} />{workout.exercises.map(exercise => {
    const demonstration = demonstrations.data?.[exercise.exercise_id]
    const videoUrl = demonstration?.video_url || exercise.video_url
    const videoMediaId = demonstration?.video_media_id || exercise.video_media_id
    return <div className="client-exercise" key={exercise.exercise_id}><div className="client-exercise-heading"><div><h3>{exercise.name}</h3><p>{exercise.sets} sets × {exercise.reps} reps · {exercise.rest_seconds ?? 60}s rest{exercise.notes ? ` · ${exercise.notes}` : ''}</p></div><Dumbbell size={19} color="#91a46f" /></div>{videoUrl && <ExerciseDemonstration name={exercise.name} videoUrl={videoUrl} videoMediaId={videoMediaId} linkClassName="client-button secondary small" linkText="Watch demonstration" />}<div className="client-set-row client-set-labels"><span>SET</span><span>REPS</span><span>KG</span><span>RPE</span><span>DONE</span></div>{Array.from({ length: exercise.sets }, (_, index) => <SetRow key={index} number={index + 1} exercise={exercise} saved={sets[`${exercise.exercise_id}:${index + 1}`]} onLog={set => logSet(exercise, index + 1, set)} />)}</div>
  })}<label className="client-field" style={{ margin: '20px 0' }}><span>Session notes</span><textarea value={notes} onChange={event => setNotes(event.target.value)} maxLength={3000} placeholder="How did it feel? Anything your coach should know?" /></label>{save.isError && <ClientNotice danger>{save.error.message}</ClientNotice>}<div className="client-form-actions"><button className="client-button" disabled={save.isPending || !Object.keys(sets).length} onClick={finish}>{save.isPending ? 'Saving session…' : 'Finish & save session'}<Check size={16} /></button><button className="client-button secondary" disabled={save.isPending} onClick={onClose}>Back to plan</button></div><p className="client-onboarding-subtitle" style={{ marginTop: 12 }}>Only checked sets are included. You can skip movements and explain why in your notes.</p></ClientCard>
}

export function WorkoutsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const assignments = useClientQuery<Page<Assignment>>(clientKeys.assignments, '/programs/assignments')
  const sessions = useClientQuery<Page<WorkoutSession>>(clientKeys.sessions, '/workouts/sessions')
  const [selection, setSelection] = useState<{ assignment: string; workout: string } | null>(null)
  const selected = selection ?? (searchParams.get('workout') && searchParams.get('assignment') ? { assignment: searchParams.get('assignment')!, workout: searchParams.get('workout')! } : null)
  const assignment = assignments.data?.items.find(item => item.id === selected?.assignment)
  const workout = assignment?.snapshot.workouts.find(item => item.id === selected?.workout)
  function close() { setSelection(null); setSearchParams({}) }
  return <><ClientHeader {...clientCopy.workouts} />{assignments.isPending ? <ClientCard><ClientLoading /></ClientCard> : assignments.isError ? <ClientCard><ClientError error={assignments.error} retry={() => { void assignments.refetch() }} /></ClientCard> : assignment && workout ? <WorkoutLogger key={`${assignment.id}:${workout.id}`} assignment={assignment} workout={workout} onClose={close} /> : !assignments.data.items.length ? <ClientCard><ClientEmpty title="Your first workout starts with a plan." description="Your coach will assign workouts here after reviewing your assessment." /></ClientCard> : <div className="client-grid"><div className="client-stack">{assignments.data.items.map(item => <ClientCard key={item.id}><SectionHeading title={item.snapshot.name} detail={item.snapshot.description} />{item.snapshot.workouts.map(planned => <div className="client-list-row" key={planned.id}><div><h3>{planned.name}</h3><p>{planned.day ? `${planned.day} · ` : ''}{planned.exercises.length} exercises</p><div className="client-meta"><span><Dumbbell size={13} />{planned.exercises.reduce((sum, exercise) => sum + exercise.sets, 0)} working sets</span>{planned.duration_minutes && <span><Clock3 size={13} />{planned.duration_minutes} minutes</span>}</div></div><button className="client-button secondary small" onClick={() => setSelection({ assignment: item.id, workout: planned.id })}>Start session<ArrowRight size={14} /></button></div>)}</ClientCard>)}</div><ClientCard><SectionHeading title="Training history" />{sessions.isPending ? <ClientLoading /> : sessions.isError ? <ClientError error={sessions.error} retry={() => { void sessions.refetch() }} /> : !sessions.data.items.length ? <ClientEmpty title="Your story starts here." description="Completed sessions will appear here, ready for you and your coach to review." /> : sessions.data.items.slice(0, 10).map(session => { const title = assignments.data.items.find(item => item.id === session.assignment_id)?.snapshot.workouts.find(item => item.id === session.workout_id)?.name ?? 'Training session'; return <div className="client-list-row" key={session.id}><div><h3>{title}</h3><p>{formatDate(session.created_at)} · {session.sets.length} sets</p>{session.notes && <p style={{ marginTop: 6 }}>{session.notes}</p>}</div><span className="client-status completed">Saved</span></div> })}</ClientCard></div>}</>
}

export function ProgramsPage() {
  const assignments = useClientQuery<Page<Assignment>>(clientKeys.assignments, '/programs/assignments')
  return <><ClientHeader {...clientCopy.programs} />{assignments.isPending ? <ClientCard><ClientLoading /></ClientCard> : assignments.isError ? <ClientCard><ClientError error={assignments.error} retry={() => { void assignments.refetch() }} /></ClientCard> : !assignments.data.items.length ? <ClientCard><ClientEmpty title="A plan built around you." description="Assigned programs will appear here once your coach has reviewed your goals and assessment." /></ClientCard> : <div className="client-grid equal">{assignments.data.items.map(item => <ClientCard key={item.id}><div className="client-section-heading"><span className="client-inline-icon"><Dumbbell size={23} /></span><span className="client-status active">{item.status}</span></div><h2 style={{ fontSize: 23, letterSpacing: '-.6px' }}>{item.snapshot.name}</h2><p className="client-subtitle">{item.snapshot.description}</p><div className="client-meta" style={{ margin: '20px 0' }}><span>{item.snapshot.weeks ?? 'Flexible'} weeks</span><span>{item.snapshot.difficulty}</span><span>{item.snapshot.workouts.length} sessions</span></div><div className="client-goal-card"><h3>Training focus</h3><p>{item.snapshot.goal || 'A balanced training routine.'}</p></div><p className="client-onboarding-subtitle" style={{ margin: '15px 0' }}>Assigned {formatDate(item.created_at)} · Your assigned program is saved as a snapshot for your training history.</p><a href="/app/workouts" className="client-button secondary">View your workouts<ArrowRight size={15} /></a></ClientCard>)}</div>}</>
}
