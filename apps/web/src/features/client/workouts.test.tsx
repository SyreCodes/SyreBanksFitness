import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WorkoutsPage } from './workouts'

const request = vi.hoisted(() => vi.fn())
vi.mock('../../services/api', () => ({ api: request }))
vi.mock('../../services/auth', () => ({ useAuth: () => ({ user: { id: 'client-one', name: 'Test Client' } }) }))

const assignment = { id: 'assignment-one', status: 'ACTIVE', created_at: '2026-10-03T09:00:00Z', snapshot: { name: 'Foundation', workouts: [{ id: 'workout-one', name: 'Full body', exercises: [{ exercise_id: 'squat', name: 'Bodyweight squat', sets: 2, reps: '10–12', rest_seconds: 45 }] }] } }

afterEach(() => { cleanup(); sessionStorage.clear(); request.mockReset() })

function showWorkout(demonstration?: { id: string; video_url: string; video_media_id: string }) {
  request.mockImplementation((path: string, options?: RequestInit) => {
    if (path === '/programs/assignments') return Promise.resolve({ items: [assignment], total: 1 })
    if (path.startsWith('/exercises?')) return Promise.resolve({ items: demonstration ? [demonstration] : [], total: demonstration ? 1 : 0 })
    if (options?.method === 'POST') return Promise.resolve({ id: 'saved-session', ...JSON.parse(options.body as string) })
    return Promise.resolve({ items: [], total: 0 })
  })
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  render(<QueryClientProvider client={queries}><MemoryRouter initialEntries={['/app/workouts?assignment=assignment-one&workout=workout-one']}><WorkoutsPage /></MemoryRouter></QueryClientProvider>)
}

describe('client workout completion', () => {
  it('shows an uploaded exercise demonstration while logging the workout', async () => {
    showWorkout({ id: 'squat', video_url: '/api/v1/media/video-one/file', video_media_id: 'video-one' })
    const video = await screen.findByLabelText('Bodyweight squat video demonstration')
    expect(video.tagName).toBe('VIDEO')
    expect(video).toHaveAttribute('controls')
    expect(video.getAttribute('src')).toMatch(/\/api\/v1\/media\/video-one\/file$/)
  })

  it('saves checked sets once the client finishes, including zero-weight bodyweight sets', async () => {
    showWorkout()
    const reps = await screen.findByRole('spinbutton', { name: 'Bodyweight squat set 1 repetitions' })
    const finish = screen.getByRole('button', { name: 'Finish & save session' })
    expect(finish).toBeDisabled()
    fireEvent.change(reps, { target: { value: '12' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log Bodyweight squat set 1' }))
    expect(request.mock.calls.some(([, options]) => options?.method === 'POST')).toBe(false)
    expect(screen.getByRole('timer')).toHaveTextContent('00:45')
    fireEvent.click(finish)
    await screen.findByText('Session complete. Good work.')
    await waitFor(() => {
      const call = request.mock.calls.find(([path, options]) => path === '/workouts/sessions' && options?.method === 'POST')
      expect(call).toBeDefined()
      expect(JSON.parse(call![1].body)).toMatchObject({ assignment_id: 'assignment-one', workout_id: 'workout-one', completed: true, sets: [{ exercise_id: 'squat', set_number: 1, reps: 12, weight_kg: 0, completed: true }] })
    })
  })
  it('keeps unfinished repetitions from becoming a completed workout', async () => {
    showWorkout()
    await screen.findByRole('spinbutton', { name: 'Bodyweight squat set 1 repetitions' })
    fireEvent.click(screen.getByRole('button', { name: 'Log Bodyweight squat set 1' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter reps')
    expect(screen.getByRole('button', { name: 'Finish & save session' })).toBeDisabled()
  })
})
