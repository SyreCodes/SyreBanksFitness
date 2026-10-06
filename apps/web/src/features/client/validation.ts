import { z } from 'zod'

export const weightSchema = z.object({
  value: z.coerce.number().finite().min(20, 'Enter a weight of at least 20 kg.').max(400, 'Enter a weight below 400 kg.'),
  recorded_at: z.string().min(1, 'Choose the measurement date.'),
})

export const setSchema = z.object({
  reps: z.coerce.number().int().min(1, 'Enter at least one repetition.').max(200),
  weight_kg: z.coerce.number().finite().min(0).max(1000),
  rpe: z.union([z.literal(''), z.coerce.number().min(1).max(10)]).optional(),
})

export type LoggedSet = { exercise_id: string; set_number: number; reps: number; weight_kg: number; rpe?: number }

/** Zero is valid for bodyweight movements; an empty reps field is never a completed set. */
export function makeLoggedSet(exerciseId: string, setNumber: number, raw: unknown): LoggedSet {
  const set = setSchema.parse(raw)
  return { exercise_id: exerciseId, set_number: setNumber, reps: set.reps, weight_kg: set.weight_kg, ...(typeof set.rpe === 'number' ? { rpe: set.rpe } : {}) }
}

export function localDate(): string {
  const date = new Date()
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
