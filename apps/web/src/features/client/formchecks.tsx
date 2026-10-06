import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Play, RefreshCw, Send, ShieldCheck, Video } from 'lucide-react'
import { api } from '../../services/api'
import { mediaPlaybackUrl } from '../../services/media'
import type { ListResult } from '../../services/api'
import { ClientCard, ClientEmpty, ClientError, ClientHeader, ClientLoading, ClientNotice, FieldLabel, formatDateTime, SectionHeading } from './common'
import type { Assignment } from './types'

export type FormCheck = {
  id: string; client_id: string; client_name: string; exercise_id: string; exercise_name: string;
  media_asset_id: string; comment: string; status: 'SUBMITTED' | 'REVIEWED' | 'NEEDS_CORRECTION' | 'APPROVED';
  feedback: string; timestamped_notes: { seconds: number; note: string }[]; reviewed_at?: string;
  created_at: string; media_url: string | null; media_available: boolean;
}
type ExerciseOption = { id: string; name: string }
type Submission = { exercise_id: string; comment: string }

function timeLabel(seconds: number) { return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}` }

function FormCheckHistory({ item, refresh }: { item: FormCheck; refresh: () => void }) {
  const video = useRef<HTMLVideoElement>(null)
  const [failed, setFailed] = useState(false)
  const url = mediaPlaybackUrl(item.media_url)
  function seek(seconds: number) { if (video.current) { video.current.currentTime = seconds; void video.current.play().catch(() => undefined) } }
  return <ClientCard><SectionHeading title={item.exercise_name} detail={`Submitted ${formatDateTime(item.created_at)}`} /><span className={`client-status ${item.status === 'APPROVED' ? 'completed' : ''}`}>{item.status.replaceAll('_', ' ')}</span>{item.comment && <p className="client-subtitle" style={{ margin: '14px 0' }}>{item.comment}</p>}{url ? <><video ref={video} key={url} src={url} controls playsInline preload="metadata" onError={() => setFailed(true)} onCanPlay={() => setFailed(false)} style={{ width: '100%', maxHeight: 340, borderRadius: 10, marginTop: 16, background: '#22271e' }} aria-label={`${item.exercise_name} form check video`} />{failed && <ClientNotice>The video link may have expired, or this browser cannot play the video. Refresh the link and try again.</ClientNotice>}<button type="button" className="client-button secondary small" style={{ marginTop: 10 }} onClick={refresh}><RefreshCw size={13} />Refresh video link</button></> : <ClientNotice>The video is no longer available. Your feedback and submission history are preserved.</ClientNotice>}{item.feedback && <div className="client-goal-card" style={{ marginTop: 18 }}><h3>Your coach’s feedback</h3><p style={{ whiteSpace: 'pre-wrap' }}>{item.feedback}</p>{item.reviewed_at && <p style={{ marginTop: 8, fontSize: 10 }}>{formatDateTime(item.reviewed_at)}</p>}</div>}{item.timestamped_notes.length > 0 && <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>{item.timestamped_notes.map((note, index) => <div key={index} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}><button type="button" className="client-button secondary small" disabled={!url} onClick={() => seek(note.seconds)} aria-label={`Play video at ${timeLabel(note.seconds)}`}><Play size={12} />{timeLabel(note.seconds)}</button><p className="client-subtitle">{note.note}</p></div>)}</div>}</ClientCard>
}

export function FormChecksPage() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(0)
  const [file, setFile] = useState<File | null>(null)
  const [uploadedAsset, setUploadedAsset] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const form = useForm<Submission>({ defaultValues: { exercise_id: '', comment: '' } })
  const exercises = useQuery({ queryKey: ['client', 'formcheck-exercises'], queryFn: async () => {
    const [catalog, programs] = await Promise.all([api<ListResult<ExerciseOption>>('/exercises?limit=100'), api<ListResult<Assignment>>('/programs/assignments?limit=100')])
    const choices = new Map(catalog.items.map(exercise => [exercise.id, exercise]))
    for (const assignment of programs.items.filter(item => item.status === 'ACTIVE')) for (const workout of assignment.snapshot.workouts) for (const exercise of workout.exercises) choices.set(exercise.exercise_id, { id: exercise.exercise_id, name: exercise.name })
    return [...choices.values()].sort((a, b) => a.name.localeCompare(b.name))
  } })
  const history = useQuery({ queryKey: ['client', 'formchecks', page], queryFn: () => api<ListResult<FormCheck>>(`/formchecks?limit=10&offset=${page * 10}`) })
  const fileError = file && (file.type !== 'video/mp4' ? 'Choose a video in MP4 format.' : file.size > 10 * 1024 * 1024 ? 'Keep your video below 10 MB.' : file.size === 0 ? 'Choose a nonempty video.' : '')
  const submit = useMutation({ mutationFn: async (values: Submission) => {
    if (!file || fileError) throw new Error(fileError || 'Choose a short MP4 video first.')
    let mediaId = uploadedAsset
    if (!mediaId) {
      const body = new FormData(); body.set('file', file); body.set('purpose', 'private'); body.set('public', 'false'); body.set('caption', 'Private movement form check')
      const asset = await api<{ id: string }>('/media', { method: 'POST', body })
      mediaId = asset.id; setUploadedAsset(asset.id)
    }
    return api<FormCheck>('/formchecks', { method: 'POST', body: JSON.stringify({ ...values, media_asset_id: mediaId }) })
  }, onSuccess: () => {
    form.reset(); setFile(null); setUploadedAsset(null); setSuccess(true); setPage(0)
    if (input.current) input.current.value = ''
    void queryClient.invalidateQueries({ queryKey: ['client', 'formchecks'] })
  } })
  return <><ClientHeader eyebrow="MOVE WITH CONFIDENCE" title="A little guidance goes a long way." subtitle="Share a short movement video and get clear, private feedback from your coach." /><div className="client-grid"><ClientCard><SectionHeading title="Send a form check" detail="Film 15–30 seconds with your full movement in frame." /><ClientNotice><ShieldCheck size={16} style={{ verticalAlign: 'middle', marginRight: 7 }} />Your video stays private. Your assigned coach and administrators can review it.</ClientNotice>{exercises.isPending ? <ClientLoading /> : exercises.isError ? <ClientError error={exercises.error} retry={() => { void exercises.refetch() }} /> : !exercises.data.length ? <ClientEmpty title="Your exercise list is on its way." description="Your coach will add exercises and assign your plan before you submit a movement video." /> : <form className="client-form" onSubmit={form.handleSubmit(values => submit.mutate(values))}><FieldLabel title="Which exercise would you like reviewed?"><select {...form.register('exercise_id', { required: 'Choose an exercise.' })} disabled={submit.isPending}><option value="">Choose an exercise</option>{exercises.data.map(exercise => <option key={exercise.id} value={exercise.id}>{exercise.name}</option>)}</select></FieldLabel>{form.formState.errors.exercise_id && <p className="client-form-error" role="alert">{form.formState.errors.exercise_id.message}</p>}<FieldLabel title="Movement video (MP4, up to 10 MB)" hint="Avoid capturing other people in your video."><input ref={input} type="file" accept="video/mp4,.mp4" disabled={submit.isPending} onChange={event => { setFile(event.target.files?.[0] ?? null); setUploadedAsset(null); setSuccess(false); submit.reset() }} /></FieldLabel>{fileError && <p className="client-form-error" role="alert">{fileError}</p>}<FieldLabel title="What would you like help with? (optional)"><textarea {...form.register('comment')} disabled={submit.isPending} maxLength={3000} placeholder="For example: Is my squat depth right? I’m unsure about the last repetition." /></FieldLabel>{submit.isError && <ClientNotice danger>{submit.error.message}</ClientNotice>}{success && <ClientNotice>Your video is submitted. Your coach will review it and your feedback will appear here.</ClientNotice>}<button className="client-button" type="submit" disabled={submit.isPending || !file || Boolean(fileError)}><Send size={15} />{submit.isPending ? 'Uploading & submitting…' : 'Send to your coach'}</button></form>}</ClientCard><div className="client-stack"><div><SectionHeading title="Your form checks" detail="Feedback and video notes, all in one place." />{history.isPending ? <ClientCard><ClientLoading /></ClientCard> : history.isError ? <ClientCard><ClientError error={history.error} retry={() => { void history.refetch() }} /></ClientCard> : !history.data.items.length ? <ClientCard><ClientEmpty title="Start with one movement." description="Submit a short video when you’d like your coach’s eyes on your form." action={<span className="client-inline-icon"><Video size={20} /></span>} /></ClientCard> : <div className="client-stack">{history.data.items.map(item => <FormCheckHistory key={item.id} item={item} refresh={() => { void history.refetch() }} />)}</div>}{history.data && history.data.total > 10 && <div className="client-form-actions" style={{ marginTop: 18 }}><button className="client-button secondary small" disabled={page === 0} onClick={() => setPage(value => value - 1)}><ChevronLeft size={15} />Previous</button><span className="client-subtitle">Page {page + 1} of {Math.ceil(history.data.total / 10)}</span><button className="client-button secondary small" disabled={(page + 1) * 10 >= history.data.total} onClick={() => setPage(value => value + 1)}>Next<ChevronRight size={15} /></button></div>}</div></div></div></>
}
