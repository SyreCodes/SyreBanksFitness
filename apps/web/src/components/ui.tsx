import { useEffect, useRef } from 'react';
import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react';
import { LoaderCircle, X, Inbox } from 'lucide-react';

export function Button({ children, variant = 'primary', className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger' }) { return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>; }
export function Card({ children, className = '', ...props }: HTMLAttributes<HTMLDivElement>) { return <div className={`card ${className}`} {...props}>{children}</div>; }
export function Badge({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'lime'; className?: string }) { return <span className={`badge badge-${tone} ${className}`}>{children}</span>; }
export function PageHeader({ title, subtitle, actions, eyebrow }: { title: string; subtitle?: string; actions?: ReactNode; eyebrow?: string }) { return <div className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</div>; }
export function Field({ label, children, error, hint, htmlFor }: { label: string; children: ReactNode; error?: string; hint?: string; htmlFor?: string }) { return <div className="field"><label htmlFor={htmlFor}>{label}{children}</label>{hint && <small>{hint}</small>}{error && <span className="field-error" role="alert">{error}</span>}</div>; }
export function Loading({ label = 'Loading your workspace…' }: { label?: string }) { return <div className="loading-state" role="status"><LoaderCircle className="spin" size={24}/><span>{label}</span></div>; }
export function EmptyState({ title, description, action, icon }: { title: string; description?: string; action?: ReactNode; icon?: ReactNode }) { return <div className="empty-state">{icon ?? <Inbox size={30}/>}<h3>{title}</h3>{description && <p>{description}</p>}{action}</div>; }
export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) { return <div className="error-state" role="alert"><strong>We couldn’t load this.</strong><p>{error instanceof Error ? error.message : 'Please try again.'}</p>{retry && <Button variant="secondary" onClick={retry}>Try again</Button>}</div>; }
export function Modal({ open = true, title, children, onClose }: { open?: boolean; title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; if (open && dialog && !dialog.open) dialog.showModal(); if (!open && dialog?.open) dialog.close(); }, [open]);
  return <dialog ref={ref} className="modal" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }}><div className="modal-head"><h2>{title}</h2><button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={21}/></button></div>{children}</dialog>;
}
