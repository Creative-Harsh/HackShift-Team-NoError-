import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './features/auth/AuthContext'
import { AppLayout, ProtectedRoute } from './layouts/AppLayout'
import { AuthPage } from './pages/AuthPage'
import { CasesPage } from './pages/DashboardPage'
import { AnimalsPage } from './pages/AnimalsPage'
import { AnimalFormPage } from './pages/AnimalFormPage'
import { AnimalDetailPage } from './pages/AnimalDetailPage'
import { ReportPage } from './pages/ReportPage'
import { CaseDetailPage } from './pages/CaseDetailPage'
import { Loading } from './components/ui'
import './styles.css'
if ('serviceWorker' in navigator && import.meta.env.PROD) navigator.serviceWorker.register('/sw.js').catch(() => undefined)
const WorkspaceHome = React.lazy(() => import('./pages/ProfessionalPage'))
const LaboratoryPage = React.lazy(() => import('./pages/ProfessionalPage').then(m => ({ default: m.LaboratoryPage })))
const OutbreakPage = React.lazy(() => import('./pages/OutbreakPage'))
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><AuthProvider><Routes>
  <Route path="/login" element={<AuthPage/>}/><Route path="/register" element={<AuthPage register/>}/>
  <Route element={<ProtectedRoute/>}><Route element={<AppLayout/>}>
    <Route index element={<React.Suspense fallback={<Loading/>}><WorkspaceHome/></React.Suspense>}/>
    <Route element={<ProtectedRoute roles={['farmer','paravet','vet','admin']}/>}><Route path="animals" element={<AnimalsPage/>}/><Route path="animals/:id" element={<AnimalDetailPage/>}/><Route path="cases" element={<CasesPage/>}/><Route path="cases/:id" element={<CaseDetailPage/>}/></Route>
    <Route element={<ProtectedRoute roles={['farmer','paravet']}/>}><Route path="animals/new" element={<AnimalFormPage/>}/><Route path="animals/:id/edit" element={<AnimalFormPage/>}/><Route path="report" element={<ReportPage/>}/></Route>
    <Route element={<ProtectedRoute roles={['lab']}/>}><Route path="laboratory" element={<React.Suspense fallback={<Loading/>}><LaboratoryPage/></React.Suspense>}/></Route>
    <Route element={<ProtectedRoute roles={['paravet','vet','admin']}/>}><Route path="outbreaks" element={<React.Suspense fallback={<Loading/>}><OutbreakPage/></React.Suspense>}/></Route>
  </Route></Route><Route path="*" element={<Navigate to="/" replace/>}/>
</Routes></AuthProvider></BrowserRouter></React.StrictMode>)
