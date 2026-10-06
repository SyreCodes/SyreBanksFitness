import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { useMutation, useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { ArrowLeft, ArrowUpRight, Eye, EyeOff, LoaderCircle, CheckCircle2, Mail, ShieldCheck } from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../services/auth';
import { Brand } from '../public/Brand';
import { fetchPublicContent } from '../public/content';
import { loginSchema, registerSchema, resetSchema } from './authSchema';
import '../public/public.css';
import './auth.css';

type AuthValues = { name: string; email: string; password: string; confirm_password: string };
type AuthMode = 'login' | 'register' | 'forgot-password' | 'reset-password' | 'verify-email';
const authCopy: Record<AuthMode, { eyebrow: string; title: string; description: string; action: string }> = {
  login: { eyebrow: 'WELCOME BACK', title: 'SHOW UP.\nGET STRONGER.', description: 'Your plan, your progress, your next move. Let’s get to work.', action: 'Log in to your account' },
  register: { eyebrow: 'YOUR NEXT CHAPTER', title: 'BUILD YOUR\nFOUNDATION.', description: 'Create your account and take the next step toward purposeful coaching.', action: 'Create your account' },
  'forgot-password': { eyebrow: 'GET BACK ON TRACK', title: 'RESET.\nREFOCUS.', description: 'Enter your email and we’ll send reset instructions if an account exists.', action: 'Send reset instructions' },
  'reset-password': { eyebrow: 'A FRESH START', title: 'MAKE YOUR\nNEXT MOVE.', description: 'Choose a strong new password for your coaching account.', action: 'Set your new password' },
  'verify-email': { eyebrow: 'ONE LAST CHECK', title: 'VERIFY YOUR\nEMAIL ADDRESS.', description: 'Confirm your email to keep your coaching account connected.', action: 'Verify email address' },
};

export function AuthPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const auth = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const mode = (Object.keys(authCopy).includes(location.pathname.slice(1)) ? location.pathname.slice(1) : 'login') as AuthMode;
  const copy = authCopy[mode];
  const form = useForm<AuthValues>({ defaultValues: { name: '', email: '', password: '', confirm_password: '' } });
  const content = useQuery({ queryKey: ['public-content'], queryFn: fetchPublicContent });
  const mutation = useMutation({ mutationFn: async (values: AuthValues) => {
    if (mode === 'login') { const user = await auth.login(values.email, values.password); navigate(['SUPER_ADMIN', 'ADMIN', 'COACH'].includes(user.role) ? '/admin' : '/app', { replace: true }); return { message: 'You’re logged in.' }; }
    if (mode === 'register') { const user = await auth.register({ name: values.name, email: values.email, password: values.password }); navigate(['SUPER_ADMIN', 'ADMIN', 'COACH'].includes(user.role) ? '/admin' : '/app/onboarding', { replace: true }); return { message: 'Your account is ready.' }; }
    if (mode === 'forgot-password') return api<{ message: string }>('/auth/forgot-password', { method: 'POST', body: JSON.stringify({ email: values.email }) });
    if (mode === 'reset-password') return api<{ message: string }>('/auth/reset-password', { method: 'POST', body: JSON.stringify({ token: search.get('token'), password: values.password }) });
    return api<{ message: string }>('/auth/verify-email', { method: 'POST', body: JSON.stringify({ token: search.get('token') }) });
  } });
  const resend = useMutation({ mutationFn: () => api<{ message: string }>('/auth/request-verification', { method: 'POST' }) });
  const resetForm = form.reset;
  const resetMutation = mutation.reset;
  useEffect(() => { resetForm(); resetMutation(); setShowPassword(false); document.title = `${mode === 'login' ? 'Log in' : mode === 'register' ? 'Create an account' : copy.eyebrow} · Syre Banks Fitness`; }, [mode, copy.eyebrow, resetForm, resetMutation]);
  const submit = form.handleSubmit(values => {
    form.clearErrors();
    const schema = mode === 'login' ? loginSchema : mode === 'register' ? registerSchema : mode === 'forgot-password' ? z.object({ email: z.email('Enter a valid email address.') }) : mode === 'reset-password' ? resetSchema : z.object({});
    const result = schema.safeParse(values);
    if (!result.success) { result.error.issues.forEach(issue => form.setError(issue.path[0] as keyof AuthValues, { message: issue.message })); const key = result.error.issues[0]?.path[0] as keyof AuthValues | undefined; if (key) form.setFocus(key); return; }
    mutation.mutate(values);
  });
  const field = (name: keyof AuthValues, label: string, type: string, autoComplete: string) => <label className="sb-field">{label}<div className={name === 'password' || name === 'confirm_password' ? 'sb-password-field' : undefined}><input {...form.register(name)} type={type === 'password' && showPassword ? 'text' : type} autoComplete={autoComplete} aria-label={label} aria-describedby={form.formState.errors[name] ? `auth-${name}-error` : undefined} aria-invalid={!!form.formState.errors[name]} />{name === 'password' && <button type="button" onClick={() => setShowPassword(!showPassword)} aria-label={showPassword ? 'Hide password' : 'Show password'} aria-pressed={showPassword}>{showPassword ? <EyeOff size={19} /> : <Eye size={19} />}</button>}</div>{form.formState.errors[name] && <span id={`auth-${name}-error`} role="alert">{form.formState.errors[name]?.message}</span>}</label>;
  const missingToken = (mode === 'reset-password' || mode === 'verify-email') && !search.get('token');

  return <div className="public-site sb-auth"><aside className="sb-auth-visual"><Brand light />{content.data?.hero_image_url && <img src={content.data.hero_image_url} alt="Illustrative training photography" />}<div className="sb-auth-visual-shade" /><div className="sb-auth-motto"><p className="sb-kicker">PURPOSE. PROCESS. PROGRESS.</p><h2>BUILD THE BODY.<br />BUILD THE DISCIPLINE.<br /><span>BUILD THE LIFE.</span></h2><p>Personalized coaching. Real accountability.<br />A stronger chapter starts with you.</p></div><small>{content.data?.hero_image_caption || 'SYRE BANKS FITNESS'}</small></aside><main className="sb-auth-main"><Link className="sb-auth-back" to="/"><ArrowLeft size={17} />Back to home</Link><div className="sb-auth-mobile-brand"><Brand /></div><div className="sb-auth-form"><p className="sb-kicker">{copy.eyebrow}</p><h1>{copy.title}</h1><p className="sb-auth-description">{copy.description}</p>{mutation.isSuccess && !['login', 'register'].includes(mode) ? <div className="sb-auth-success" role="status"><CheckCircle2 size={36} /><h2>{mode === 'forgot-password' ? 'CHECK YOUR INBOX.' : mode === 'reset-password' ? 'PASSWORD UPDATED.' : 'EMAIL VERIFIED.'}</h2><p>{mutation.data.message}</p><Link className="sb-button sb-button-dark" to="/login">Back to login <ArrowUpRight size={18} /></Link></div> : missingToken ? <div className="sb-auth-token-state"><Mail size={34} /><h2>{mode === 'verify-email' ? 'Check your verification email.' : 'You need a reset link.'}</h2><p>{mode === 'verify-email' ? 'Open the verification link sent to your email address to confirm your account.' : 'Request a password reset email, then open the link included in it.'}</p>{mode === 'verify-email' && auth.user ? <button className="sb-button sb-button-dark" disabled={resend.isPending} onClick={() => resend.mutate()}>{resend.isPending ? 'Sending…' : 'Resend verification email'}</button> : <Link className="sb-button sb-button-dark" to={mode === 'verify-email' ? '/login' : '/forgot-password'}>{mode === 'verify-email' ? 'Log in to resend' : 'Request a reset link'} <ArrowUpRight size={18} /></Link>}{resend.isSuccess && <p role="status">{resend.data.message}</p>}{resend.isError && <p className="sb-form-error" role="alert">{resend.error.message}</p>}</div> : <form onSubmit={submit} noValidate>{mode === 'register' && field('name', 'Full name', 'text', 'name')}{['login', 'register', 'forgot-password'].includes(mode) && field('email', 'Email address', 'email', 'email')}{['login', 'register', 'reset-password'].includes(mode) && field('password', mode === 'reset-password' ? 'New password' : 'Password', 'password', mode === 'login' ? 'current-password' : 'new-password')}{['register', 'reset-password'].includes(mode) && <><p className="sb-password-hint">Use at least 12 characters. A unique passphrase works well.</p>{field('confirm_password', 'Confirm password', 'password', 'new-password')}</>}{mode === 'login' && <Link className="sb-auth-forgot" to="/forgot-password">Forgot your password?</Link>}{mutation.isError && <div className="sb-form-error" role="alert">{mutation.error.message}</div>}<button type="submit" className="sb-button sb-button-dark sb-auth-submit" disabled={mutation.isPending}>{mutation.isPending ? <><LoaderCircle size={18} className="spin" />Please wait…</> : <>{copy.action} <ArrowUpRight size={19} /></>}</button>{mode === 'register' && <p className="sb-auth-legal">Review our <Link to="/legal/terms">Terms</Link> and <Link to="/legal/privacy">Privacy Policy</Link> before creating your account.</p>}</form>}{mode === 'login' && <p className="sb-auth-switch">New to the team? <Link to="/register">Create an account <ArrowUpRight size={15} /></Link></p>}{mode === 'register' && <p className="sb-auth-switch">Already have an account? <Link to="/login">Log in <ArrowUpRight size={15} /></Link></p>}<div className="sb-auth-security"><ShieldCheck size={16} /><span>Your account. Your progress. Kept private.</span></div></div><footer className="sb-auth-footer"><span>© {new Date().getFullYear()} Syre Banks Fitness</span><Link to="/contact">Need help?</Link></footer></main></div>;
}
