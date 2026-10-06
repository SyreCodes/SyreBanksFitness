import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../services/api'

export const clientKeys = {
  profile: ['client', 'profile'], assignments: ['client', 'assignments'], sessions: ['client', 'sessions'],
  measurements: ['client', 'measurements'], habits: ['client', 'habits'], habitLogs: ['client', 'habit-logs'],
  checkins: ['client', 'checkins'], messages: ['client', 'messages'], bookings: ['client', 'bookings'],
  availability: ['client', 'availability'], nutrition: ['client', 'nutrition'], products: ['products'],
  subscriptions: ['client', 'subscriptions'], invoices: ['client', 'invoices'],
} as const

export function useClientQuery<T>(queryKey: readonly string[], path: string, enabled = true) {
  return useQuery<T>({ queryKey, queryFn: () => api<T>(path), enabled })
}

export function useClientMutation<TInput, TOutput = unknown>(path: string | ((input: TInput) => string), options: { method?: string; keys?: readonly (readonly string[])[]; body?: (input: TInput) => unknown } = {}) {
  const queryClient = useQueryClient()
  return useMutation<TOutput, Error, TInput>({
    mutationFn: (input) => api<TOutput>(typeof path === 'function' ? path(input) : path, { method: options.method ?? 'POST', body: JSON.stringify(options.body ? options.body(input) : input) }),
    onSuccess: async () => { await Promise.all((options.keys ?? []).map(queryKey => queryClient.invalidateQueries({ queryKey }))) },
  })
}
