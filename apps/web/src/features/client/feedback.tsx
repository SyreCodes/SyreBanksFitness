import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Bug, ChevronUp, Heart, Lightbulb, MessageSquare, Plus, Search, Sparkles } from 'lucide-react';
import { Badge, Button, Card, EmptyState, ErrorState, Field, Loading, Modal } from '../../components/ui';
import { api, type ListResult } from '../../services/api';
import { useAuth } from '../../services/auth';
import { ClientHeader, formatDate } from './common';
import './feedback.css';

export const feedbackStatuses = ['SUBMITTED', 'REVIEWING', 'PLANNED', 'IN_PROGRESS', 'COMPLETED', 'DECLINED'] as const;
const categories = ['idea', 'feature', 'bug', 'compliment', 'general'] as const;
const categoryLabels: Record<string, string> = { idea: 'Idea', feature: 'Feature request', bug: 'Bug report', compliment: 'Compliment', general: 'General feedback' };
export const feedbackStatusLabels: Record<string, string> = { SUBMITTED: 'Submitted', REVIEWING: 'Under review', PLANNED: 'Planned', IN_PROGRESS: 'In progress', COMPLETED: 'Completed', DECLINED: 'Declined' };
const categoryIcons = { idea: Lightbulb, feature: Sparkles, bug: Bug, compliment: Heart, general: MessageSquare };

export type FeedbackPost = {
  id: string; title: string; description: string; category: typeof categories[number]; status: typeof feedbackStatuses[number];
  owner_name: string; own_post: boolean; coach_response: string; vote_count: number; voted: boolean; created_at: string; updated_at: string;
};

const createSchema = z.object({ title: z.string().trim().min(3, 'Give your idea a clear title (at least 3 characters).').max(160), description: z.string().trim().min(10, 'Add a little detail (at least 10 characters).').max(5000), category: z.enum(categories) });
type NewFeedback = z.infer<typeof createSchema>;

export function FeedbackPage() {
  return <><ClientHeader eyebrow="YOUR VOICE MATTERS" title="Help shape your coaching experience." subtitle="Share ideas, report a problem, and support the changes that matter to you." /><FeedbackBoard /></>;
}

export function FeedbackBoard({ admin = false }: { admin?: boolean }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const canReview = admin && ['ADMIN', 'SUPER_ADMIN'].includes(user?.role || '');
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<FeedbackPost | null>(null);
  const [notice, setNotice] = useState('');
  const params = new URLSearchParams({ limit: '20', offset: String(offset) });
  if (search.trim()) params.set('search', search.trim());
  if (category) params.set('category', category);
  if (status) params.set('status', status);
  const query = useQuery({ queryKey: ['feedback', user?.id, search, category, status, offset], queryFn: () => api<ListResult<FeedbackPost>>(`/feedback?${params.toString()}`) });
  const vote = useMutation({ mutationFn: (values: { id: string; voted: boolean }) => api<FeedbackPost>(`/feedback/${values.id}/vote`, { method: 'POST', body: JSON.stringify({ voted: values.voted }) }), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['feedback'] }); } });
  const filterChanged = () => { setOffset(0); setNotice(''); };

  return <div className="feedback-board"><div className="feedback-intro-note"><Lightbulb size={20} /><p>Ideas here are visible to the coaching community. For personal coaching or health questions, use your private coach messages.</p></div><div className="feedback-toolbar"><label className="feedback-search"><Search size={18} /><input type="search" aria-label="Search feedback" placeholder="Search ideas and feedback" maxLength={100} value={search} onChange={event => { setSearch(event.target.value); filterChanged(); }} /></label><label className="feedback-filter"><span>Category</span><select value={category} onChange={event => { setCategory(event.target.value); filterChanged(); }}><option value="">All categories</option>{categories.map(value => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></label>{admin && <label className="feedback-filter"><span>Status</span><select value={status} onChange={event => { setStatus(event.target.value); filterChanged(); }}><option value="">All statuses</option>{feedbackStatuses.map(value => <option key={value} value={value}>{feedbackStatusLabels[value]}</option>)}</select></label>}<Button onClick={() => setCreating(true)}><Plus size={17} />Share an idea</Button></div>{notice && <div className="feedback-notice" role="status">{notice}</div>}{vote.isError && <div className="feedback-error" role="alert">{vote.error.message}</div>}{query.isPending ? <Loading label="Loading ideas and feedback…" /> : query.isError ? <ErrorState error={query.error} retry={() => void query.refetch()} /> : query.data.items.length === 0 ? <Card><EmptyState icon={<Lightbulb size={34} />} title={search || category || status ? 'No matching feedback.' : 'A better experience starts with an idea.'} description={search || category || status ? 'Try another search or filter.' : 'Share what would make your coaching experience more useful. The team can respond here.'} action={!search && !category && !status ? <Button onClick={() => setCreating(true)}>Share the first idea <Plus size={16} /></Button> : undefined} /></Card> : <><div className="feedback-post-list">{query.data.items.map(post => { const Icon = categoryIcons[post.category]; return <Card className="feedback-post" key={post.id}><button className={`feedback-vote ${post.voted ? 'feedback-voted' : ''}`} disabled={vote.isPending} onClick={() => vote.mutate({ id: post.id, voted: !post.voted })} aria-pressed={post.voted} aria-label={`${post.voted ? 'Remove support for' : 'Support'} ${post.title}`}><ChevronUp size={21} /><strong>{vote.isPending && vote.variables.id === post.id ? '…' : post.vote_count}</strong><span>{post.vote_count === 1 ? 'vote' : 'votes'}</span></button><div className="feedback-post-content"><div className="feedback-post-tags"><Badge><Icon size={13} />{categoryLabels[post.category]}</Badge><Badge tone={post.status === 'COMPLETED' ? 'success' : post.status === 'IN_PROGRESS' || post.status === 'PLANNED' ? 'lime' : 'neutral'}>{feedbackStatusLabels[post.status]}</Badge></div><h2>{post.title}</h2><p className="feedback-description">{post.description}</p><div className="feedback-post-meta"><span>{post.own_post ? 'Shared by you' : `Shared by ${post.owner_name}`}</span><span>{formatDate(post.created_at)}</span>{canReview && <button onClick={() => setSelected(post)}>Review & respond</button>}</div>{post.coach_response && <div className="feedback-response"><MessageSquare size={18} /><div><strong>Team response</strong><p>{post.coach_response}</p></div></div>}</div></Card>; })}</div><div className="feedback-pagination"><span>{offset + 1}–{Math.min(offset + 20, query.data.total)} of {query.data.total} posts</span><div><Button variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</Button><Button variant="secondary" disabled={offset + 20 >= query.data.total} onClick={() => setOffset(offset + 20)}>Next</Button></div></div></>}{creating && <NewFeedbackModal onClose={() => setCreating(false)} onSaved={() => { setCreating(false); setSearch(''); setCategory(''); setStatus(''); setOffset(0); setNotice('Your feedback is saved. The coaching community can now view it.'); }} />}{selected && canReview && <FeedbackReview post={selected} onClose={() => setSelected(null)} onSaved={() => { setSelected(null); setNotice('The feedback status and public response have been updated.'); }} />}</div>;
}

function NewFeedbackModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient();
  const form = useForm<NewFeedback>({ resolver: zodResolver(createSchema), defaultValues: { title: '', description: '', category: 'idea' } });
  const save = useMutation({ mutationFn: (data: NewFeedback) => api<FeedbackPost>('/feedback', { method: 'POST', body: JSON.stringify(data) }), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['feedback'] }); onSaved(); } });
  return <Modal title="Share an idea" onClose={onClose}><p className="feedback-modal-description">Tell the team what would help you. Your title and description will be visible to coaching clients and staff.</p><form className="feedback-form" onSubmit={form.handleSubmit(values => save.mutate(values))}><Field label="A clear title" error={form.formState.errors.title?.message}><input aria-label="A clear title" {...form.register('title')} maxLength={160} placeholder="What could make the experience better?" /></Field><Field label="Category"><select aria-label="Feedback category" {...form.register('category')}>{categories.map(value => <option key={value} value={value}>{categoryLabels[value]}</option>)}</select></Field><Field label="Tell us more" error={form.formState.errors.description?.message}><textarea aria-label="Tell us more" {...form.register('description')} maxLength={5000} rows={5} placeholder="Explain the idea, or what happened and what you expected." /></Field>{save.isError && <div className="feedback-error" role="alert">{save.error.message}</div>}<div className="form-actions"><Button type="button" variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={save.isPending}>{save.isPending ? 'Sharing…' : 'Share feedback'}</Button></div></form></Modal>;
}

function FeedbackReview({ post, onClose, onSaved }: { post: FeedbackPost; onClose: () => void; onSaved: () => void }) {
  const queryClient = useQueryClient();
  const form = useForm<{ status: FeedbackPost['status']; coach_response: string }>({ defaultValues: { status: post.status, coach_response: post.coach_response } });
  const save = useMutation({ mutationFn: (data: { status: FeedbackPost['status']; coach_response: string }) => api(`/feedback/${post.id}`, { method: 'PATCH', body: JSON.stringify(data) }), onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['feedback'] }); onSaved(); } });
  return <Modal title="Review feedback" onClose={onClose}><div className="feedback-review-summary"><h3>{post.title}</h3><p>{post.description}</p></div><form className="feedback-form" onSubmit={form.handleSubmit(data => save.mutate(data))}><Field label="Status"><select aria-label="Feedback status" {...form.register('status')}>{feedbackStatuses.map(value => <option key={value} value={value}>{feedbackStatusLabels[value]}</option>)}</select></Field><Field label="Public team response" hint="Visible to all coaching clients and staff."><textarea aria-label="Public team response" {...form.register('coach_response', { maxLength: 6000 })} maxLength={6000} rows={5} placeholder="Explain the decision or next step." /></Field>{save.isError && <div className="feedback-error" role="alert">{save.error.message}</div>}<div className="form-actions"><Button variant="secondary" type="button" onClick={onClose}>Cancel</Button><Button disabled={save.isPending}>{save.isPending ? 'Saving…' : 'Publish response'}</Button></div></form></Modal>;
}
