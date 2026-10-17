import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { ArrowRight, HeartPulse, LockKeyhole, MapPin, ShieldCheck, Users } from 'lucide-react'
import { Brand, ErrorNotice, Field } from '../components/ui'
import { endpoints, errorMessage } from '../services/api'
import { useAuth } from '../features/auth/AuthContext'

const loginSchema = z.object({ email: z.email('Enter a valid email address'), password: z.string().min(1, 'Enter your password') })
const registerSchema = z.object({ name: z.string().min(2, 'Enter your full name'), email: z.email('Enter a valid email address'), password: z.string().min(10, 'Use at least 10 characters'), district: z.string().min(2, 'Enter your district') })
const demos = [{ label: 'Farmer', email: 'farmer' }, { label: 'Field worker', email: 'paravet' }, { label: 'Veterinarian', email: 'vet' }, { label: 'Laboratory', email: 'lab' }, { label: 'District admin', email: 'admin' }]
export function AuthPage({ register: registering = false }: { register?: boolean }) {
  const { user, accept } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [busyDemo, setBusyDemo] = useState('')
  const login = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema) })
  const signup = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema), defaultValues: { district: 'Pune' } })
  if (user) return <Navigate to="/" replace/>
  async function demo(email: string) { setError(''); setBusyDemo(email); try { accept(await endpoints.login({ email: `${email}@demo.pashuraksha.in`, password: 'Demo@26128' })); navigate('/') } catch (e) { setError(errorMessage(e)) } finally { setBusyDemo('') } }
  return <div className="auth-page">
    <section className="auth-story"><Brand/><div className="auth-story-content"><span className="pill">SMART INDIA HACKATHON · PS 26128</span><h1>Healthier livestock.<br/><span>Stronger communities.</span></h1><p>From the first field report to a coordinated response. One connected record for every animal.</p><div className="auth-features"><div><HeartPulse/><span><strong>Animal health, in one place</strong><small>Identity, symptoms and health history</small></span></div><div><MapPin/><span><strong>Early signals. Local action.</strong><small>Spatial surveillance and transparent risk</small></span></div><div><Users/><span><strong>Connected care teams</strong><small>Farmer → veterinarian → laboratory → authority</small></span></div></div></div><p className="auth-footnote">A livestock health decision-support prototype.<br/>Demo records and identity lookup are simulated.</p></section>
    <section className="auth-form-area"><div className="auth-form"><span className="icon-tile"><LockKeyhole/></span><p className="eyebrow">WELCOME TO PASHURAKSHA</p><h2>{registering ? 'Create your farmer account' : 'Sign in to your workspace'}</h2><p className="muted">{registering ? 'Keep your animals’ health records together.' : 'Access your records and continue the care journey.'}</p>
    {error && <ErrorNotice message={error}/>}
    {registering ? <form onSubmit={signup.handleSubmit(async values => { setError(''); try { accept(await endpoints.register(values)); navigate('/') } catch (e) { setError(errorMessage(e)) } })} className="form-stack">
      <Field label="Full name" error={signup.formState.errors.name?.message}><input autoComplete="name" {...signup.register('name')}/></Field>
      <Field label="Email address" error={signup.formState.errors.email?.message}><input type="email" autoComplete="email" {...signup.register('email')}/></Field>
      <Field label="Password" error={signup.formState.errors.password?.message} hint="Use at least 10 characters, including a letter and a number."><input type="password" autoComplete="new-password" {...signup.register('password')}/></Field>
      <Field label="District" error={signup.formState.errors.district?.message}><input {...signup.register('district')}/></Field>
      <button className="button primary" disabled={signup.formState.isSubmitting}>{signup.formState.isSubmitting ? 'Creating account…' : 'Create farmer account'}<ArrowRight size={18}/></button>
      <p className="small muted">Professional accounts are provisioned by the administrator.</p>
    </form> : <form onSubmit={login.handleSubmit(async values => { setError(''); try { accept(await endpoints.login(values)); navigate('/') } catch (e) { setError(errorMessage(e)) } })} className="form-stack">
      <Field label="Email address" error={login.formState.errors.email?.message}><input type="email" autoComplete="username" placeholder="you@example.com" {...login.register('email')}/></Field>
      <Field label="Password" error={login.formState.errors.password?.message}><input type="password" autoComplete="current-password" placeholder="Enter your password" {...login.register('password')}/></Field>
      <button className="button primary" disabled={login.formState.isSubmitting}>{login.formState.isSubmitting ? 'Signing in…' : 'Sign in'}<ArrowRight size={18}/></button>
    </form>}
    <p className="auth-switch">{registering ? 'Already registered?' : 'New to PashuRaksha?'} <Link to={registering ? '/login' : '/register'}>{registering ? 'Sign in' : 'Create a farmer account'}</Link></p>
    {!registering && <div className="demo-box"><div className="demo-label"><ShieldCheck size={16}/><strong>Explore the working demo</strong><span>SIMULATED DATA</span></div><p>Choose a role to open its dedicated workspace.</p><div className="demo-roles">{demos.map(d => <button key={d.email} disabled={!!busyDemo} onClick={() => demo(d.email)}>{busyDemo === d.email ? 'Opening…' : d.label}<ArrowRight size={14}/></button>)}</div><small>Demo accounts: password <code>Demo@26128</code></small></div>}
    </div></section>
  </div>
}
