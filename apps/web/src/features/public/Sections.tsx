import { useState } from 'react';
import { useCatalog, cleanText, goals } from '../launch/data';
import { CurrencyControl, PackageTile, QueryState } from '../launch/components';
import { Link } from 'react-router-dom';
import { ArrowUpRight, Dumbbell, Flame, Target, TrendingUp, Sprout, Repeat2, ArrowRight } from 'lucide-react';
import { publicCopy, usePublicContent, type Exercise } from './content';
import { ExerciseDemonstration } from './ExerciseDemonstration';

const goalIcons = [Dumbbell, Flame, TrendingUp, Target, Sprout, Repeat2];


export function GoalCards({ limit }: { limit?: number }) {
  return <div className="sb-goals-grid">{goals.slice(0, limit).map(([name, description], index) => { const Icon = goalIcons[index]; return <Link className="sb-goal-card" key={name} to={`/programs?goal=${encodeURIComponent(name)}`}><div className="sb-goal-top"><Icon size={27} strokeWidth={1.5} /><span>{String(index + 1).padStart(2, '0')}</span></div><h3>{name}</h3><p>{description}</p><span className="sb-goal-link">Find your direction <ArrowUpRight size={18} /></span></Link>; })}</div>;
}

export function PricingCards() {
  const query = useCatalog(); const [currency, setCurrency] = useState('RWF');
  return <><CurrencyControl value={currency} onChange={setCurrency}/><QueryState query={query}>{query.data?.items.filter(p => p.type !== 'DIGITAL').length ? <div className="launch-grid">{query.data.items.filter(p => p.type !== 'DIGITAL').slice(0,3).map(p => <PackageTile key={p.id} product={p} currency={currency}/>)}</div> : <div className="sb-empty"><h3>Let’s find the right support.</h3><p>Packages are being prepared. Tell us your goals and discuss your options.</p><Link className="sb-text-link" to="/apply?kind=CONSULTATION">Request a consultation <ArrowUpRight size={18}/></Link></div>}</QueryState></>;
}

export function ExerciseCards({ exercises }: { exercises: Exercise[] }) {
  return <div className="sb-exercise-grid">{exercises.map(exercise => <article className="sb-exercise-card" key={exercise.id}><div className="sb-exercise-art">{exercise.image_url ? <img src={exercise.image_url} alt={exercise.name} loading="lazy" /> : <Dumbbell size={53} strokeWidth={1} />}<span>{exercise.difficulty || 'Training fundamentals'}</span></div><div className="sb-exercise-body"><div className="sb-exercise-tags"><span>{exercise.muscle_group || 'Full body'}</span><span>{exercise.equipment || 'Technique first'}</span></div><h3>{exercise.name}</h3><p>{exercise.description || 'Learn the movement and build your training foundation.'}</p>{exercise.video_url ? <ExerciseDemonstration name={exercise.name} videoUrl={exercise.video_url} videoMediaId={exercise.video_media_id} linkClassName="sb-text-link" linkText="Watch demonstration" /> : <span className="sb-exercise-no-video">Written instructions available in the library</span>}</div></article>)}</div>;
}

export function FaqList({ limit }: { limit?: number }) {
  const content = usePublicContent();
  const entries = content.faq?.filter(faq => faq.question && faq.answer);
  return <div className="sb-faq-list">{(entries?.length ? entries : publicCopy.faq).slice(0, limit).map((faq, index) => <details key={faq.question}><summary><span><em>{String(index + 1).padStart(2, '0')}</em>{faq.question}</span><span className="sb-faq-plus" aria-hidden="true">+</span></summary><p>{faq.answer}</p></details>)}</div>;
}

export function CallToAction() {
  return <section className="sb-final-cta"><div className="sb-container"><div><p className="sb-kicker">THE FIRST REP IS A DECISION</p><h2>YOUR NEXT CHAPTER.<br /><span>STARTS WITH YOU.</span></h2></div><div><p>You bring the commitment.<br />We bring the plan and accountability.</p><Link className="sb-button sb-button-dark" to="/apply">Let's build it together <ArrowUpRight size={20} /></Link></div></div></section>;
}

export function SectionHeading({ eyebrow, title, description, link, linkLabel }: { eyebrow: string; title: string; description?: string; link?: string; linkLabel?: string }) {
  return <div className="sb-section-heading"><div><p className="sb-kicker">{eyebrow}</p><h2 className="preserve-lines">{cleanText(title)}</h2>{description && <p className="sb-section-description">{description}</p>}</div>{link && <Link className="sb-text-link" to={link}>{linkLabel || 'Explore more'} <ArrowRight size={18} /></Link>}</div>;
}
