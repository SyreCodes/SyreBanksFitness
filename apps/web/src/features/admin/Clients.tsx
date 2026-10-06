import { useDeferredValue, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, Mail, MessageSquare, Plus, Search, Users } from 'lucide-react';
import { api } from '../../services/api';
import type { ListResult } from '../../services/api';
import { useAuth } from '../../services/auth';
import { Badge, Button, Card, EmptyState, ErrorState, Field, Loading, Modal, PageHeader } from '../../components/ui';
import type { Client, Program } from './types';
import { date, exportCsv, initials, label, useList, useToast } from './shared';

export function Clients() {
  const { user } = useAuth();
  const mayCreate = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';
  const [params,setParams] = useSearchParams();
  const search = params.get('q') || '';
  const deferredSearch = useDeferredValue(search);
  const status = params.get('status') || 'ALL';
  const requestedPage = Number(params.get('page') || 1);
  const page = Number.isSafeInteger(requestedPage) && requestedPage > 0 ? requestedPage : 1;
  const pageSize = 20;
  const [create,setCreate] = useState(params.get('create') === 'true');
  const updateParams = (changes: Record<string, string | null>) => setParams(current => {
    const next = new URLSearchParams(current);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    return next;
  }, { replace: true });
  const query = new URLSearchParams({ limit: String(pageSize), offset: String((page - 1) * pageSize) });
  if (deferredSearch.trim()) query.set('search', deferredSearch.trim());
  if (status === 'NEEDS_ATTENTION') query.set('attention', 'needs_attention');
  else if (status !== 'ALL') query.set('status', status);
  const clients = useQuery({ queryKey: ['clients', deferredSearch, status, page], queryFn: () => api<ListResult<Client>>(`/clients?${query}`) });
  const rows = clients.data?.items || [];
  const total = clients.data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return <>
    <PageHeader title="Your clients" subtitle="Know the person. Guide the progress." eyebrow="Coaching" actions={<><Button variant="secondary" disabled={!rows.length} onClick={() => exportCsv('clients', [['Name','Email','Status','Goal'],...rows.map(client => [client.name,client.email,client.status,client.goal || ''])])}><Download size={15}/>Export page</Button>{mayCreate&&<Button onClick={() => setCreate(true)}><Plus size={17}/>Add client</Button>}</>}/>
    <div className="filter-bar"><div className="filters">{['ALL','NEEDS_ATTENTION','ACTIVE','ONBOARDING','PAUSED','COMPLETED','CANCELLED'].map(value => <button key={value} className={`filter-button ${status===value?'active':''}`} onClick={() => updateParams({ status: value==='ALL'?null:value, page: null })}>{value==='ALL'?'All clients':label(value)}</button>)}</div><div className="search-input"><Search size={16}/><input aria-label="Search clients" placeholder="Search name or email…" value={search} onChange={e => updateParams({ q: e.target.value, page: null })}/></div></div>
    {clients.isPending?<Loading/>:clients.isError?<ErrorState error={clients.error} retry={() => void clients.refetch()}/>:<Card className="table-card"><div className="table-wrap"><table className="data-table"><thead><tr><th>Client</th><th>Goal</th><th>Status</th><th>Joined</th><th>Adherence</th><th/></tr></thead><tbody>{rows.map((client,index) => <tr key={client.id}><td><Link to={`/admin/clients/${client.id}`} className="name-cell"><div className={`avatar ${['avatar-purple','avatar-lime','avatar-blue','avatar-orange'][index%4]}`}>{initials(client.name)}</div><div><strong>{client.name}</strong><small>{client.email}</small></div></Link></td><td>{client.goal||'Assessment pending'}</td><td>{client.attention_status==='NEEDS_ATTENTION'&&<Badge tone="warning">Needs attention</Badge>}<Badge tone={client.status==='ACTIVE'?'success':client.status==='ONBOARDING'?'lime':'neutral'}>{label(client.status)}</Badge>{client.attention_reasons?.[0]&&<small className="muted" style={{display:'block',marginTop:5}}>{client.attention_reasons[0]}</small>}</td><td>{date(client.joined_at)}</td><td>{client.adherence == null ? '—' : `${Math.round(client.adherence)}%`}</td><td><Link to={`/admin/clients/${client.id}`} className="text-link">View profile</Link></td></tr>)}</tbody></table></div>{!rows.length&&<EmptyState title={search || status!=='ALL'?'No matching clients':'Your next transformation starts here'} description={search || status!=='ALL'?'Try a different search or filter.':'Create a client account to begin their coaching journey.'} icon={<Users size={30}/>} action={!search && status==='ALL' && mayCreate && <Button onClick={() => setCreate(true)}>Add client</Button>}/>}<div className="table-footer"><span>{total ? `Showing ${(page-1)*pageSize+1}–${(page-1)*pageSize+rows.length} of ${total} clients` : '0 clients'}</span><div style={{display:'flex',gap:8,alignItems:'center'}}><Button variant="secondary" disabled={page<=1} onClick={() => updateParams({page:String(page-1)})}>Previous</Button><span>Page {page} of {totalPages}</span><Button variant="secondary" disabled={page>=totalPages} onClick={() => updateParams({page:String(page+1)})}>Next</Button></div></div></Card>}
    {mayCreate&&create&&<CreateClient onClose={() => { setCreate(false); updateParams({create:null}); }}/>}
  </>;
}
function CreateClient({onClose}:{onClose:()=>void}) {
  const {user}=useAuth();const toast=useToast();const queryClient=useQueryClient();const [error,setError]=useState('');
  const mutation=useMutation({mutationFn:(data:Record<string,string>)=>api('/clients',{method:'POST',body:JSON.stringify(data)}),onSuccess:()=>{void queryClient.invalidateQueries({queryKey:['clients']});void queryClient.invalidateQueries({queryKey:['admin-dashboard']});toast('Client account created.');onClose();},onError:(e:Error)=>setError(e.message)});
  return <Modal title="Start a new coaching journey" onClose={onClose}><form onSubmit={e=>{e.preventDefault();const form=new FormData(e.currentTarget);const data=Object.fromEntries(form.entries()) as Record<string,string>;mutation.mutate({...data,status:'ONBOARDING',assigned_coach_id:user!.id});}}><Field label="Full name"><input name="name" required minLength={2} autoComplete="name"/></Field><Field label="Email address"><input name="email" type="email" required autoComplete="email"/></Field><Field label="Initial account password" hint="At least 12 characters. Share through a secure channel."><input name="password" type="password" required minLength={12} autoComplete="new-password"/></Field><Field label="Primary goal"><select name="goal"><option>Muscle building</option><option>Fat loss</option><option>Strength</option><option>Body recomposition</option><option>Lifestyle & habits</option></select></Field>{error&&<div role="alert" className="form-error">{error}</div>}<div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={mutation.isPending}>{mutation.isPending?'Creating…':'Create client'}</Button></div></form></Modal>;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function privateValue(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() || null;
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (Array.isArray(value) && value.every(item => typeof item === 'string' || typeof item === 'number')) return value.join(', ') || null;
  return null;
}

const assessmentLabels: Record<string, string> = {
  height_cm: 'Height (cm)', weight_kg: 'Weight (kg)', target_weight_kg: 'Target weight (kg)',
  duration_minutes: 'Preferred workout duration (minutes)', sleep_hours: 'Sleep (hours)',
};
const healthFlagKeys = new Set(['heart_condition', 'chest_pain', 'dizziness', 'injury', 'medical_restriction', 'other_condition']);

function PrivateFacts({title, values, health = false}: {title: string; values: Record<string, unknown> | null; health?: boolean}) {
  const rows = Object.entries(values || {}).filter(([, value]) => privateValue(value) !== null);
  return <section style={{marginTop:24}}><h3 style={{marginBottom:12}}>{title}</h3>{rows.length ? <dl className="detail-list">{rows.map(([key, value]) => <div key={key}><dt>{assessmentLabels[key] || label(key)}</dt><dd>{health && healthFlagKeys.has(key) && value === true ? <Badge tone="warning">Yes — review</Badge> : privateValue(value)}</dd></div>)}</dl> : <p className="account-note">No information submitted yet.</p>}</section>;
}

function PrivateAssessment({profile}: {profile?: Record<string, unknown>}) {
  const assessment = asRecord(profile?.assessment);
  const health = asRecord(profile?.health_screening);
  return <div className="privacy-note" style={{marginTop:20}}>
    <p>Private client information. Use these answers to adapt coaching and follow up with the client.</p>
    {profile?.review_required === true && <div className="notice" role="status" style={{marginTop:12}}>Health screening needs coach review. Advise the client to seek qualified medical guidance when appropriate.</div>}
    <PrivateFacts title="Fitness assessment" values={assessment}/>
    <PrivateFacts title="Health screening" values={health} health/>
  </div>;
}

export function ClientDetail() {
  const {id}=useParams();const toast=useToast();const queryClient=useQueryClient();const [tab,setTab]=useState('Overview');const [status,setStatus]=useState('');
  const query=useQuery({queryKey:['client',id],queryFn:()=>api<Client>(`/clients/${id}`)});
  const programs=useList<Program>('/programs','programs');
  const mutation=useMutation({mutationFn:(values:Record<string,string>)=>api(`/clients/${id}`,{method:'PATCH',body:JSON.stringify(values)}),onSuccess:()=>{void queryClient.invalidateQueries({queryKey:['client',id]});void queryClient.invalidateQueries({queryKey:['clients']});toast('Client profile updated.');}});
  const assign=useMutation({mutationFn:(programId:string)=>api(`/programs/${programId}/assign`,{method:'POST',body:JSON.stringify({client_id:id})}),onSuccess:()=>{toast('Program assigned as a personal snapshot.');void queryClient.invalidateQueries({queryKey:['client',id]});}});
  if(query.isPending)return <Loading/>;if(query.isError)return <ErrorState error={query.error}/>;const client=query.data;
  return <><Link className="text-link" to="/admin/clients" style={{marginBottom:18}}>Back to clients</Link><div className="client-detail-hero"><div className="avatar avatar-lime">{initials(client.name)}</div><div className="client-detail-info"><h1>{client.name}</h1><p>{client.email} · {client.goal || 'Assessment pending'}</p></div><Badge tone={client.status==='ACTIVE'?'success':'neutral'}>{label(client.status)}</Badge><Link to={`/admin/messages?client=${id}`} className="button button-secondary" style={{marginLeft:'auto'}}><MessageSquare size={15}/>Message client</Link></div><div className="tabs">{['Overview','Profile','Programs','Notes'].map(value=><button key={value} className={tab===value?'active':''} onClick={()=>setTab(value)}>{value}</button>)}</div>
    {tab==='Overview'&&<div className="two-column"><Card><div className="section-heading"><h2>The person behind the progress</h2></div><dl className="detail-list"><div><dt>Current goal</dt><dd>{client.goal||'Not set'}</dd></div><div><dt>Client since</dt><dd>{date(client.joined_at)}</dd></div><div><dt>Workout adherence</dt><dd>{client.adherence == null ? '—' : `${Math.round(client.adherence)}%`}</dd></div><div><dt>Lifecycle</dt><dd>{label(client.status)}</dd></div></dl><div className="form-actions"><a className="button button-secondary" href={`mailto:${client.email}`}><Mail size={15}/>Email client</a></div></Card><Card><h2>Coaching attention</h2>{client.attention_reasons?.length?<div className="stack" style={{marginTop:20}}>{client.attention_reasons.map(reason=><div className="notice" key={reason}>{reason}</div>)}</div>:<EmptyState title="Keep checking in" description="This client's adherence and missed check-ins inform the coaching attention status."/>}</Card></div>}
    {tab==='Profile'&&<Card className="settings-section"><h2 style={{marginBottom:20}}>Client profile</h2><form onSubmit={e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.currentTarget).entries()) as Record<string,string>;mutation.mutate(data);}}><Field label="Primary goal"><input name="goal" defaultValue={client.goal}/></Field><Field label="Client lifecycle"><select name="status" value={status||client.status} onChange={e=>setStatus(e.target.value)}>{['PROSPECT','ONBOARDING','ACTIVE','PAUSED','COMPLETED','CANCELLED'].map(value=><option key={value}>{value}</option>)}</select></Field><PrivateAssessment profile={client.profile}/>{mutation.isError&&<div className="form-error">{mutation.error.message}</div>}<div className="form-actions"><Button disabled={mutation.isPending}>Save profile</Button></div></form></Card>}
    {tab==='Programs'&&<Card className="settings-section"><h2>Assign a personal program</h2><p className="account-note">A snapshot preserves the client’s program when you edit the reusable template later.</p><form onSubmit={e=>{e.preventDefault();const data=new FormData(e.currentTarget);assign.mutate(String(data.get('program_id')));}}><Field label="Program template"><select name="program_id" required><option value="">Choose a program</option>{programs.data?.items.map(program=><option value={program.id} key={program.id}>{program.name} · {program.weeks} weeks</option>)}</select></Field>{assign.isError&&<div className="form-error">{assign.error.message}</div>}<Button disabled={assign.isPending||!programs.data?.items.length}>Assign program</Button></form></Card>}
    {tab==='Notes'&&<Card><h2>Private coach notes</h2><p className="account-note">Notes stay inside this coaching workspace.</p><form onSubmit={e=>{e.preventDefault();const value=new FormData(e.currentTarget).get('notes');mutation.mutate({notes:String(value)});}}><Field label="Notes"><textarea name="notes" defaultValue={String(client.profile?.notes||'')} rows={6}/></Field>{mutation.isError&&<div className="form-error">{mutation.error.message}</div>}<Button disabled={mutation.isPending}>Save notes</Button></form></Card>}
  </>;
}
