import { Link } from 'react-router-dom';
import { ArrowUpRight, Check, Dumbbell, Flame, Target, TrendingUp, Sprout, Repeat2, ArrowRight } from 'lucide-react';
import { ErrorState, Loading } from '../../components/ui';
import { publicCopy, useProducts, usePublicContent, formatPrice, type Exercise } from './content';
import { ExerciseDemonstration } from './ExerciseDemonstration';

const goalIcons = [Dumbbell, Flame, TrendingUp, Target, Sprout, Repeat2];
const entitlementNames: Record<string, string> = { program_access: 'Personalized program access', coach_messaging: 'Coach messaging', weekly_checkin: 'Weekly check-ins', form_review: 'Form review', nutrition_guidance: 'Nutrition guidance', exercise_library: 'Exercise library' };

export function GoalCards({ limit }: { limit?: number }) {
  return <div className="sb-goals-grid">{publicCopy.goals.slice(0, limit).map((goal, index) => { const Icon = goalIcons[index]; return <Link className="sb-goal-card" key={goal.name} to={`/apply?goal=${encodeURIComponent(goal.name)}`}><div className="sb-goal-top"><Icon size={27} strokeWidth={1.5} /><span>{goal.number}</span></div><h3>{goal.name}</h3><p>{goal.description}</p><span className="sb-goal-link">Find your direction <ArrowUpRight size={18} /></span></Link>; })}</div>;
}

export function PricingCards() {
  const products = useProducts();
  if (products.isPending) return <Loading label="Loading current coaching plans…" />;
  if (products.isError) return <ErrorState error={products.error} retry={() => void products.refetch()} />;
  if (!products.data.items.length) return <div className="sb-empty"><h3>Let's find the right plan for you.</h3><p>Published coaching plans will appear here. You can still send an application to discuss your goals.</p><Link className="sb-text-link" to="/apply">Start your application <ArrowUpRight size={18} /></Link></div>;
  return <div className="sb-pricing-grid">{products.data.items.map((product, index) => {
    const entitled = Object.entries(product.entitlements || {}).filter(([key, value]) => value === true && entitlementNames[key]).map(([key]) => entitlementNames[key]);
    const features = product.features?.length ? product.features : entitled.length ? entitled : ['Plan details confirmed during consultation'];
    const annual = product.billing_interval === 'year' || product.billing_interval === 'annual';
    return <article className={`sb-price-card ${index === 0 ? 'sb-price-featured' : ''}`} key={product.id}><div className="sb-price-top"><span className="sb-kicker">{annual ? 'COMMIT TO YOUR NEXT CHAPTER' : 'BUILD YOUR MOMENTUM'}</span><span className="sb-price-tag">{annual ? 'Long-term focus' : 'Flexible commitment'}</span></div><h3>{product.name}</h3><p>{product.description}</p><div className="sb-price">{formatPrice(product)}<span> / {product.billing_interval === 'annual' ? 'year' : product.billing_interval === 'monthly' ? 'month' : product.billing_interval}</span></div><div className="sb-price-divider" /><ul>{features.map(feature => <li key={feature}><Check size={17} />{feature}</li>)}</ul><Link className={`sb-button ${index === 0 ? 'sb-button-lime' : 'sb-button-outline'}`} to={`/apply?plan=${encodeURIComponent(product.id)}`}>Apply for coaching <ArrowUpRight size={18} /></Link><small>Subject to assessment and coaching availability.</small></article>;
  })}</div>;
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
  return <div className="sb-section-heading"><div><p className="sb-kicker">{eyebrow}</p><h2>{title}</h2>{description && <p className="sb-section-description">{description}</p>}</div>{link && <Link className="sb-text-link" to={link}>{linkLabel || 'Explore more'} <ArrowRight size={18} /></Link>}</div>;
}
