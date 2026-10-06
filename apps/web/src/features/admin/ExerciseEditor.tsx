import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Field, Modal } from '../../components/ui'
import { api } from '../../services/api'
import { mediaPlaybackUrl } from '../../services/media'
import {
  describeVideoUploadError, uploadExerciseVideo, videoFileError,
  type VideoUploadPolicy, type VideoUploadStage,
} from '../../services/exerciseVideo'
import type { Exercise } from './types'

type Props = { exercise?: Exercise; onClose: () => void; onSaved: (exercise: Exercise) => void }
const fallbackPolicy: VideoUploadPolicy = { max_bytes: 100 * 1024 * 1024, accepted_types: ['video/mp4', 'video/webm', 'video/quicktime'] }
const busyStages: VideoUploadStage[] = ['preparing', 'uploading', 'processing', 'retrying']

function newUploadKey(): string {
  return `exercise-video-${crypto.randomUUID()}`
}

function lines(value: string[] | string | undefined): string {
  return Array.isArray(value) ? value.join('\n') : value ?? ''
}

export function ExerciseEditor({ exercise, onClose, onSaved }: Props) {
  const queryClient = useQueryClient()
  const policyQuery = useQuery({ queryKey: ['exercise-video-policy'], queryFn: () => api<VideoUploadPolicy>('/exercises/video-upload-policy'), staleTime: 5 * 60_000 })
  const policy = policyQuery.data ?? fallbackPolicy
  const [saved, setSaved] = useState<Exercise | null>(exercise ?? null)
  const [file, setFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [stage, setStage] = useState<VideoUploadStage | 'idle'>('idle')
  const [progress, setProgress] = useState(0)
  const [attempt, setAttempt] = useState(1)
  const [saving, setSaving] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [detailsSaved, setDetailsSaved] = useState(false)
  const [error, setError] = useState('')
  const [uploadError, setUploadError] = useState('')
  const [notice, setNotice] = useState('')
  const [mediaUrl, setMediaUrl] = useState(exercise?.media_url ?? '')
  const uploadKey = useRef<string | null>(null)
  const uploadController = useRef<AbortController | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)
  const busy = saving || removing || busyStages.includes(stage as VideoUploadStage)
  const selectedFileError = file ? videoFileError(file, policy) : ''

  useEffect(() => {
    if (!file || typeof URL.createObjectURL !== 'function') { setPreviewUrl(null); return }
    const url = URL.createObjectURL(file)
    setPreviewUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [file])
  useEffect(() => () => uploadController.current?.abort(), [])

  function close() {
    if (busy) return
    if ((dirty || (file && stage !== 'complete')) && !window.confirm('Discard your unsaved exercise changes or selected video?')) return
    onClose()
  }

  function chooseFile(next: File | null) {
    setFile(next)
    setUploadError('')
    setNotice('')
    setStage('idle')
    setProgress(0)
    uploadKey.current = next ? newUploadKey() : null
    if (next) setDirty(true)
  }

  async function uploadVideo(target: Exercise) {
    if (!file || busyStages.includes(stage as VideoUploadStage)) return
    const validation = videoFileError(file, policy)
    if (validation) { setUploadError(validation); return }
    const controller = new AbortController()
    uploadController.current = controller
    setUploadError('')
    setProgress(0)
    try {
      const result = await uploadExerciseVideo<Exercise>(target.id, file, uploadKey.current ?? (uploadKey.current = newUploadKey()), controller.signal, {
        onProgress: setProgress,
        onStage: (next, retryAttempt) => { setStage(next); setAttempt(retryAttempt) },
      })
      setSaved(result)
      setDetailsSaved(false)
      setDirty(false)
      setNotice('Exercise and video saved.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['exercises'] }),
        queryClient.invalidateQueries({ queryKey: ['public-exercises'] }),
      ])
      onSaved(result)
    } catch (cause) {
      setStage('failed')
      setUploadError(`Exercise details were saved, but the video upload failed. ${describeVideoUploadError(cause, policy)}`)
    } finally {
      uploadController.current = null
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (busy) return
    if (file && policyQuery.isPending) { setError('Checking the video upload limit. Please try again shortly.'); return }
    if (file && policyQuery.isError) { setError('Could not check the upload limit. Retry loading the video policy.'); return }
    if (selectedFileError) { setUploadError(selectedFileError); return }
    const fields = new FormData(event.currentTarget)
    const payload = {
      name: String(fields.get('name') ?? '').trim(),
      muscle_group: String(fields.get('muscle_group') ?? '').trim(),
      equipment: String(fields.get('equipment') ?? '').trim(),
      difficulty: String(fields.get('difficulty') ?? '').trim(),
      description: String(fields.get('description') ?? '').trim(),
      instructions: String(fields.get('instructions') ?? '').trim(),
      coach_cues: String(fields.get('coach_cues') ?? '').split('\n').map(value => value.trim()).filter(Boolean),
      media_url: file ? (saved?.media_url ?? null) : (mediaUrl.trim() || null),
      published: fields.get('published') === 'on',
    }
    setSaving(true)
    setError('')
    setNotice('')
    try {
      const result = await api<Exercise>(saved ? `/exercises/${saved.id}` : '/exercises', {
        method: saved ? 'PATCH' : 'POST', body: JSON.stringify(payload),
      })
      setSaved(result)
      setDirty(false)
      setDetailsSaved(true)
      void queryClient.invalidateQueries({ queryKey: ['exercises'] })
      setSaving(false)
      if (file) await uploadVideo(result)
      else onSaved(result)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'The exercise could not be saved. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function removeUploadedVideo() {
    if (!saved?.video_media_id || busy) return
    if (!window.confirm('Remove this demonstration video from the exercise?')) return
    setRemoving(true)
    setError('')
    try {
      const result = await api<Exercise>(`/exercises/${saved.id}/video`, { method: 'DELETE' })
      setSaved(result)
      setNotice('Demonstration video removed.')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['exercises'] }),
        queryClient.invalidateQueries({ queryKey: ['public-exercises'] }),
      ])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Could not remove the video. Please try again.')
    } finally { setRemoving(false) }
  }

  const currentVideo = mediaPlaybackUrl(saved?.video_url)
  return <Modal title={exercise ? 'Edit exercise' : 'Add exercise'} onClose={close}>
    <form onSubmit={event => { void submit(event) }} onChange={() => setDirty(true)}>
      <Field label="Exercise name"><input name="name" defaultValue={exercise?.name ?? ''} required minLength={2} maxLength={120} /></Field>
      <div className="form-grid-two">
        <Field label="Muscle group"><input name="muscle_group" defaultValue={exercise?.muscle_group ?? exercise?.primary_muscle ?? ''} required minLength={2} maxLength={80} /></Field>
        <Field label="Equipment"><input name="equipment" defaultValue={exercise?.equipment ?? 'Bodyweight'} maxLength={100} /></Field>
      </div>
      <Field label="Difficulty"><select name="difficulty" defaultValue={exercise?.difficulty ?? 'Beginner'}><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select></Field>
      <Field label="Description"><textarea name="description" defaultValue={exercise?.description ?? ''} maxLength={5000} rows={3} /></Field>
      <Field label="Instructions"><textarea name="instructions" defaultValue={lines(exercise?.instructions)} maxLength={5000} rows={4} /></Field>
      <Field label="Coach cues (one per line)"><textarea name="coach_cues" defaultValue={lines(exercise?.coach_cues)} rows={3} /></Field>

      <div className="exercise-video-panel">
        <h3>Demonstration video</h3>
        {currentVideo && <div className="exercise-video-current"><p className="muted">Current demonstration</p>
          {saved?.video_media_id ? <video controls playsInline preload="metadata" src={currentVideo} aria-label="Current exercise demonstration" /> : <a href={currentVideo} target="_blank" rel="noopener noreferrer">Watch current demonstration</a>}
          <Button type="button" variant="secondary" disabled={busy} onClick={() => fileInput.current?.click()}>Replace video</Button>
          {saved?.video_media_id && <Button type="button" variant="danger" disabled={busy} onClick={() => { void removeUploadedVideo() }}>Remove current video</Button>}
          {!saved?.video_media_id && <Button type="button" variant="secondary" disabled={busy} onClick={() => { setMediaUrl(''); setDirty(true); setNotice('Save the exercise to remove its video link.') }}>Remove video link</Button>}
        </div>}
        <Field label="Demonstration video (optional)" hint={`Upload an MP4, WebM, or MOV file, up to ${Math.round(policy.max_bytes / (1024 * 1024))} MB.`}>
          <input ref={fileInput} type="file" accept={policy.accepted_types.join(',')} disabled={busy} onChange={event => chooseFile(event.currentTarget.files?.[0] ?? null)} />
        </Field>
        {policyQuery.isError && <p className="form-error" role="alert">Could not load the video upload limit. <Button type="button" variant="secondary" onClick={() => { void policyQuery.refetch() }}>Retry</Button></p>}
        {file && <div className="exercise-video-selected"><strong>{file.name}</strong><span>{(file.size / (1024 * 1024)).toFixed(1)} MB · {file.type || 'Unknown type'}</span>
          {previewUrl && <video controls playsInline preload="metadata" src={previewUrl} aria-label="Selected video preview" />}
          <Button type="button" variant="secondary" disabled={busy} onClick={() => { if (fileInput.current) fileInput.current.value = ''; chooseFile(null) }}>Clear selected video</Button>
        </div>}
        {selectedFileError && <p className="form-error" role="alert">{selectedFileError}</p>}
        {stage !== 'idle' && stage !== 'failed' && <div className="video-upload-status" role="status" aria-live="polite">
          <p>{stage === 'processing' ? 'Processing video on the server…' : stage === 'retrying' ? `Connection interrupted. Retrying upload (${attempt}/3)…` : stage === 'complete' ? 'Video uploaded.' : `Uploading video… ${progress}%`}</p>
          <progress value={progress} max={100} aria-label="Video upload progress" />
          {stage === 'uploading' && <Button type="button" variant="secondary" onClick={() => uploadController.current?.abort()}>Cancel upload</Button>}
        </div>}
        {uploadError && <div className="form-error" role="alert"><p>{uploadError}</p>
          {detailsSaved && saved && file && <Button type="button" variant="secondary" disabled={busy || Boolean(selectedFileError)} onClick={() => { void uploadVideo(saved) }}>Retry video upload</Button>}
        </div>}
        <Field label="Or use a video link" hint="A file upload replaces an existing link after it finishes successfully."><input type="url" value={mediaUrl} disabled={busy || Boolean(saved?.video_media_id)} onChange={event => { setMediaUrl(event.target.value); setDirty(true) }} placeholder="https://…" /></Field>
      </div>
      <label className="checkbox-row"><input name="published" type="checkbox" defaultChecked={exercise?.published !== false} /> Publish to exercise library</label>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}
      <div className="form-actions"><Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancel</Button><Button disabled={busy || Boolean(selectedFileError)}>{saving ? 'Saving…' : exercise ? 'Save exercise' : 'Add exercise'}</Button></div>
    </form>
  </Modal>
}
