import { lazy, Suspense } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from '../services/auth';
import { Loading, ErrorState } from '../components/ui';
import { AppShell } from '../layouts/AppShell';
const PublicSite = lazy(() => import('../features/public/PublicSite').then(module => ({default:module.PublicSite})));
const AuthPage = lazy(() => import('../features/auth/AuthPage').then(module => ({default:module.AuthPage})));
const ClientApp = lazy(() => import('../features/client/ClientApp').then(module => ({default:module.ClientApp})));
const AdminApp = lazy(() => import('../features/admin/AdminApp'));
function Protected({admin=false}:{admin?:boolean}){const {user,loading}=useAuth();const location=useLocation();if(loading)return <Loading/>;if(!user)return <Navigate to="/login" state={{from:location.pathname}} replace/>;if(admin&&!['SUPER_ADMIN','ADMIN','COACH'].includes(user.role))return <ErrorState error={new Error('This workspace is reserved for your coach. Visit your client dashboard.')}/>;return <Outlet/>;}
export function App(){return <Suspense fallback={<Loading/>}><Routes><Route element={<Protected admin/>}><Route element={<AppShell mode="admin"/>}><Route path="/admin/*" element={<AdminApp/>}/></Route></Route><Route element={<Protected/>}><Route element={<AppShell mode="client"/>}><Route path="/app/*" element={<ClientApp/>}/></Route></Route>{['login','register','forgot-password','reset-password','verify-email'].map(path=><Route key={path} path={`/${path}`} element={<AuthPage/>}/>)}<Route path="/*" element={<PublicSite/>}/></Routes></Suspense>;}
