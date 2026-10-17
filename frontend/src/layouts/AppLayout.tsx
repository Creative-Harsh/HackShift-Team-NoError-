import { useEffect, useState } from 'react'
import { NavLink, Navigate, Outlet } from 'react-router-dom'
import { Activity, ClipboardList, House, LogOut, Menu, PawPrint, ShieldCheck, Wifi, WifiOff, X, FlaskConical, Map } from 'lucide-react'
import { useAuth } from '../features/auth/AuthContext'
import { Brand, Loading } from '../components/ui'
import { roleNames } from '../types'
import { QueuePanel } from '../features/offline/QueuePanel'
import { PashuMitra } from '../features/assistant/PashuMitra'
import type { Role } from '../types'
export function ProtectedRoute({ roles }: { roles?: Role[] }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading/>
  if (!user) return <Navigate to="/login" replace/>
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace/>
  return <Outlet/>
}
export function AppLayout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [online, setOnline] = useState(navigator.onLine)
  useEffect(() => { const update = () => setOnline(navigator.onLine); window.addEventListener('online', update); window.addEventListener('offline', update); return () => { window.removeEventListener('online', update); window.removeEventListener('offline', update) } }, [])
  if (!user) return null
  const fieldRole = ['farmer', 'paravet'].includes(user.role)
  return <div className="app-shell">
    {open && <button className="sidebar-overlay" aria-label="Close navigation" onClick={() => setOpen(false)}/>}
    <aside className={`sidebar ${open ? 'is-open' : ''}`}><div className="sidebar-brand"><Brand/><button className="icon-button mobile-only" onClick={() => setOpen(false)} aria-label="Close menu"><X/></button></div><div className="workspace-label">{roleNames[user.role]} workspace</div>
    <nav aria-label="Main navigation">
      <NavLink data-guide="nav-home" to="/" end onClick={() => setOpen(false)}><House size={19}/>{user.role === 'admin' ? 'District overview' : user.role === 'vet' ? 'Review overview' : 'Overview'}</NavLink>
      {user.role !== 'lab' && <NavLink data-guide="nav-animals" to="/animals" onClick={() => setOpen(false)}><PawPrint size={19}/>{user.role === 'farmer' ? 'My animals' : 'Animal records'}</NavLink>}
      {fieldRole && <NavLink data-guide="nav-report" to="/report" onClick={() => setOpen(false)}><Activity size={19}/>Report symptoms</NavLink>}
      {user.role !== 'lab' && <NavLink data-guide="nav-cases" to="/cases" onClick={() => setOpen(false)}><ClipboardList size={19}/>{user.role === 'vet' ? 'Case worklist' : 'Health reports'}</NavLink>}
      {['paravet','vet','admin'].includes(user.role) && <NavLink data-guide="nav-outbreaks" to="/outbreaks" onClick={() => setOpen(false)}><Map size={19}/>Outbreak map</NavLink>}
      {user.role === 'lab' && <NavLink data-guide="nav-lab" to="/laboratory" onClick={() => setOpen(false)}><FlaskConical size={19}/>Laboratory requests</NavLink>}
    </nav><div className="sidebar-note"><ShieldCheck size={20}/><strong>Every report matters.</strong><p>Early reporting helps your care team respond sooner.</p></div><div className="sidebar-footer"><span className="prototype-dot"/> SIH 2026 · Prototype</div></aside>
    <div className="main-shell"><header className="topbar"><div className="topbar-left"><button className="icon-button mobile-only" data-guide="menu" aria-label="Open menu" onClick={() => setOpen(true)}><Menu/></button><span>{user.district} district</span><span className="topbar-divider"/><span className="muted small">Livestock health & surveillance</span></div><div className="topbar-right"><span className={`connection ${online ? '' : 'offline'}`}>{online ? <Wifi size={15}/> : <WifiOff size={15}/>}<span>{online ? 'Online' : 'Offline'}</span></span><div className="user-avatar">{user.name.slice(0, 1)}</div><div className="user-info"><strong>{user.name}</strong><small>{roleNames[user.role]}</small></div><button className="icon-button" aria-label="Sign out" title="Sign out" onClick={() => { void logout().catch(() => undefined) }}><LogOut size={18}/></button></div></header>
    <main><Outlet/><QueuePanel/></main><footer className="main-footer"><span>PashuRaksha · PS 26128</span><span>Bharat Pashudhan-compatible identity simulation</span></footer></div>
    <PashuMitra key={user.id}/>
  </div>
}
