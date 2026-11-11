import { useQuery } from '@tanstack/react-query';
import { api, type ListResult } from '../../services/api';
export type FAQ = { question: string; answer: string };
export type Price = { currency: 'RWF' | 'USD'; amount_minor: number; pricing_type: 'one_time' | 'monthly' | 'annual' };
export type Introduction = { cover_media_id: string | null; intro_media_id: string | null; demonstration_media_ids: string[]; environment: 'Home' | 'Gym' | 'Either'; equipment: string[]; days_per_week: number; minutes_per_session: number; suitability: string; philosophy: string; support: string[]; measurement: string; expectations: string; faq: FAQ[] };
export type Program = Omit<Introduction, 'days_per_week' | 'minutes_per_session'> & { days_per_week: number | null; minutes_per_session: number | null; id: string; name: string; goal: string; description: string; difficulty: string; weeks: number; published?: boolean; cover_url: string | null; intro_url: string | null; demonstration_urls: string[]; launch_details?: Partial<Introduction> };
export type CatalogItem = { id: string; name: string; description: string; full_description: string; type: 'COACHING' | 'MEMBERSHIP' | 'DIGITAL'; status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED'; active: boolean; featured: boolean; categories: string[]; features: string[]; prices: Price[]; program_ids: string[]; cover_media_id?: string | null; preview_media_id?: string | null; paid_media_ids?: string[]; cover_url: string | null; preview_url: string | null; support_level: string; duration: string; renewal: string; cancellation: string; suitability: string; delivery: string; availability: 'COMING_SOON' | 'ENROLLMENT_OPEN' | 'WAITLIST'; faq: FAQ[] };
export type Flags = { enrollment: boolean; digital_store: boolean; program_discovery: boolean; live_payments: false };
export const useFlags = () => useQuery({ queryKey: ['launch-flags'], queryFn: () => api<Flags>('/launch/config'), staleTime: 30_000 });
export const usePrograms = () => useQuery({ queryKey: ['launch-programs'], queryFn: () => api<ListResult<Program>>('/launch/programs') });
export const useProgram = (id?: string) => useQuery({ queryKey: ['launch-program', id], queryFn: () => api<Program>(`/launch/programs/${id}`), enabled: !!id });
export const useCatalog = (params = '') => useQuery({ queryKey: ['launch-catalog', params], queryFn: () => api<ListResult<CatalogItem>>('/launch/catalog' + (params ? '?' + params : '')) });
export function priceText(price: Price) { return new Intl.NumberFormat('en', { style: 'currency', currency: price.currency, maximumFractionDigits: price.currency === 'RWF' ? 0 : 2 }).format(price.amount_minor / (price.currency === 'USD' ? 100 : 1)); }
export const cleanText = (text?: string) => (text || '').replace(/\\n/g, '\n');
export const goals = [
  ['Build Muscle', 'Progressive training for a stronger foundation.'], ['Lose Body Fat', 'Sustainable routines, without extreme promises.'], ['Improve Strength', 'Build confidence in the movements that matter.'], ['Train at Home', 'Make your space work for your training.'], ['Improve Athletic Performance', 'Move with strength, control and purpose.'], ['Build Healthy Habits', 'Small actions you can return to every day.'],
];
export const introDefaults: Introduction = { cover_media_id: null, intro_media_id: null, demonstration_media_ids: [], environment: 'Either', equipment: [], days_per_week: 3, minutes_per_session: 45, suitability: '', philosophy: '', support: [], measurement: '', expectations: '', faq: [] };
