import { z } from 'zod';

export const loginSchema = z.object({ email: z.email('Enter a valid email address.'), password: z.string().min(1, 'Enter your password.') });
export const registerSchema = z.object({ name: z.string().trim().min(2, 'Enter your full name.').max(120), email: z.email('Enter a valid email address.'), password: z.string().min(12, 'Use at least 12 characters.').max(128), confirm_password: z.string() }).refine(values => values.password === values.confirm_password, { path: ['confirm_password'], message: 'Your passwords do not match.' });
export const resetSchema = z.object({ password: z.string().min(12, 'Use at least 12 characters.').max(128), confirm_password: z.string() }).refine(values => values.password === values.confirm_password, { path: ['confirm_password'], message: 'Your passwords do not match.' });
