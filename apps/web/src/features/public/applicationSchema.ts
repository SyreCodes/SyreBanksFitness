import { z } from 'zod';

const text = (message: string) => z.string().trim().min(1, message).max(3000);
const numericText = (minimum: number, maximum: number, message: string) => z.string().trim().refine(value => value !== '' && Number.isFinite(Number(value)) && Number(value) >= minimum && Number(value) <= maximum, message);

export const applicationSteps = [
  z.object({ name: z.string().trim().min(2, 'Enter your full name.').max(120), email: z.email('Enter a valid email address.'), phone: z.string().trim().min(7, 'Enter a phone number we can contact you on.').max(30), country: text('Enter your country.'), timezone: text('Choose your timezone.'), age: numericText(1, 120, 'Enter a valid age.').refine(value => Number.isInteger(Number(value)), 'Enter your age in whole years.') }),
  z.object({ goal: text('Choose your primary goal.'), secondary_goals: z.string().max(1000), desired_outcome: z.string().trim().min(10, 'Tell us what success would look like (at least 10 characters).').max(3000), target_timeframe: text('Choose your timeframe.') }),
  z.object({ experience: text('Choose your experience level.'), training_frequency: text('Choose your current training frequency.'), environment: text('Choose where you train.'), equipment: text('Tell us which equipment you have, or enter none.') }),
  z.object({ occupation: text('Enter your occupation or daily routine.'), activity_level: text('Choose your activity level.'), sleep_hours: numericText(1, 24, 'Enter your usual sleep hours between 1 and 24.'), stress: text('Choose your usual stress level.'), training_days: z.array(z.string()).min(1, 'Choose at least one available day.'), training_time: text('Choose your preferred training time.') }),
  z.object({ coaching_preference: z.enum(['remote', 'live', 'hybrid'], { error: 'Choose a coaching approach.' }) }),
  z.object({ motivation: z.string().trim().min(10, 'Tell us why now (at least 10 characters).').max(3000), obstacle: text('Tell us about your biggest obstacle.'), previous_attempts: text('Tell us what you have tried, or enter this is my first start.'), stopping_pattern: text('Tell us what usually gets in the way.') }),
  z.object({ budget: text('Select a plan interest or choose to discuss it.') }),
  z.object({ consent: z.literal(true, { error: 'Please agree before submitting your application.' }) }),
];

export const applicationSchema = applicationSteps.reduce((combined, step) => combined.merge(step), z.object({}));

export type ApplicationValues = {
  name: string; email: string; phone: string; country: string; timezone: string; age: string;
  goal: string; secondary_goals: string; desired_outcome: string; target_timeframe: string;
  experience: string; training_frequency: string; environment: string; equipment: string;
  occupation: string; activity_level: string; sleep_hours: string; stress: string; training_days: string[]; training_time: string;
  coaching_preference: 'remote' | 'live' | 'hybrid' | ''; motivation: string; obstacle: string; previous_attempts: string; stopping_pattern: string;
  budget: string; consent: boolean;
};

export const applicationDraftKey = 'syre-coaching-application-v1';

export function initialApplicationValues(search: URLSearchParams): ApplicationValues {
  const empty: ApplicationValues = { name: '', email: '', phone: '', country: '', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Africa/Kigali', age: '', goal: search.get('goal') || '', secondary_goals: '', desired_outcome: '', target_timeframe: '', experience: '', training_frequency: '', environment: '', equipment: '', occupation: '', activity_level: '', sleep_hours: '', stress: '', training_days: [], training_time: '', coaching_preference: (['remote', 'live', 'hybrid'].includes(search.get('preference') || '') ? search.get('preference') : '') as ApplicationValues['coaching_preference'], motivation: '', obstacle: '', previous_attempts: '', stopping_pattern: '', budget: search.get('plan') || '', consent: false };
  try {
    const raw = sessionStorage.getItem(applicationDraftKey);
    if (!raw) return empty;
    const saved: unknown = JSON.parse(raw);
    if (!saved || typeof saved !== 'object' || Array.isArray(saved)) return empty;
    const values = { ...empty };
    for (const key of Object.keys(empty) as (keyof ApplicationValues)[]) {
      const value = (saved as Record<string, unknown>)[key];
      if (key === 'training_days') { if (Array.isArray(value) && value.every(day => typeof day === 'string')) values.training_days = value; }
      else if (key === 'consent') values.consent = false;
      else if (typeof value === 'string') Object.assign(values, { [key]: value });
    }
    return values;
  } catch { return empty; }
}

export function applicationPayload(values: ApplicationValues, consentVersion: string) {
  return { ...values, name: values.name.trim(), email: values.email.trim(), phone: values.phone.trim(), age: Number(values.age), sleep_hours: Number(values.sleep_hours), consent_version: consentVersion, source: 'WEBSITE', timezone: values.timezone, utm_source: new URLSearchParams(window.location.search).get('utm_source'), utm_campaign: new URLSearchParams(window.location.search).get('utm_campaign') };
}
