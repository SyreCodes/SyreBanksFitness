import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import { CheckCircle2 } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { api } from '../../services/api';
import type { ListResult } from '../../services/api';

const ToastContext = createContext<(message: string) => void>(() => undefined);
export function AdminToastProvider({ children }: { children: ReactNode }) { const [message,setMessage] = useState(''); const toast = (value: string) => { setMessage(value); window.setTimeout(() => setMessage(''), 4000); }; return <ToastContext.Provider value={toast}>{children}{message && <div className="toast" role="status"><CheckCircle2 size={18}/>{message}</div>}</ToastContext.Provider>; }
export const useToast = () => useContext(ToastContext);
export function useList<T>(path: string, key: string = path) { return useQuery({ queryKey: [key, path], queryFn: () => api<ListResult<T>>(path) }); }
export const initials = (name: string) => name.split(' ').map(value => value[0]).slice(0,2).join('').toUpperCase();
export const label = (value: string) => value.replaceAll('_', ' ').toLowerCase().replace(/^\w/, character => character.toUpperCase());
export function date(value: string | undefined) { return value ? new Date(value).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'Africa/Kigali' }) : '—'; }
export function money(value: number, currency = 'USD') { return new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value); }
export function exportCsv(name: string, rows: (string | number)[][]) { const csv = rows.map(row => row.map(cell => { const value = String(cell); const safe = /^[=+@-]/.test(value) ? `'${value}` : value; return `"${safe.replaceAll('"','""')}"`; }).join(',')).join('\r\n'); const url = URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8;'})); const link = document.createElement('a'); link.href = url; link.download = `${name}.csv`; link.click(); URL.revokeObjectURL(url); }
