import { AlertCircle, ArrowRight, LoaderCircle, ShieldCheck } from 'lucide-react'
import { cloneElement, isValidElement, useId } from 'react'
import type { ReactNode, ReactElement } from 'react'
import { Link } from 'react-router-dom'

export const human = (value: string | null | undefined) => value ? value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) : 'Not recorded'
export const dateTime = (value: string) => new Date(value).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
export function Brand({ compact = false }: { compact?: boolean }) { return <div className="brand"><span className="brand-mark"><ShieldCheck size={25}/></span><div><strong>PashuRaksha</strong>{!compact && <small>LIVESTOCK HEALTH NETWORK</small>}</div></div> }
export function Badge({ value, tone }: { value: string; tone?: string }) { return <span className={`badge badge-${(tone || value).toLowerCase()}`}>{human(value)}</span> }
export function Loading() { return <div className="loading" role="status"><LoaderCircle className="spin" size={22}/> Loading records…</div> }
export function ErrorNotice({ message, retry }: { message: string; retry?: () => void }) { return <div className="error-notice" role="alert"><AlertCircle size={18}/><span>{message}</span>{retry && <button className="text-button" onClick={retry}>Try again</button>}</div> }
export function Empty({ title, children }: { title: string; children?: ReactNode }) { return <div className="empty"><ShieldCheck size={30}/><h3>{title}</h3><p>{children}</p></div> }
export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) { return <div className="page-header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="muted">{description}</p>}</div>{action}</div> }
export function Panel({ title, subtitle, children, className = '', action, guide }: { title?: string; subtitle?: string; children: ReactNode; className?: string; action?: ReactNode; guide?: string }) { return <section data-guide={guide} className={`panel ${className}`}>{title && <div className="panel-header"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{action}</div>}{children}</section> }
export function Field({ label, error, children, hint }: { label: string; error?: string; children: ReactNode; hint?: string }) {
  const labelId = useId()
  const descriptionId = `${labelId}-description`
  const field = isValidElement(children) ? cloneElement(children as ReactElement<{ 'aria-labelledby'?: string; 'aria-describedby'?: string; 'aria-invalid'?: boolean }>, { 'aria-labelledby': labelId, 'aria-describedby': hint || error ? descriptionId : undefined, 'aria-invalid': !!error }) : children
  return <label className="field"><span id={labelId}>{label}</span>{field}{(hint || error) && <span id={descriptionId}>{hint && <small>{hint}</small>}{error && <small className="field-error">{error}</small>}</span>}</label>
}
export function TextLink({ to, children }: { to: string; children: ReactNode }) { return <Link className="text-link" to={to}>{children}<ArrowRight size={15}/></Link> }
export function SafetyNotice() { return <div className="safety-notice"><ShieldCheck size={18}/><p><strong>Decision-support only.</strong> AI-assisted preliminary assessment requires veterinary review. Treatment decisions belong to a veterinarian.</p></div> }
