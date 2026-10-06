import { useEffect, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, Menu, X, ChevronDown, Instagram, Mail } from 'lucide-react';
import { PublicContentContext, usePublicContent, fetchPublicContent } from './content';
import { HomePage } from './HomePage';
import { ApplicationPage } from './ApplicationPage';
import { Brand } from './Brand';
import { AboutPage, ProgramsPage, ServicesPage, TransformationsPage, ExercisesPage, BlogPage, PricingPage, FaqPage, ContactPage, LegalPage } from './PublicPages';
import './public.css';

const navigation = [
  ['/', 'Home'], ['/about', 'About'], ['/programs', 'Programs'], ['/services', 'Services'], ['/exercises', 'Exercise library'], ['/pricing', 'Pricing'],
];
const extraNavigation = [['/transformations', 'Transformations'], ['/blog', 'Journal'], ['/faq', 'FAQ'], ['/contact', 'Contact']];
const titles: Record<string, string> = { '/': 'Personalized fitness coaching', '/about': 'About the approach', '/programs': 'Training programs', '/services': 'Coaching services', '/transformations': 'Client transformations', '/exercises': 'Exercise library', '/blog': 'The journal', '/apply': 'Train with Syre', '/pricing': 'Coaching plans', '/faq': 'Questions answered', '/contact': 'Get in touch' };

function PublicHeader() {
  const [open, setOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const location = useLocation();
  useEffect(() => { setOpen(false); setMoreOpen(false); }, [location.pathname]);
  return <header className="sb-header" onKeyDown={event => { if (event.key === 'Escape') { setOpen(false); setMoreOpen(false); } }}><div className="sb-header-inner">
    <Brand light />
    <nav className="sb-desktop-nav" aria-label="Main navigation">{navigation.map(([path, title]) => <NavLink key={path} to={path} end={path === '/'}>{title}</NavLink>)}<div className="sb-more"><button onClick={() => setMoreOpen(!moreOpen)} aria-expanded={moreOpen} aria-controls="sb-more-menu">More <ChevronDown size={13} /></button>{moreOpen && <div id="sb-more-menu" className="sb-more-menu">{extraNavigation.map(([path, title]) => <Link key={path} to={path}>{title}</Link>)}</div>}</div></nav>
    <div className="sb-header-actions"><Link className="sb-login-link" to="/login">Log in</Link><Link className="sb-button sb-button-lime sb-header-cta" to="/apply">Train with me <ArrowUpRight size={17} /></Link><button className="sb-menu-toggle" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="sb-mobile-menu" aria-label={open ? 'Close navigation' : 'Open navigation'}>{open ? <X /> : <Menu />}</button></div>
  </div>{open && <nav id="sb-mobile-menu" className="sb-mobile-menu" aria-label="Mobile navigation">{[...navigation, ...extraNavigation, ['/apply', 'Train with me'], ['/login', 'Log in']].map(([path, title]) => <NavLink key={path} to={path} end={path === '/'}>{title}<ArrowUpRight size={18} /></NavLink>)}</nav>}</header>;
}

function PublicFooter() {
  const content = usePublicContent();
  return <footer className="sb-footer"><div className="sb-container sb-footer-top"><div><Brand light /><p>Build strength. Find your discipline.<br />Become more than you were yesterday.</p><div className="sb-socials"><a href={content.instagram_url || 'https://www.instagram.com/williamsyre2.0/'} aria-label="Syre Banks Fitness on Instagram" target="_blank" rel="noreferrer"><Instagram size={20} /></a><a href={content.tiktok_url || 'https://www.tiktok.com/@mugabo.willy'} target="_blank" rel="noreferrer">TikTok <ArrowUpRight size={15} /></a><a href={`mailto:${content.contact_email || 'syrefitness6@gmail.com'}`} aria-label="Email Syre Banks Fitness"><Mail size={20} /></a></div></div><div><h3>Explore</h3><Link to="/about">About the approach</Link><Link to="/programs">Programs</Link><Link to="/services">Coaching services</Link><Link to="/exercises">Exercise library</Link></div><div><h3>Your next step</h3><Link to="/apply">Train with me</Link><Link to="/pricing">Plans & pricing</Link><Link to="/faq">Questions answered</Link><Link to="/contact">Get in touch</Link></div><div className="sb-footer-contact"><h3>Let's connect</h3><a href={`mailto:${content.contact_email || 'syrefitness6@gmail.com'}`}>{content.contact_email || 'syrefitness6@gmail.com'}</a><a href={`tel:${content.contact_phone || '0785430927'}`}>{content.contact_phone || '0785430927'}</a><span>Online coaching. Wherever you train.</span></div></div><div className="sb-container sb-footer-bottom"><span>© {new Date().getFullYear()} Syre Banks Fitness</span><div><Link to="/legal/privacy">Privacy</Link><Link to="/legal/terms">Terms</Link><Link to="/legal/disclaimer">Disclaimer</Link><Link to="/legal/cookies">Cookies</Link><Link to="/legal/refunds">Refunds</Link></div></div></footer>;
}

export function PublicSite() {
  const location = useLocation();
  const content = useQuery({ queryKey: ['public-content'], queryFn: fetchPublicContent });
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
    document.title = `${titles[location.pathname] || 'Syre Banks Fitness'} · Syre Banks Fitness`;
    let meta = document.querySelector<HTMLMetaElement>('meta[name="description"]');
    if (!meta) { meta = document.createElement('meta'); meta.name = 'description'; document.head.appendChild(meta); }
    meta.content = 'Personalized fitness coaching, purposeful training and real accountability. Build the body, the discipline and the life with Syre Banks Fitness.';
  }, [location.pathname]);
  return <PublicContentContext.Provider value={content.data || {}}><div className="public-site"><a className="sb-skip-link" href="#main-content">Skip to content</a><PublicHeader /><main id="main-content"><Routes><Route index element={<HomePage />} /><Route path="about" element={<AboutPage />} /><Route path="programs" element={<ProgramsPage />} /><Route path="services" element={<ServicesPage />} /><Route path="transformations" element={<TransformationsPage />} /><Route path="exercises" element={<ExercisesPage />} /><Route path="blog" element={<BlogPage />} /><Route path="blog/:slug" element={<BlogPage />} /><Route path="apply" element={<ApplicationPage />} /><Route path="pricing" element={<PricingPage />} /><Route path="faq" element={<FaqPage />} /><Route path="contact" element={<ContactPage />} /><Route path="legal/:policy" element={<LegalPage />} /><Route path="*" element={<section className="sb-section sb-container"><h1 className="sb-display">Page not found.</h1><p>Let's get you back to your next step.</p><Link className="sb-button sb-button-dark" to="/">Back to home <ArrowUpRight size={18} /></Link></section>} /></Routes></main>{content.isError && <div className="sb-content-notice" role="status">Some website content is temporarily unavailable. <button onClick={() => void content.refetch()}>Try again</button></div>}<PublicFooter /></div></PublicContentContext.Provider>;
}
