import { createContext, useContext } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';

export type PublicContent = {
  hero_image_url?: string;
  hero_image_caption?: string;
  hero_heading?: string;
  hero_description?: string;
  about_image_url?: string;
  about_heading?: string;
  about_bio?: string;
  coaching_philosophy?: string;
  contact_email?: string;
  contact_phone?: string;
  instagram_url?: string;
  tiktok_url?: string;
  legal_version?: string;
  faq?: { question: string; answer: string }[];
  transformations?: { id: string; alias: string; story: string; duration?: string; before_image_url: string; after_image_url: string; consent_status: string }[];
  testimonials?: { id: string; name: string; quote: string; publication_consent: boolean }[];
  legal?: Record<string, string>;
};

export type Product = {
  id: string;
  name: string;
  description: string;
  price_minor: number;
  currency: string;
  billing_interval: string;
  features?: string[];
  entitlements?: Record<string, boolean | number>;
};

export type Exercise = {
  id: string;
  name: string;
  description?: string;
  muscle_group?: string;
  equipment?: string;
  difficulty?: string;
  video_url?: string;
  video_media_id?: string | null;
  media_url?: string | null;
  image_url?: string;
  instructions?: string[] | string;
};

export type BlogPost = { id: string; title: string; slug?: string; excerpt?: string; body?: string; category?: string; cover_image_url?: string; published_at?: string };
export type Paginated<T> = { items: T[]; total: number };

export const PublicContentContext = createContext<PublicContent>({});
export const usePublicContent = () => useContext(PublicContentContext);
export const useProducts = () => useQuery({ queryKey: ['public-products'], queryFn: () => api<Paginated<Product>>('/products') });
export const useExercises = () => useQuery({ queryKey: ['public-exercises'], queryFn: async () => {
  const data = await api<Paginated<Exercise>>('/exercises');
  return { ...data, items: data.items.map(item => ({ ...item, video_url: item.video_url || (item.media_url && /(?:youtube\.com|youtu\.be|vimeo\.com|\.(?:mp4|webm)(?:\?|$))/i.test(item.media_url) ? item.media_url : undefined), image_url: item.image_url || (item.media_url && /\.(?:jpe?g|png|webp|avif)(?:\?|$)/i.test(item.media_url) ? item.media_url : undefined) })) };
} });

export async function fetchPublicContent(): Promise<PublicContent> {
  const raw = await api<PublicContent & { headline?: string; subheadline?: string; about?: string | { bio?: string; image_url?: string; heading?: string }; contact?: { email?: string; phone?: string; instagram_url?: string; tiktok_url?: string } }>('/content/public');
  return { ...raw, hero_heading: raw.hero_heading || raw.headline, hero_description: raw.hero_description || raw.subheadline, about_bio: raw.about_bio || (typeof raw.about === 'string' ? raw.about : raw.about?.bio), about_image_url: raw.about_image_url || (typeof raw.about === 'object' ? raw.about.image_url : undefined), about_heading: raw.about_heading || (typeof raw.about === 'object' ? raw.about.heading : undefined), contact_email: raw.contact_email || raw.contact?.email, contact_phone: raw.contact_phone || raw.contact?.phone, instagram_url: raw.instagram_url || raw.contact?.instagram_url, tiktok_url: raw.tiktok_url || raw.contact?.tiktok_url };
}

export function formatPrice(product: Product) {
  const currency = product.currency.toUpperCase();
  const exponent = new Intl.NumberFormat('en', { style: 'currency', currency }).resolvedOptions().maximumFractionDigits ?? 2;
  const divisor = 10 ** exponent;
  return new Intl.NumberFormat('en', { style: 'currency', currency, maximumFractionDigits: product.price_minor % divisor === 0 ? 0 : exponent }).format(product.price_minor / divisor);
}

export const publicCopy = {
  brand: 'SYRE BANKS',
  brandSuffix: 'FITNESS',
  heroHeading: 'BUILD THE BODY.\nBUILD THE DISCIPLINE.\nBUILD THE LIFE.',
  heroDescription: 'Personalized coaching. A clear plan. Real accountability. Build strength and confidence that go beyond the gym.',
  eyebrow: 'YOUR NEXT CHAPTER STARTS HERE',
  apply: 'Start your transformation',
  explore: 'Explore programs',
  goals: [
    { number: '01', name: 'Muscle building', description: 'Train with intent. Build a stronger, more capable body.', icon: 'dumbbell' },
    { number: '02', name: 'Fat loss', description: 'Create sustainable habits that support your goals.', icon: 'flame' },
    { number: '03', name: 'Strength', description: 'Get stronger with a plan that progresses with you.', icon: 'strength' },
    { number: '04', name: 'Body recomposition', description: 'Build muscle and refine your approach to training.', icon: 'target' },
    { number: '05', name: 'Beginner transformation', description: 'Build your foundation, one confident session at a time.', icon: 'beginner' },
    { number: '06', name: 'Lifestyle & habits', description: 'Make movement and consistency part of your life.', icon: 'habit' },
  ],
  faq: [
    { question: 'Do I need experience to get started?', answer: 'No. Your application and assessment help your coach understand your starting point. Training can be adapted to your experience, available equipment and schedule.' },
    { question: 'Can I train at home?', answer: 'Yes. Tell us where you train and which equipment you have. Your coach will discuss what is practical for your goals.' },
    { question: 'What is the difference between remote and live coaching?', answer: 'Remote coaching gives you a personalized plan, progress tracking and coach feedback on your own schedule. Live virtual training adds real-time guidance during scheduled sessions, subject to your plan and coach availability.' },
    { question: 'How do I choose a plan?', answer: 'Start with the coaching application. Your coach reviews your goals and preferences before helping you choose a suitable plan. Current prices are shown on the pricing page.' },
    { question: 'How quickly will I see results?', answer: 'Progress depends on your starting point, consistency, recovery and many other factors. Coaching focuses on measurable, sustainable progress; no specific result or timeframe is guaranteed.' },
    { question: 'Is nutrition guidance included?', answer: 'Coaching can include general nutrition habits and guidance according to your plan. It does not replace care from a qualified health professional.' },
  ],
};
