import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, ShieldCheck, Users as UsersIcon } from 'lucide-react';
import { api } from '../../services/api';
import type { ListResult } from '../../services/api';
import { useAuth } from '../../services/auth';
import { Badge, Button, Card, EmptyState, ErrorState, Field, Loading, Modal, PageHeader } from '../../components/ui';
import type { AdminUser, Audit } from './types';
import { date, label, useToast } from './shared';

const roles: AdminUser['role'][] = ['SUPER_ADMIN', 'ADMIN', 'COACH', 'CLIENT', 'LEAD'];
const pageSize = 20;
function historyDetail(event: Audit): string {
  if (event.details?.previous_role && event.details.new_role) return label(event.details.previous_role) + ' → ' + label(event.details.new_role);
  if (typeof event.details?.new_active === 'boolean') return event.details.new_active ? 'Account activated' : 'Account deactivated';
  return '';
}

export function Users() {
  const [draftSearch, setDraftSearch] = useState('');
  const [search, setSearch] = useState('');
  const [role, setRole] = useState('');
  const [active, setActive] = useState('');
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<AdminUser | null>(null);
  const params = new URLSearchParams({ limit: String(pageSize), offset: String(page * pageSize) });
  if (search) params.set('search', search);
  if (role) params.set('role', role);
  if (active) params.set('active', active);
  const query = useQuery({
    queryKey: ['admin-users', search, role, active, page],
    queryFn: () => api<ListResult<AdminUser>>('/admin/users?' + params.toString()),
  });
  const total = query.data?.total ?? 0;
  return <>
    <PageHeader eyebrow="User management" title="People behind the platform" subtitle="Review account access and keep each role appropriate." />
    <Card className="user-filter-card">
      <form className="user-filter-form" onSubmit={event => { event.preventDefault(); setPage(0); setSearch(draftSearch.trim()); }}>
        <div className="search-input"><Search size={16}/><input aria-label="Search users" placeholder="Search name or email…" value={draftSearch} onChange={event => setDraftSearch(event.target.value)}/></div>
        <select aria-label="Filter users by role" value={role} onChange={event => { setRole(event.target.value); setPage(0); }}><option value="">All roles</option>{roles.map(value => <option value={value} key={value}>{label(value)}</option>)}</select>
        <select aria-label="Filter users by status" value={active} onChange={event => { setActive(event.target.value); setPage(0); }}><option value="">All account states</option><option value="true">Active</option><option value="false">Deactivated</option></select>
        <Button variant="secondary" type="submit">Search</Button>
      </form>
    </Card>
    {query.isPending ? <Loading/> : query.isError ? <ErrorState error={query.error} retry={() => { void query.refetch(); }}/> : <Card className="table-card">
      <div className="table-wrap"><table className="data-table">
        <thead><tr><th>Name</th><th>Role</th><th>Account</th><th>Email</th><th>Joined</th><th/></tr></thead>
        <tbody>{query.data.items.map(account => <tr key={account.id}>
          <td><strong>{account.name}</strong><small className="user-email">{account.email}</small></td>
          <td><Badge tone={account.role === 'SUPER_ADMIN' || account.role === 'ADMIN' ? 'lime' : 'neutral'}>{label(account.role)}</Badge></td>
          <td><Badge tone={account.active ? 'success' : 'danger'}>{account.active ? 'Active' : 'Deactivated'}</Badge></td>
          <td>{account.email_verified ? 'Verified' : 'Unverified'}</td>
          <td>{date(account.created_at)}</td>
          <td><Button variant="ghost" onClick={() => setSelected(account)}>Review access</Button></td>
        </tr>)}</tbody>
      </table></div>
      {!query.data.items.length && <EmptyState title="No matching accounts" description="Try a different name, role, or account state." icon={<UsersIcon size={28}/>}/>}
      <div className="table-footer"><span>{total} accounts</span><div><Button variant="ghost" disabled={page === 0} onClick={() => setPage(value => value - 1)}>Previous</Button><span>Page {page + 1} of {Math.max(1, Math.ceil(total / pageSize))}</span><Button variant="ghost" disabled={(page + 1) * pageSize >= total} onClick={() => setPage(value => value + 1)}>Next</Button></div></div>
    </Card>}
    {selected && <UserEditor key={selected.id} account={selected} onClose={() => setSelected(null)}/>}
  </>;
}

function UserEditor({ account, onClose }: { account: AdminUser; onClose: () => void }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [role, setRole] = useState<AdminUser['role']>(account.role);
  const [active, setActive] = useState(account.active);
  const [confirm, setConfirm] = useState(false);
  const isSelf = account.id === user?.id;
  const changed = role !== account.role || active !== account.active;
  const history = useQuery({
    queryKey: ['admin-user-history', account.id],
    queryFn: () => api<ListResult<Audit>>('/audit?resource_type=User&resource_id=' + encodeURIComponent(account.id) + '&limit=20'),
  });
  const mutation = useMutation({
    mutationFn: () => api<AdminUser>('/admin/users/' + account.id, { method: 'PATCH', body: JSON.stringify({ role, active }) }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin-users'] });
      void queryClient.invalidateQueries({ queryKey: ['audit'] });
      toast('Account access updated.');
      onClose();
    },
  });
  return <Modal title={'Manage ' + account.name} onClose={onClose}>
    <div className="user-account-summary"><div><strong>{account.email}</strong><span>Joined {date(account.created_at)} · {account.email_verified ? 'Email verified' : 'Email unverified'}</span></div><Badge tone={account.active ? 'success' : 'danger'}>{account.active ? 'Active' : 'Deactivated'}</Badge></div>
    {!confirm ? <form onSubmit={event => { event.preventDefault(); if (changed && !isSelf) setConfirm(true); }}>
      <Field label="Role"><select value={role} disabled={isSelf} onChange={event => setRole(event.target.value as AdminUser['role'])}>{roles.map(value => <option value={value} key={value}>{label(value)}</option>)}</select></Field>
      <Field label="Account state"><select value={active ? 'active' : 'inactive'} disabled={isSelf} onChange={event => setActive(event.target.value === 'active')}><option value="active">Active</option><option value="inactive">Deactivated</option></select></Field>
      {isSelf && <p className="account-note">Your own administrator access cannot be changed here.</p>}
      <div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Close</Button><Button disabled={!changed || isSelf}>Review changes</Button></div>
    </form> : <div className="user-confirm">
      <ShieldCheck size={26}/>
      <h3>Confirm this access change</h3>
      <p>{account.name} will have the <strong>{label(role)}</strong> role and an <strong>{active ? 'active' : 'deactivated'}</strong> account. Deactivating an account ends its current sessions.</p>
      {mutation.isError && <div className="form-error" role="alert">{mutation.error.message}</div>}
      <div className="form-actions"><Button variant="secondary" onClick={() => setConfirm(false)}>Back</Button><Button variant="danger" disabled={mutation.isPending} onClick={() => mutation.mutate()}>{mutation.isPending ? 'Saving…' : 'Confirm access change'}</Button></div>
    </div>}
    <div className="user-history"><h3>Account history</h3>{history.isPending ? <Loading label="Loading account history…"/> : history.isError ? <ErrorState error={history.error} retry={() => { void history.refetch(); }}/> : history.data.items.length ? <div className="user-history-list">{history.data.items.map(event => <div key={event.id}><span>{label(event.action)}{historyDetail(event) && <small>{historyDetail(event)}</small>}</span><small>{date(event.created_at)} · {event.actor_name || 'System'}</small></div>)}</div> : <p className="muted">No recorded account changes yet.</p>}</div>
  </Modal>;
}
