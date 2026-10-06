import { Navigate, Route, Routes } from 'react-router-dom';
import { Dashboard } from './Dashboard';
import { ClientDetail, Clients } from './Clients';
import { Leads } from './Leads';
import { FormChecks } from './FormChecks';
import { Feedback } from './Feedback';
import { Exercises, Programs } from './Programs';
import { Calendar, Checkins, Messages } from './Experience';
import { AuditLog, Content, Payments, Settings } from './Business';
import { Users } from './Users';
import { useAuth } from '../../services/auth';
import { AdminToastProvider } from './shared';
import './admin.css';
export default function AdminApp(){const {user}=useAuth();const isAdmin=user?.role==='ADMIN'||user?.role==='SUPER_ADMIN';const isSuperAdmin=user?.role==='SUPER_ADMIN';return <AdminToastProvider><Routes><Route index element={<Dashboard/>}/><Route path="clients" element={<Clients/>}/><Route path="clients/:id" element={<ClientDetail/>}/><Route path="leads" element={<Leads/>}/><Route path="programs" element={<Programs/>}/><Route path="exercises" element={<Exercises/>}/><Route path="checkins" element={<Checkins/>}/><Route path="messages" element={<Messages/>}/><Route path="formchecks" element={<FormChecks/>}/><Route path="feedback" element={<Feedback/>}/><Route path="calendar" element={<Calendar/>}/><Route path="payments" element={isAdmin?<Payments/>:<Navigate to="/admin" replace/>}/><Route path="content" element={isAdmin?<Content/>:<Navigate to="/admin" replace/>}/><Route path="settings" element={isAdmin?<Settings/>:<Navigate to="/admin" replace/>}/><Route path="users" element={isSuperAdmin?<Users/>:<Navigate to="/admin" replace/>}/><Route path="audit" element={<AuditLog/>}/><Route path="*" element={<Navigate to="/admin" replace/>}/></Routes></AdminToastProvider>;}
