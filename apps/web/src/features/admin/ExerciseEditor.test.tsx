import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '../../services/api'
import { ExerciseEditor } from './ExerciseEditor'
import type { Exercise } from './types'

const mocks = vi.hoisted(() => ({ api: vi.fn(), upload: vi.fn() }))
vi.mock('../../services/api', async importOriginal => {
  const actual = await importOriginal<typeof import('../../services/api')>()
  return { ...actual, api: mocks.api }
})
vi.mock('../../services/exerciseVideo', async importOriginal => {
  const actual = await importOriginal<typeof import('../../services/exerciseVideo')>()
  return { ...actual, uploadExerciseVideo: mocks.upload }
})

const policy = { max_bytes: 100 * 1024 * 1024, accepted_types: ['video/mp4', 'video/webm', 'video/quicktime'] }
const base: Exercise = { id: 'exercise-1', name: 'Squat', muscle_group: 'Legs', equipment: 'Barbell', difficulty: 'Beginner', description: 'Stand tall.', instructions: 'Lower with control.', coach_cues: [], media_url: null, published: true }
const uploaded: Exercise = { ...base, video_media_id: 'media-1', video_url: '/api/v1/media/media-1/file' }

function renderEditor(exercise?: Exercise) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const onSaved = vi.fn()
  render(<QueryClientProvider client={query}><ExerciseEditor exercise={exercise} onSaved={onSaved} onClose={vi.fn()} /></QueryClientProvider>)
  return onSaved
}

async function chooseVideo(file = new File(['video bytes'], 'squat.mp4', { type: 'video/mp4' })) {
  await screen.findByText(/up to 100 MB/i)
  fireEvent.change(screen.getByLabelText('Demonstration video (optional)'), { target: { files: [file] } })
  return file
}

function fillNewExercise() {
  fireEvent.change(screen.getByLabelText('Exercise name'), { target: { value: 'Squat' } })
  fireEvent.change(screen.getByLabelText('Muscle group'), { target: { value: 'Legs' } })
  fireEvent.change(screen.getByLabelText('Equipment'), { target: { value: 'Barbell' } })
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Stand tall.' } })
  fireEvent.change(screen.getByLabelText('Instructions'), { target: { value: 'Lower with control.' } })
}

describe('exercise video editor', () => {
  beforeEach(() => {
    mocks.api.mockReset()
    mocks.upload.mockReset()
    mocks.api.mockImplementation(async (path: string) => path === '/exercises/video-upload-policy' ? policy : base)
    mocks.upload.mockResolvedValue(uploaded)
    HTMLDialogElement.prototype.showModal = function () { this.open = true }
    HTMLDialogElement.prototype.close = function () { this.open = false }
  })
  afterEach(cleanup)

  it('creates an exercise and uploads its selected MP4 with an upload ID', async () => {
    const onSaved = renderEditor()
    fillNewExercise()
    const file = await chooseVideo()
    fireEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(uploaded))
    expect(mocks.api.mock.calls.filter(([path]) => path === '/exercises')).toHaveLength(1)
    expect(mocks.upload).toHaveBeenCalledWith('exercise-1', file, expect.stringMatching(/^exercise-video-/), expect.any(AbortSignal), expect.objectContaining({ onProgress: expect.any(Function) }))
  })

  it('retries a failed video without resubmitting exercise details', async () => {
    mocks.upload.mockRejectedValueOnce(new ApiError('Storage unavailable', 503, 'STORAGE_UNAVAILABLE'))
    const onSaved = renderEditor()
    fillNewExercise()
    await chooseVideo()
    fireEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
    expect(await screen.findByText(/Exercise details were saved, but the video upload failed/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry video upload' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(uploaded))
    expect(mocks.api.mock.calls.filter(([path]) => path === '/exercises')).toHaveLength(1)
    expect(mocks.upload).toHaveBeenCalledTimes(2)
    expect(mocks.upload.mock.calls[0][2]).toBe(mocks.upload.mock.calls[1][2])
  })

  it('replaces an existing video after exercise details save', async () => {
    const replacement = { ...uploaded, video_media_id: 'media-2' }
    mocks.upload.mockResolvedValue(replacement)
    const onSaved = renderEditor(uploaded)
    const file = await chooseVideo()
    fireEvent.click(screen.getByRole('button', { name: 'Save exercise' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(replacement))
    expect(mocks.api.mock.calls.find(([path]) => path === '/exercises/exercise-1')?.[1]).toMatchObject({ method: 'PATCH' })
    expect(mocks.upload.mock.calls[0][1]).toBe(file)
  })

  it('keeps the current link if its replacement upload fails', async () => {
    mocks.api.mockImplementation(async (path: string) => path === '/exercises/video-upload-policy' ? policy : { ...base, media_url: 'https://example.com/old-video', video_url: 'https://example.com/old-video' })
    mocks.upload.mockRejectedValue(new ApiError('Storage unavailable', 503, 'STORAGE_UNAVAILABLE'))
    const onSaved = renderEditor({ ...base, media_url: 'https://example.com/old-video', video_url: 'https://example.com/old-video' })
    await chooseVideo()
    fireEvent.click(screen.getByRole('button', { name: 'Save exercise' }))
    expect(await screen.findByText(/Exercise details were saved, but the video upload failed/)).toBeInTheDocument()
    const payload = JSON.parse(mocks.api.mock.calls.find(([path]) => path === '/exercises/exercise-1')?.[1].body as string) as { media_url: string }
    expect(payload.media_url).toBe('https://example.com/old-video')
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('validates the configured size before saving the exercise', async () => {
    mocks.api.mockImplementation(async (path: string) => path === '/exercises/video-upload-policy' ? { ...policy, max_bytes: 2 } : base)
    renderEditor()
    fillNewExercise()
    await screen.findByText(/up to 0 MB/i)
    fireEvent.change(screen.getByLabelText('Demonstration video (optional)'), { target: { files: [new File(['too large'], 'squat.mp4', { type: 'video/mp4' })] } })
    expect(screen.getByText(/Video exceeds the 0 MB upload limit/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add exercise' })).toBeDisabled()
    expect(mocks.upload).not.toHaveBeenCalled()
  })

  it('shows upload progress', async () => {
    mocks.upload.mockImplementation((_id, _file, _key, _signal, callbacks) => {
      callbacks.onStage('uploading', 1)
      callbacks.onProgress(43)
      return new Promise<Exercise>(() => {})
    })
    renderEditor()
    fillNewExercise()
    await chooseVideo()
    fireEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
    expect(await screen.findByRole('progressbar', { name: 'Video upload progress' })).toHaveAttribute('value', '43')
  })

  it('removes a stored video with the video endpoint', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mocks.api.mockImplementation(async (path: string) => path === '/exercises/video-upload-policy' ? policy : { ...base, video_media_id: null, video_url: null })
    renderEditor(uploaded)
    fireEvent.click(screen.getByRole('button', { name: 'Remove current video' }))
    await waitFor(() => expect(mocks.api).toHaveBeenCalledWith('/exercises/exercise-1/video', { method: 'DELETE' }))
    vi.restoreAllMocks()
  })

  it('saves exercise details without starting a video upload', async () => {
    const onSaved = renderEditor()
    fillNewExercise()
    fireEvent.click(screen.getByRole('button', { name: 'Add exercise' }))
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(base))
    expect(mocks.upload).not.toHaveBeenCalled()
  })

  it('keeps the persisted demonstration visible while a new link is drafted', () => {
    renderEditor({ ...base, media_url: 'https://example.com/old.mp4', video_url: 'https://example.com/old.mp4' })
    fireEvent.change(screen.getByLabelText('Or use a video link'), { target: { value: 'https://example.com/new.mp4' } })
    expect(screen.getByRole('link', { name: 'Watch current demonstration' })).toHaveAttribute('href', 'https://example.com/old.mp4')
  })
})
