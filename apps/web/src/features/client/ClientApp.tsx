import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { ClientLoading } from './common'
import './client.css'

const DashboardPage = lazy(() => import('./dashboard').then(module => ({ default: module.DashboardPage })))
const WorkoutsPage = lazy(() => import('./workouts').then(module => ({ default: module.WorkoutsPage })))
const ProgramsPage = lazy(() => import('./workouts').then(module => ({ default: module.ProgramsPage })))
const ProgressPage = lazy(() => import('./progress').then(module => ({ default: module.ProgressPage })))
const NutritionPage = lazy(() => import('./progress').then(module => ({ default: module.NutritionPage })))
const HabitsPage = lazy(() => import('./habits').then(module => ({ default: module.HabitsPage })))
const CheckinsPage = lazy(() => import('./coaching').then(module => ({ default: module.CheckinsPage })))
const MessagesPage = lazy(() => import('./coaching').then(module => ({ default: module.MessagesPage })))
const BookingsPage = lazy(() => import('./coaching').then(module => ({ default: module.BookingsPage })))
const BillingPage = lazy(() => import('./billing').then(module => ({ default: module.BillingPage })))
const OnboardingPage = lazy(() => import('./onboarding').then(module => ({ default: module.OnboardingPage })))

const FormChecksPage = lazy(() => import('./formchecks').then(module => ({ default: module.FormChecksPage })))
const FeedbackPage = lazy(() => import('./feedback').then(module => ({ default: module.FeedbackPage })))

export function ClientApp() {
  return <div className="client-portal"><Suspense fallback={<ClientLoading />}><Routes><Route index element={<DashboardPage />} /><Route path="workouts" element={<WorkoutsPage />} /><Route path="programs" element={<ProgramsPage />} /><Route path="progress" element={<ProgressPage />} /><Route path="nutrition" element={<NutritionPage />} /><Route path="habits" element={<HabitsPage />} /><Route path="checkins" element={<CheckinsPage />} /><Route path="messages" element={<MessagesPage />} /><Route path="bookings" element={<BookingsPage />} /><Route path="billing" element={<BillingPage />} /><Route path="onboarding" element={<OnboardingPage />} /><Route path="formchecks" element={<FormChecksPage />} /><Route path="feedback" element={<FeedbackPage />} /><Route path="*" element={<Navigate to="/app" replace />} /></Routes></Suspense></div>
}
