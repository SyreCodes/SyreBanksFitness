import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Activity, AlertCircle, CalendarDays, CheckCircle2, ChevronDown, ClipboardCheck, CreditCard, Download, Dumbbell, FileText, MessageSquare, Plus, TrendingUp, Users, Video } from 'lucide-react';
import { api } from '../../services/api';
import { useAuth } from '../../services/auth';
import { Badge, Button, Card, EmptyState, ErrorState, Loading, PageHeader } from '../../components/ui';
import type { Dashboard as DashboardData } from './types';
import { date, exportCsv, initials, label, money } from './shared';

export function Dashboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';
  const [range, setRange] = useState('6months');
  const query = useQuery({ queryKey: ['admin-dashboard'], queryFn: () => api<DashboardData>('/admin/dashboard') });
  if (query.isPending) return <Loading/>;
  if (query.isError) return <ErrorState error={query.error} retry={() => void query.refetch()}/>;
  const data = query.data; const metrics = data.metrics;
  const greeting = new Date().toLocaleDateString('en-GB', {weekday:'long',day:'numeric',month:'long',timeZone:'Africa/Kigali'});
  const hour = Number(new Date().toLocaleTimeString('en-GB', {hour:'2-digit',hourCycle:'h23',timeZone:'Africa/Kigali'}));
  const salutation = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const chartData = range === '3months' ? data.revenue_trend.slice(-3) : data.revenue_trend;
  const priorityActions = data.priority_actions.filter(item => item.count > 0);
  const maxFunnelCount = Math.max(1, ...data.lead_funnel.map(item => item.count));
  const additionalRevenue = Object.entries(data.revenue_by_currency_minor)
    .filter(([currency]) => currency !== metrics.revenue_currency)
    .map(([currency, amount]) => money(amount / (currency === 'RWF' ? 1 : 100), currency))
    .join(' · ');
  return <>
    <PageHeader title={`${salutation}, ${user?.name.split(' ')[0] || 'Syre'} 👋`} subtitle="A little discipline, every day. Let’s keep your clients moving forward." eyebrow={greeting} actions={<><Button variant="secondary" onClick={() => exportCsv('coaching-overview', [['Metric','Value'],...Object.entries(metrics).map(([key,value]) => [label(key),value ?? 'Unavailable'])])}><Download size={15}/>Export report</Button>{isAdmin&&<Link to="/admin/clients?create=true" className="button button-primary"><Plus size={17}/>Add client</Link>}</>}/>
    <Card className="command-card">
      <div className="command-heading"><div><span className="eyebrow">TODAY</span><h2>Your coaching priorities</h2><p>Start with the people and tasks waiting for you.</p></div><span className="command-date">{greeting}</span></div>
      {priorityActions.length ? <div className="command-actions">{priorityActions.map(item => <Link to={item.href} key={item.key} className="command-action"><strong>{item.count}</strong><span>{item.label}</span><ChevronDown size={14} style={{transform:'rotate(-90deg)'}}/></Link>)}</div> : <div className="command-clear"><CheckCircle2 size={20}/>Your queue is clear. Take a look at your upcoming sessions below.</div>}
    </Card>
    <div className="metric-grid">
      <Metric label="Active clients" value={String(metrics.active_clients)} icon={<Users size={16}/>} note={`${metrics.total_clients} clients in your workspace`}/>
      <Metric label="Monthly revenue · USD" value={money(metrics.monthly_revenue)} icon={<CreditCard size={16}/>} note={additionalRevenue ? 'Also received ' + additionalRevenue : 'Verified payments this month'}/>
      <Metric label="New leads" value={String(metrics.new_leads)} icon={<TrendingUp size={16}/>} note="Ready for your first conversation"/>
      <Metric label="Weekly training activity" value={`${Math.round(metrics.workout_adherence)}%`} icon={<Activity size={16}/>} note="Active clients who logged a workout"/>
      <Metric label="Pending form reviews" value={String(metrics.formchecks_pending)} icon={<Video size={16}/>} note="Movement videos needing coach feedback"/>
      <Metric label="Unread messages" value={String(metrics.unread_messages)} icon={<MessageSquare size={16}/>} note="Client conversations awaiting a reply"/>
      <Metric label="Active memberships" value={String(metrics.active_subscriptions)} icon={<CreditCard size={16}/>} note="Paid periods currently active"/>
      <Metric label="Failed payments" value={String(metrics.failed_payments)} icon={<AlertCircle size={16}/>} note="Payments needing follow-up"/>
    </div>
    <div className="dashboard-grid">
      <Card><div className="section-heading"><div><h2>Revenue overview</h2><p className="muted" style={{fontSize:'.7rem',marginTop:5}}>Your business, growing with your community.</p></div><select className="chart-select" aria-label="Revenue date range" value={range} onChange={e => setRange(e.target.value)}><option value="6months">Last 6 months</option><option value="3months">Last 3 months</option></select></div><div className="revenue-head"><strong>{money(chartData.reduce((total,row) => total+row.revenue,0))}</strong><span>total revenue in this period</span></div>{chartData.some(row => row.revenue > 0) ? <div style={{height:213,width:'100%'}}><ResponsiveContainer><AreaChart data={chartData} margin={{top:20,right:4,bottom:0,left:-20}}><defs><linearGradient id="revenue" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c5df77" stopOpacity={.4}/><stop offset="100%" stopColor="#c5df77" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#edf0e5"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{fill:'#9ba48b',fontSize:10}} dy={10}/><YAxis tickLine={false} axisLine={false} tick={{fill:'#9ba48b',fontSize:10}} tickFormatter={value => `$${value >= 1000 ? `${value/1000}k` : value}`}/><Tooltip formatter={value => money(Number(value))} contentStyle={{border:'1px solid #e4e8da',borderRadius:10,fontSize:12}}/><Area type="monotone" dataKey="revenue" stroke="#95b34c" strokeWidth={2.5} fill="url(#revenue)"/></AreaChart></ResponsiveContainer></div> : <div className="revenue-empty"><EmptyState title="No verified revenue yet" description="Paid invoices will appear on the chart as they arrive."/></div>}</Card>
      <Card><div className="section-heading"><h2>Needs your attention <span className="number-pill">{metrics.clients_needing_attention+metrics.checkins_pending}</span></h2><Activity size={16} color="#a2ac8c"/></div>
        {metrics.checkins_pending>0 && <Link to="/admin/checkins" className="priority-item"><div className="priority-symbol"><ClipboardCheck size={17}/></div><div className="priority-text"><strong>{metrics.checkins_pending} check-ins to review</strong><small>A few words from you can make their week.</small></div><Badge tone="warning">Review</Badge></Link>}
        {data.attention.slice(0,3).map((item,index) => <Link to={`/admin/clients/${item.client_id}`} key={`${item.client_id}-${index}`} className="priority-item"><div className="avatar avatar-orange">{initials(item.name)}</div><div className="priority-text"><strong>{item.name}</strong><small>{item.reason}</small></div><ChevronDown size={13} color="#a9ae9d" style={{transform:'rotate(-90deg)'}}/></Link>)}
        {!data.attention.length && !metrics.checkins_pending && <EmptyState title="Everyone is moving forward" description="Clients with missed workouts or check-ins will appear here." icon={<CheckCircle2 size={28}/>}/>}
        <Link to="/admin/clients?status=NEEDS_ATTENTION" className="attention-footer">View all priority clients</Link>
      </Card>
    </div>
    <div className="dashboard-analytics">
      <Card><div className="section-heading"><h2>New clients</h2><Users size={16} color="#a4ae90"/></div><div className="mini-chart"><ResponsiveContainer><BarChart data={data.new_clients_trend} margin={{top:8,right:4,bottom:0,left:-24}}><CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#edf0e5"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{fill:'#7a866b',fontSize:11}}/><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{fill:'#7a866b',fontSize:11}}/><Tooltip contentStyle={{border:'1px solid #e4e8da',borderRadius:10,fontSize:12}}/><Bar dataKey="count" name="New clients" fill="#a9c46a" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></div></Card>
      <Card>
        <div className="section-heading"><h2>Lead funnel</h2><TrendingUp size={16} color="#a4ae90"/></div>
        <div className="funnel-list">{data.lead_funnel.map(item => <div className="funnel-row" key={item.stage}>
          <span className="funnel-label">{label(item.stage)}</span>
          <div className="funnel-track" aria-hidden="true"><span style={{width:(item.count / maxFunnelCount * 100) + '%'}}/></div>
          <strong>{item.count}</strong>
        </div>)}</div>
        <p className="analytics-foot">{metrics.lead_conversion}% of applications converted to clients</p>
      </Card>
      <Card><div className="section-heading"><h2>Membership status</h2><CreditCard size={16} color="#a4ae90"/></div>{data.subscription_status.length ? <div className="subscription-breakdown">{data.subscription_status.map(item => <div key={item.status}><span>{label(item.status)}</span><strong>{item.count}</strong></div>)}</div> : <EmptyState title="No memberships yet" description="Verified memberships will appear here."/>}<div className="analytics-foot"><strong>Annualized recurring revenue</strong><span>{metrics.annualized_recurring_revenue_minor == null ? 'Unavailable while memberships do not auto-renew' : money(metrics.annualized_recurring_revenue_minor / 100)}</span></div></Card>
    </div>
    <div className="dashboard-grid">
      <Card className="table-card"><div className="section-heading"><h2>Your clients</h2><Link className="text-link" to="/admin/clients">View all clients</Link></div><div className="table-wrap"><table className="data-table"><thead><tr><th>Client</th><th>Goal</th><th>Status</th><th>Adherence</th><th/></tr></thead><tbody>{data.recent_clients.slice(0,4).map((client,index) => <tr key={client.id}><td><Link to={`/admin/clients/${client.id}`} className="name-cell"><div className={`avatar ${['avatar-purple','avatar-orange','avatar-blue','avatar-lime'][index%4]}`}>{initials(client.name)}</div><div><strong>{client.name}</strong><small>Joined {date(client.joined_at)}</small></div></Link></td><td>{client.goal || 'Assessment pending'}</td><td><Badge tone={client.status==='ACTIVE'?'success':client.status==='ONBOARDING'?'lime':'neutral'}>{label(client.status)}</Badge></td><td><div className="adherence-cell"><span>{client.adherence == null ? '—' : `${Math.round(client.adherence)}%`}</span>{client.adherence != null && <div className="progress-track"><span style={{width:`${client.adherence}%`}}/></div>}</div></td><td><Link to={`/admin/clients/${client.id}`} className="row-action" aria-label={`View ${client.name}`}><ChevronDown size={14} style={{transform:'rotate(-90deg)'}}/></Link></td></tr>)}</tbody></table></div>{!data.recent_clients.length && <EmptyState title="Meet your first client" action={isAdmin?<Link to="/admin/clients?create=true" className="button button-primary">Add client</Link>:undefined}/>}<div className="table-footer"><span>Showing {Math.min(data.recent_clients.length,4)} of {metrics.total_clients} clients</span><Link to="/admin/clients">Manage clients</Link></div></Card>
      <Card><div className="section-heading"><h2>Upcoming sessions</h2><Link to="/admin/calendar" className="text-link">View calendar</Link></div>{data.sessions.slice(0,3).map(session => <div className="session-item" key={session.id}><div className="session-time"><strong>{new Date(session.starts_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',timeZone:'Africa/Kigali'})}</strong>{date(session.starts_at)}</div><div className="session-info"><strong>{session.client_name || 'Coaching session'}</strong><small>{label(session.type || session.session_type || 'Live training')}</small></div><div className="session-type-icon"><Video size={15}/></div></div>)}{!data.sessions.length && <EmptyState title="Room to connect" description="Booked consultations and training sessions appear here." icon={<CalendarDays size={28}/>}/>}<Link to="/admin/calendar" className="button button-secondary" style={{width:'100%',marginTop:18}}><Plus size={14}/>Schedule a session</Link></Card>
    </div>
    <div className="dashboard-three">
      <Card><div className="section-heading"><h2>Recent activity</h2><Link to="/admin/audit" className="text-link">View all</Link></div>{data.activity.slice(0,4).map((item,index) => <div className="activity-item" key={item.id}><div className="activity-dot">{index%2 ? <ClipboardCheck size={12}/> : <CheckCircle2 size={12}/>}</div><div className="activity-text"><p>{item.label || label(item.action)}</p><small>{date(item.created_at)}</small></div></div>)}{!data.activity.length && <EmptyState title="A fresh start" description="Coaching activity will appear here."/>}</Card>
      <Card><div className="section-heading"><h2>Coaching at a glance</h2><Dumbbell size={16} color="#a4ae90"/></div><div className="coaching-stat"><span>Check-ins awaiting review</span><strong>{metrics.checkins_pending}</strong></div><div className="coaching-stat"><span>Upcoming sessions</span><strong>{metrics.upcoming_sessions}</strong></div><div className="coaching-stat"><span>Clients needing attention</span><strong>{metrics.clients_needing_attention}</strong></div><div className="coaching-stat"><span>Lead conversion</span><strong>{metrics.lead_conversion}%</strong></div><div className="coaching-adherence"><span>Weekly training activity</span><strong>{Math.round(metrics.workout_adherence)}%</strong><div className="progress-track"><span style={{width:Math.min(100,Math.max(0,metrics.workout_adherence))+'%'}}/></div></div><div className="consistency-note"><div className="consistency-icon"><Activity size={18}/></div><p>Progress comes from showing up.<br/><strong>Keep the momentum going.</strong></p></div></Card>
      <Card className="quick-actions-card"><div className="section-heading"><h2>Make your next move</h2></div><p>Less admin. More coaching.</p><div className="quick-actions"><Link to="/admin/programs?create=true"><Dumbbell size={18}/>Create program</Link><Link to="/admin/exercises?create=true"><Plus size={18}/>Add exercise</Link><Link to="/admin/messages"><MessageSquare size={18}/>Message a client</Link>{isAdmin&&<Link to="/admin/content"><FileText size={18}/>Manage content</Link>}</div></Card>
    </div>
    <div className="dashboard-end"><span>Small steps. Stronger every day.</span><span>SYRE BANKS FITNESS</span></div>
  </>;
}
function Metric({label:metricLabel,value,icon,note}:{label:string;value:string;icon:React.ReactNode;note:string}) { return <Card className="metric-card"><div className="metric-top"><span>{metricLabel}</span><div className="metric-icon">{icon}</div></div><div className="metric-value">{value}</div><div className="metric-bottom">{note}</div></Card>; }
