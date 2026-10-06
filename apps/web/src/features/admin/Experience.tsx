import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck, MessageSquare, Send } from 'lucide-react';
import { api, type ListResult } from '../../services/api';
import { useAuth } from '../../services/auth';
import { Badge, Button, Card, EmptyState, ErrorState, Field, Loading, Modal, PageHeader } from '../../components/ui';
import type { Checkin, Client, Message } from './types';
import { date, initials, label, useList, useToast } from './shared';

export function Checkins(){const query=useList<Checkin>('/checkins','checkins');const [selected,setSelected]=useState<Checkin|null>(null);const [filter,setFilter]=useState('SUBMITTED');const rows=query.data?.items.filter(item=>filter==='ALL'||item.status===filter)||[];return <><PageHeader title="Listen. Adjust. Keep moving." subtitle="Your clients’ week, in their own words." eyebrow="Weekly check-ins" actions={<Badge tone="warning">{query.data?.items.filter(item=>item.status==='SUBMITTED').length??0} awaiting review</Badge>}/><div className="filters" style={{marginBottom:22}}>{['SUBMITTED','REVIEWED','ALL'].map(value=><button className={`filter-button ${filter===value?'active':''}`} key={value} onClick={()=>setFilter(value)}>{value==='ALL'?'All check-ins':label(value)}</button>)}</div>{query.isPending?<Loading/>:query.isError?<ErrorState error={query.error}/>:!rows.length?<Card><EmptyState title="A little space to reflect" description="Submitted weekly check-ins will appear here for your review." icon={<ClipboardCheck size={30}/>}/></Card>:<Card className="table-card"><div className="table-wrap"><table className="data-table"><thead><tr><th>Client</th><th>Submitted</th><th>Energy</th><th>Weight</th><th>Status</th><th/></tr></thead><tbody>{rows.map(item=><tr key={item.id}><td><div className="name-cell"><div className="avatar avatar-lime">{initials(item.client_name||'Client')}</div><strong>{item.client_name||'Client'}</strong></div></td><td>{date(item.created_at)}</td><td>{String(item.energy??item.answers?.energy??'—')}/5</td><td>{String(item.weight??item.answers?.weight_kg??'—')} kg</td><td><Badge tone={item.status==='REVIEWED'?'success':'warning'}>{label(item.status)}</Badge></td><td><Button variant="secondary" onClick={()=>setSelected(item)}>{item.status==='REVIEWED'?'View':'Review'}</Button></td></tr>)}</tbody></table></div></Card>}{selected&&<CheckinReview checkin={selected} onClose={()=>setSelected(null)}/>}</>;}
function CheckinReview({checkin,onClose}:{checkin:Checkin;onClose:()=>void}){const toast=useToast();const qc=useQueryClient();const [feedback,setFeedback]=useState(checkin.coach_feedback||'');const mutation=useMutation({mutationFn:()=>api(`/checkins/${checkin.id}`,{method:'PATCH',body:JSON.stringify({coach_feedback:feedback,status:'REVIEWED'})}),onSuccess:()=>{void qc.invalidateQueries({queryKey:['checkins']});void qc.invalidateQueries({queryKey:['admin-dashboard']});toast('Feedback saved for your client.');onClose();}});const answers=checkin.answers||{};return <Modal title={`${checkin.client_name||'Client'}’s check-in`} onClose={onClose}><p className="muted" style={{fontSize:'.8rem'}}>Submitted {date(checkin.created_at)}</p><div className="checkin-review">{[['Weight',checkin.weight??answers.weight_kg,'kg'],['Energy',checkin.energy??answers.energy,'/5'],['Sleep',checkin.sleep??answers.sleep,'/5']].map(([title,value,unit])=><div className="checkin-score" key={String(title)}>{String(title)}<strong>{String(value??'—')} <small>{String(unit)}</small></strong></div>)}</div>{[['Wins this week',checkin.wins??answers.wins],['Challenges',checkin.challenges??answers.challenges],['Questions',checkin.questions??answers.questions]].map(([title,value])=><div className="checkin-text" key={String(title)}><strong>{String(title)}</strong><p>{String(value||'Nothing added.')}</p></div>)}<Field label="Your coaching feedback"><textarea value={feedback} onChange={e=>setFeedback(e.target.value)} rows={4} placeholder="Recognize the effort. Give one clear next step."/></Field>{mutation.isError&&<div className="form-error">{mutation.error.message}</div>}<div className="form-actions"><Button disabled={!feedback.trim()||mutation.isPending} onClick={()=>mutation.mutate()}>Send feedback & mark reviewed</Button></div></Modal>;}

export function Messages(){
  const clients=useList<Client>('/clients','clients');
  const [params]=useSearchParams();
  const [selectedId,setSelectedId]=useState(params.get('client')||'');
  const [body,setBody]=useState('');
  const {user}=useAuth();
  const qc=useQueryClient();
  const selected=clients.data?.items.find(client=>client.id===selectedId)||clients.data?.items[0];
  const messages=useInfiniteQuery({
    queryKey:['messages',selected?.id],
    queryFn:({pageParam})=>api<ListResult<Message>>('/messages?client_id='+encodeURIComponent(selected!.id)+'&limit=50&offset='+pageParam),
    initialPageParam:0,
    getNextPageParam:(lastPage,allPages)=>allPages.length*50<lastPage.total?allPages.length*50:undefined,
    enabled:Boolean(selected),
  });
  const thread=messages.data?.pages.flatMap(page=>page.items).sort((a,b)=>a.created_at.localeCompare(b.created_at))||[];
  const send=useMutation({mutationFn:()=>api('/messages',{method:'POST',body:JSON.stringify({recipient_id:selected?.id,body})}),onSuccess:()=>{setBody('');void qc.invalidateQueries({queryKey:['messages']});}});
  return <><PageHeader title="A conversation can change a week." subtitle="Stay close to the people you coach." eyebrow="Messages"/>
    {clients.isPending||(selected&&messages.isPending)?<Loading/>:clients.isError||(selected&&messages.isLoadingError)?<ErrorState error={clients.error||messages.error}/>:!selected?<Card><EmptyState title="Your coaching conversations live here" description="Add your first client to start a conversation." icon={<MessageSquare size={30}/>}/></Card>:<div className="message-layout">
      <div className="conversation-list">{clients.data?.items.map(client=><button className={'conversation-button '+(client.id===selected.id?'active':'')} key={client.id} onClick={()=>setSelectedId(client.id)}><div className="avatar avatar-lime">{initials(client.name)}</div><div><strong>{client.name}</strong><small>{client.goal||'Coaching client'}</small></div></button>)}</div>
      <div className="message-panel"><div className="message-panel-head">{selected.name}</div>
        <div className="message-bubbles">
          {messages.hasNextPage&&<Button type="button" variant="secondary" disabled={messages.isFetchingNextPage} onClick={()=>void messages.fetchNextPage()}>{messages.isFetchingNextPage?'Loading…':'Load earlier messages'}</Button>}
          {messages.isFetchNextPageError&&<div className="form-error" role="alert">Older messages could not be loaded. <Button type="button" variant="secondary" onClick={()=>void messages.fetchNextPage()}>Retry</Button></div>}
          {thread.length?thread.map(message=><div key={message.id} className={'message-bubble '+(message.sender_id===user?.id?'sent':'')}><p>{message.body}</p><small>{new Date(message.created_at).toLocaleString('en-GB',{day:'numeric',month:'short',hour:'2-digit',minute:'2-digit',timeZone:'Africa/Kigali'})}</small></div>):<EmptyState title="Start with a simple hello" description="Coaching messages stay private between you and this client."/>}
        </div>
        {send.isError&&<div className="form-error" style={{margin:'0 20px'}}>{send.error.message}</div>}
        <form className="message-compose" onSubmit={e=>{e.preventDefault();if(body.trim())send.mutate();}}><input aria-label="Message" value={body} onChange={e=>setBody(e.target.value)} placeholder={'Message '+selected.name.split(' ')[0]+'…'} maxLength={5000}/><Button disabled={!body.trim()||send.isPending}><Send size={16}/>Send</Button></form>
      </div>
    </div>}
  </>;
}

export { Calendar } from './AdminCalendar'
