import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Activity, Bell, BookOpen, CalendarDays, ChevronDown, CircleHelp, ClipboardCheck, CreditCard, Dumbbell, Ellipsis, FileText, LayoutDashboard, Lightbulb, LogOut, Menu, MessageSquare, Search, Settings, ShieldCheck, Target, Users, Video, X } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../services/auth';
import { api } from '../services/api';
import type { ListResult } from '../services/api';
import { Button, Modal, EmptyState } from '../components/ui';
import copy from '../locales/en.json';

type NavItem = { path: string; label: string; icon: LucideIcon };
const adminMain: NavItem[] = [
  { path: '/admin', label: copy.navigation.overview, icon: LayoutDashboard },
  { path: '/admin/clients', label: copy.navigation.clients, icon: Users },
  { path: '/admin/leads', label: copy.navigation.leads, icon: Target },
  { path: '/admin/programs', label: copy.navigation.programs, icon: Dumbbell },
  { path: '/admin/exercises', label: copy.navigation.exercises, icon: BookOpen },
  { path: '/admin/checkins', label: copy.navigation.checkins, icon: ClipboardCheck },
  { path: '/admin/messages', label: copy.navigation.messages, icon: MessageSquare },
  { path: '/admin/formchecks', label: 'Form reviews', icon: Video },
  { path: '/admin/calendar', label: copy.navigation.calendar, icon: CalendarDays },
];
const adminBusiness: NavItem[] = [
  { path: '/admin/payments', label: copy.navigation.payments, icon: CreditCard },
  { path: '/admin/content', label: copy.navigation.content, icon: FileText },
  { path: '/admin/feedback', label: 'Feedback & ideas', icon: Lightbulb },
  { path: '/admin/users', label: 'Users & access', icon: Users },
  { path: '/admin/audit', label: copy.navigation.audit, icon: ShieldCheck },
];
const clientMain: NavItem[] = [
  { path: '/app', label: 'My overview', icon: LayoutDashboard },
  { path: '/app/workouts', label: 'My workouts', icon: Dumbbell },
  { path: '/app/programs', label: 'My program', icon: BookOpen },
  { path: '/app/progress', label: 'My progress', icon: Activity },
  { path: '/app/habits', label: 'Daily habits', icon: ClipboardCheck },
  { path: '/app/nutrition', label: 'Nutrition', icon: Target },
  { path: '/app/checkins', label: 'Check-ins', icon: ClipboardCheck },
  { path: '/app/messages', label: 'Coach messages', icon: MessageSquare },
  { path: '/app/bookings', label: 'My sessions', icon: CalendarDays },
  { path: '/app/formchecks', label: 'Form checks', icon: Video },
  { path: '/app/feedback', label: 'Feedback & ideas', icon: Lightbulb },
  { path: '/app/billing', label: 'My membership', icon: CreditCard },
];
type Notification = { id: string; title: string; body: string; read: boolean; created_at: string; link?: string };
export function AppShell({ mode }: { mode: 'admin' | 'client' }) {
  const { user, logout } = useAuth(); const location = useLocation(); const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false); const [notificationOpen, setNotificationOpen] = useState(false); const [profileOpen, setProfileOpen] = useState(false); const [search, setSearch] = useState('');
  const notifications = useQuery({ queryKey: ['notifications'], queryFn: () => api<ListResult<Notification>>('/notifications') });
  const main = mode === 'admin' ? adminMain : clientMain;
  const business = mode !== 'admin' ? [] : user?.role === 'COACH' ? adminBusiness.filter(item => item.path === '/admin/audit') : user?.role === 'SUPER_ADMIN' ? adminBusiness : adminBusiness.filter(item => item.path !== '/admin/users');
  const current = [...main, ...business, {path:'/admin/settings',label:'Settings',icon:Settings}].find(item => item.path === location.pathname)?.label ?? (location.pathname.includes('/clients/') ? 'Client profile' : 'Workspace');
  const initials = user?.name.split(' ').map(word => word[0]).slice(0, 2).join('') || 'SB';
  const now = new Date(); const today = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: user?.timezone || 'Africa/Kigali' });
  useEffect(() => { setMobileOpen(false); setSearch(''); document.title = `${current} · Syre Banks Fitness`; }, [location.pathname, current]);
  const markNotificationsRead = async (ids: string[]) => {
    await Promise.allSettled(ids.map(id => api('/notifications/' + id, { method: 'PATCH' })));
    void notifications.refetch();
  };
  const renderNav = (items: NavItem[]) => <nav className="sidebar-nav" aria-label={mode === 'admin' ? 'Coach workspace' : 'Client workspace'}>{items.map(({ path, label, icon: Icon }) => <NavLink key={path} to={path} end={path === '/admin' || path === '/app'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>;
  return <div className="app-layout">
    {mobileOpen && <button className="sidebar-overlay" onClick={() => setMobileOpen(false)} aria-label="Close navigation"/>}
    <aside className={`sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
      <Link to="/" className="sidebar-brand"><div className="brand-mark">S</div><div className="brand-name">SYRE BANKS<small>FITNESS</small></div></Link>
      <p className="sidebar-section-label">{mode === 'admin' ? 'Coaching workspace' : 'Your training'}</p>{renderNav(main)}
      {mode === 'admin' && business.length > 0 && <><p className="sidebar-section-label">Business</p>{renderNav(business)}</>}
      <div className="sidebar-bottom">{(mode === 'client' || user?.role !== 'COACH') && <NavLink to={mode === 'admin' ? '/admin/settings' : '/app/onboarding'} className="nav-item"><Settings size={18}/>{mode === 'admin' ? 'Settings' : 'My profile'}</NavLink>}<Link to="/contact" className="nav-item"><CircleHelp size={18}/>Help & support</Link><div className="coach-profile"><div className="avatar avatar-lime">{initials}</div><div className="profile-info"><strong>{user?.name}</strong><small>{mode === 'admin' ? 'Coach account' : 'Client account'}</small></div><button className="profile-more" aria-label="Account options" onClick={() => setProfileOpen(true)}><Ellipsis size={19}/></button></div></div>
    </aside>
    <div className="workspace">
      <header className="topbar"><button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20}/></button><div className="breadcrumb"><span>{mode === 'admin' ? 'Workspace' : 'My coaching'}</span><span>/</span><b>{current}</b></div><div className="topbar-right">{mode === 'admin' && <form className="global-search" onSubmit={e => { e.preventDefault(); navigate(`/admin/clients?q=${encodeURIComponent(search)}`); }}><Search size={16}/><input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search clients…" aria-label="Search clients"/><kbd>↵</kbd></form>}<span className="topbar-date"><CalendarDays size={14}/>{today}</span><button className="icon-button" aria-label="Notifications" onClick={() => setNotificationOpen(true)}><Bell size={18}/>{notifications.data?.items.some(item => !item.read) && <span className="notification-dot"/>}</button><button className="avatar avatar-lime" aria-label="Account menu" style={{border:0}} onClick={() => setProfileOpen(true)}>{initials}</button></div></header>
      {import.meta.env.VITE_DEMO_MODE === 'true' && <div className="demo-label">Development workspace · seeded records are illustrative</div>}
      <main className="workspace-main"><Outlet/></main>
    </div>
    {notificationOpen && <Modal title="Your notifications" onClose={() => setNotificationOpen(false)}>{notifications.data?.items.length ? <><div className="stack">{notifications.data.items.map(item => <button className={'notification-item ' + (item.read ? '' : 'unread')} key={item.id} onClick={async () => { await markNotificationsRead([item.id]); setNotificationOpen(false); if (item.link) navigate(item.link); }}><strong>{item.title}</strong><p className="muted">{item.body}</p><small className="muted">{new Date(item.created_at).toLocaleString('en-GB',{timeZone:user?.timezone || 'Africa/Kigali'})}</small></button>)}</div>{notifications.data.items.some(item => !item.read) && <div className="form-actions"><Button variant="secondary" onClick={() => { void markNotificationsRead(notifications.data!.items.filter(item => !item.read).map(item => item.id)); }}>Mark all as read</Button></div>}</> : <EmptyState title="You're all caught up" description="New messages and coaching reminders will appear here."/>}</Modal>}
    {profileOpen && <Modal title="Your account" onClose={() => setProfileOpen(false)}><div className="name-cell"><div className="avatar avatar-lime">{initials}</div><div><strong>{user?.name}</strong><small>{user?.email}</small></div></div><div className="stack" style={{marginTop:24}}><Link className="button button-secondary" to="/" onClick={() => setProfileOpen(false)}>View public website <ChevronDown size={15}/></Link><button className="button button-secondary" onClick={async () => { setProfileOpen(false); await logout(); navigate('/login'); }}><LogOut size={16}/>Sign out</button><button className="button button-ghost" onClick={() => setProfileOpen(false)}><X size={16}/>Close</button></div></Modal>}
  </div>;
}
