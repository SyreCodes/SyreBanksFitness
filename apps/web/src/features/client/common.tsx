import type { ReactNode } from 'react'
import { ArrowUpRight, AlertCircle, LoaderCircle, RefreshCw, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'

export function ClientHeader({ eyebrow, title, subtitle, action }: { eyebrow: string; title: string; subtitle: string; action?: ReactNode }) {
  return <header className="client-page-header"><div><p className="client-eyebrow">{eyebrow}</p><h1>{title}</h1><p className="client-subtitle">{subtitle}</p></div>{action}</header>
}

export function ClientLoading() { return <div className="client-state" role="status"><LoaderCircle className="client-spin" size={28} /><p>Loading your coaching space…</p></div> }
export function ClientError({ error, retry }: { error?: unknown; retry?: () => void }) { return <div className="client-state client-error" role="alert"><AlertCircle size={28} /><h3>We couldn’t load this yet.</h3><p>{error instanceof Error ? error.message : 'Please try again in a moment.'}</p>{retry && <button className="client-button secondary" onClick={retry}><RefreshCw size={16} />Try again</button>}</div> }
export function ClientEmpty({ title, description, action }: { title: string; description: string; action?: ReactNode }) { return <div className="client-state"><span className="client-state-icon"><Sparkles size={22} /></span><h3>{title}</h3><p>{description}</p>{action}</div> }
export function ClientCard({ children, className = '' }: { children: ReactNode; className?: string }) { return <section className={`client-card ${className}`}>{children}</section> }
export function SectionHeading({ title, link, linkLabel = 'View all', detail }: { title: string; link?: string; linkLabel?: string; detail?: string }) { return <div className="client-section-heading"><div><h2>{title}</h2>{detail && <p>{detail}</p>}</div>{link && <Link to={link}>{linkLabel}<ArrowUpRight size={16} /></Link>}</div> }
export function ClientNotice({ children, danger = false }: { children: ReactNode; danger?: boolean }) { return <div className={`client-notice ${danger ? 'danger' : ''}`} role={danger ? 'alert' : 'status'}>{children}</div> }
export function formatDate(value?: string, options?: Intl.DateTimeFormatOptions) { return value ? new Date(value).toLocaleDateString(undefined, options ?? { month: 'short', day: 'numeric', year: 'numeric' }) : '—' }
export function formatDateTime(value?: string) { return value ? new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', timeZoneName: 'short' }) : '—' }
export function FieldLabel({ title, children, hint }: { title: string; children: ReactNode; hint?: string }) { return <label className="client-field"><span>{title}</span>{children}{hint && <small>{hint}</small>}</label> }
