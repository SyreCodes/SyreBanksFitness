import type { Assignment, WorkoutSession } from './types';
export function dateInZone(date: Date, timezone: string) { const parts = new Intl.DateTimeFormat('en', { timeZone: timezone, year:'numeric',month:'2-digit',day:'2-digit' }).formatToParts(date); const value = (type:string) => parts.find(p=>p.type===type)?.value; return `${value('year')}-${value('month')}-${value('day')}`; }
export function weekActivity(sessions:WorkoutSession[], now:Date, timezone:string) {
  const local = new Date(dateInZone(now,timezone)+'T12:00:00Z');const monday = new Date(local);monday.setUTCDate(local.getUTCDate()-((local.getUTCDay()+6)%7));
  return Array.from({length:7},(_,i)=>{const date=new Date(monday);date.setUTCDate(monday.getUTCDate()+i);const key=date.toISOString().slice(0,10);return { day:date.toLocaleDateString('en',{weekday:'short',timeZone:'UTC'}),sessions:sessions.filter(s=>s.completed&&dateInZone(new Date(s.created_at),timezone)===key).length };});
}
function dayName(value: string | number | undefined) { return typeof value === 'number' ? ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][value - 1] : value?.toLowerCase().trim(); }
export function todaysMission(assignments:Assignment[],sessions:WorkoutSession[],now:Date,timezone:string){
  const assignment=assignments.find(a=>a.status==='ACTIVE'&&(!a.starts_at||new Date(a.starts_at)<=now));
  const day=new Intl.DateTimeFormat('en',{weekday:'long',timeZone:timezone}).format(now).toLowerCase();const date=dateInZone(now,timezone);
  const workouts=assignment?.snapshot.workouts||[];const scheduled=workouts.filter(w=>dayName(w.day)===day);
  const doneToday=(id:string)=>sessions.some(s=>s.assignment_id===assignment?.id&&s.workout_id===id&&s.completed&&dateInZone(new Date(s.created_at),timezone)===date);
  const flexible=workouts.filter(w=>!w.day||!['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].includes(dayName(w.day) || ''));
  const workout=scheduled.find(w=>!doneToday(w.id)) || flexible.find(w=>!doneToday(w.id));
  return {assignment,workout,scheduled:scheduled.length>0,completed:scheduled.length>0&&scheduled.every(w=>doneToday(w.id))};
}
