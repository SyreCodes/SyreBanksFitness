import { describe, expect, it } from 'vitest'
import { makeLoggedSet, weightSchema } from './validation'

describe('workout set logging', () => {
  it('preserves bodyweight sets and explicit exercise/set identity', () => {
    expect(makeLoggedSet('push-up', 2, { reps: '12', weight_kg: '0', rpe: '8' })).toEqual({ exercise_id: 'push-up', set_number: 2, reps: 12, weight_kg: 0, rpe: 8 })
  })
  it('rejects incomplete repetitions, fractions, and effort above the scale', () => {
    for (const input of [{ reps: '', weight_kg: 10 }, { reps: 1.5, weight_kg: 10 }, { reps: 10, weight_kg: 10, rpe: 11 }]) {
      expect(() => makeLoggedSet('squat', 1, input)).toThrow()
    }
  })
})

describe('weight recording', () => {
  it('accepts a decimal metric measurement', () => {
    expect(weightSchema.parse({ value: '76.4', recorded_at: '2026-10-03' }).value).toBe(76.4)
  })
  it('rejects empty, non-finite, implausible, or undated readings', () => {
    for (const value of ['', 'NaN', Infinity, 0, 401]) expect(weightSchema.safeParse({ value, recorded_at: '2026-10-03' }).success).toBe(false)
    expect(weightSchema.safeParse({ value: 76.4, recorded_at: '' }).success).toBe(false)
  })
})
