import { useEffect, useSyncExternalStore } from 'react';
import { SunMoon } from 'lucide-react';

export type ThemePreference = 'light' | 'dark' | 'system';
export const themeKey = 'syre-theme';
const eventName = 'syre-theme-change';
export function readTheme(): ThemePreference {
  try { const value = localStorage.getItem(themeKey); return value === 'light' || value === 'dark' ? value : 'system'; }
  catch { return 'system'; }
}
function subscribe(callback: () => void) {
  const storage = () => { document.documentElement.dataset.themePreference = readTheme(); callback(); };
  window.addEventListener('storage', storage); window.addEventListener(eventName, callback);
  return () => { window.removeEventListener('storage', storage); window.removeEventListener(eventName, callback); };
}
function subscribeSystem(callback: () => void) {
  const query = window.matchMedia('(prefers-color-scheme: dark)');
  query.addEventListener('change', callback); return () => query.removeEventListener('change', callback);
}
export function setTheme(value: ThemePreference) {
  try { localStorage.setItem(themeKey, value); } catch { /* Session theme still works when storage is blocked. */ }
  document.documentElement.dataset.theme = value === 'system' ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light') : value;
  document.documentElement.dataset.themePreference = value;
  window.dispatchEvent(new Event(eventName));
}
function snapshot(): ThemePreference { return (document.documentElement.dataset.themePreference as ThemePreference) || readTheme(); }
export function ThemeSync() {
  const preference = useSyncExternalStore(subscribe, snapshot, () => 'system' as const);
  const dark = useSyncExternalStore(subscribeSystem, () => window.matchMedia('(prefers-color-scheme: dark)').matches, () => false);
  useEffect(() => { document.documentElement.dataset.theme = preference === 'system' ? (dark ? 'dark' : 'light') : preference; }, [preference, dark]);
  return null;
}
export function ThemeControl({ label = 'Appearance' }: { label?: string }) {
  const preference = useSyncExternalStore(subscribe, snapshot, () => 'system' as const);
  return <label className="theme-control"><SunMoon size={18} aria-hidden="true"/><span className="sr-only">{label}</span><select aria-label={label} value={preference} onChange={event => setTheme(event.target.value as ThemePreference)}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label>;
}
