import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Dumbbell, Plus, Search } from 'lucide-react'
import { Badge, Button, Card, EmptyState, ErrorState, Loading, Modal, PageHeader } from '../../components/ui'
import { mediaPlaybackUrl } from '../../services/media'
import { ExerciseEditor } from './ExerciseEditor'
import { useList, useToast } from './shared'
import type { Exercise } from './types'

function lines(value: Exercise['instructions'] | Exercise['coach_cues']): string[] {
  const steps = Array.isArray(value) ? value : value?.split('\n') ?? []
  return steps.map(step => step.trim()).filter(Boolean)
}

function ExerciseDetail({ exercise, onClose, onEdit }: { exercise: Exercise; onClose: () => void; onEdit: () => void }) {
  const [videoFailed, setVideoFailed] = useState(false)
  const videoUrl = mediaPlaybackUrl(exercise.video_url)
  const instructions = lines(exercise.instructions)
  const cues = lines(exercise.coach_cues)
  return <Modal title={exercise.name} onClose={onClose}>
    <p className="muted">{exercise.description}</p>
    <Badge tone={exercise.published === false ? 'neutral' : 'success'}>{exercise.published === false ? 'Draft' : 'Published'}</Badge>
    {videoUrl && exercise.video_media_id && <div style={{ marginTop: 20 }}>
      <video key={videoUrl} src={videoUrl} controls playsInline preload="metadata" aria-label={`${exercise.name} demonstration video`} onError={() => setVideoFailed(true)} onCanPlay={() => setVideoFailed(false)} style={{ width: '100%', maxHeight: 380, borderRadius: 10, background: '#22271e' }} />
      {videoFailed && <p className="form-error" role="alert">This video could not be played. Try reopening the exercise to refresh its link.</p>}
    </div>}
    {videoUrl && !exercise.video_media_id && <a href={videoUrl} rel="noopener noreferrer" target="_blank" className="button button-primary" style={{ marginTop: 20 }}>Watch demonstration</a>}
    <h3 style={{ marginTop: 24 }}>Movement instructions</h3>
    <ol style={{ fontSize: '.875rem', lineHeight: 1.9 }}>{(instructions.length ? instructions : ['Coach instructions have not been added.']).map((step, index) => <li key={index}>{step}</li>)}</ol>
    {cues.length > 0 && <div className="notice">{cues.join(' · ')}</div>}
    <div className="form-actions"><Button type="button" variant="secondary" onClick={onEdit}>Edit exercise or video</Button></div>
  </Modal>
}

export function Exercises() {
  const query = useList<Exercise>('/exercises', 'exercises')
  const [params, setParams] = useSearchParams()
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('All')
  const [editor, setEditor] = useState<Exercise | 'new' | null>(params.get('create') === 'true' ? 'new' : null)
  const [selected, setSelected] = useState<Exercise | null>(null)
  const toast = useToast()
  const rows = query.data?.items.filter(item =>
    (!search || item.name.toLowerCase().includes(search.toLowerCase())) &&
    (filter === 'All' || (item.primary_muscle || item.muscle_group || '').toLowerCase().includes(filter.toLowerCase()))
  ) ?? []

  function closeEditor() {
    setEditor(null)
    if (params.has('create')) {
      const next = new URLSearchParams(params)
      next.delete('create')
      setParams(next, { replace: true })
    }
  }

  return <>
    <PageHeader title="Good form. Strong foundations." subtitle="Your movement library, ready to teach and train." eyebrow="Exercise library" actions={<Button onClick={() => setEditor('new')}><Plus size={17} />Add exercise</Button>} />
    <div className="filter-bar">
      <div className="filters">{['All', 'Chest', 'Back', 'Legs', 'Shoulders', 'Core'].map(value => <button key={value} className={`filter-button ${filter === value ? 'active' : ''}`} onClick={() => setFilter(value)}>{value}</button>)}</div>
      <div className="search-input"><Search size={16} /><input aria-label="Search exercises" placeholder="Find a movement…" value={search} onChange={event => setSearch(event.target.value)} /></div>
    </div>
    {query.isPending ? <Loading /> : query.isError ? <ErrorState error={query.error} retry={() => { void query.refetch() }} /> : !rows.length ? <Card><EmptyState title="No movements found" description="Add an exercise or adjust your search." /></Card> : <div className="resource-grid">{rows.map(item => <Card className="resource-card" key={item.id}>
      <div className="resource-image">{item.thumbnail_url ? <img src={item.thumbnail_url} alt="" /> : <Dumbbell size={40} strokeWidth={1.2} />}</div>
      <div className="resource-body">
        <Badge tone="lime">{item.primary_muscle || item.muscle_group || 'Full body'}</Badge>
        <h3>{item.name}</h3><p>{item.description || 'Controlled movement. Consistent progress.'}</p>
        <div className="resource-meta"><span>{item.equipment}</span><span>{item.difficulty}</span><span>{item.video_media_id ? 'Video uploaded' : item.video_url ? 'Video linked' : 'No video'}</span></div>
        <Button variant="secondary" onClick={() => setSelected(item)} style={{ width: '100%' }}>View movement</Button>
      </div>
    </Card>)}</div>}
    {editor && <ExerciseEditor key={editor === 'new' ? 'new' : editor.id} exercise={editor === 'new' ? undefined : editor} onClose={closeEditor} onSaved={saved => { closeEditor(); setSelected(saved); toast(editor === 'new' ? 'Exercise added to your library.' : 'Exercise updated.'); }} />}
    {selected && !editor && <ExerciseDetail key={`${selected.id}:${selected.video_url}`} exercise={selected} onClose={() => setSelected(null)} onEdit={() => { setEditor(selected); setSelected(null) }} />}
  </>
}
