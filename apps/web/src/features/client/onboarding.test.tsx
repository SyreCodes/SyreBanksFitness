import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OnboardingPage } from './onboarding'

const request = vi.hoisted(() => vi.fn())
vi.mock('../../services/api', () => ({ api: request }))

afterEach(() => { cleanup(); request.mockReset() })

describe('assessment and consent updates', () => {
  it('uses the current policy version, preserves a withdrawn photo permission, and omits blank numeric fields', async () => {
    const version = '2026-02'
    const profile = {
      id: 'profile', client_id: 'client', onboarding_complete: true, review_required: false,
      assessment: { age: 30, height_cm: 180, weight_kg: 80, primary_goal: 'Build strength', training_experience: 'Some experience', environment: 'Gym', training_days: 'Monday and Friday', duration_minutes: 60 },
      health_screening: { heart_condition: false, chest_pain: false, dizziness: false, injury: false, medical_restriction: false, other_condition: false },
      consents: [
        ...['terms', 'privacy', 'coaching', 'liability'].map(kind => ({ kind, version, accepted: true })),
        { kind: 'photo', version, accepted: true }, { kind: 'photo', version, accepted: false },
      ],
    }
    request.mockImplementation((path: string, options?: RequestInit) => {
      if (path === '/content/public') return Promise.resolve({ legal_version: version })
      if (options?.method === 'PATCH') return Promise.resolve({ ...profile, ...JSON.parse(options.body as string) })
      return Promise.resolve(profile)
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter><OnboardingPage /></MemoryRouter></QueryClientProvider>)
    await screen.findByRole('heading', { name: 'Your starting point' })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await screen.findByRole('heading', { name: 'Training around your life' })
    fireEvent.click(screen.getByRole('button', { name: 'Continue' }))
    await screen.findByRole('heading', { name: 'Health & your permissions' })
    expect(screen.getByRole('checkbox', { name: /Optional: I give separate permission/ })).not.toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: 'Save my assessment' }))
    await screen.findByText('Your assessment is saved.')
    const call = request.mock.calls.find(([, options]) => options?.method === 'PATCH')
    expect(call).toBeDefined()
    const payload = JSON.parse(call![1].body)
    expect(payload.assessment).not.toHaveProperty('sleep_hours')
    expect(payload.assessment.duration_minutes).toBe(60)
    expect(payload.consents.every((consent: { version: string }) => consent.version === version)).toBe(true)
    expect(payload.consents.find((consent: { kind: string }) => consent.kind === 'photo').accepted).toBe(false)
  })
})
