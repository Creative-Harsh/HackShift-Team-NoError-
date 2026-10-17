import { Link } from 'react-router-dom'
import { Activity, ArrowRight, ClipboardList, PawPrint, Plus, ShieldCheck, MapPin, FlaskConical, Stethoscope } from 'lucide-react'
import { useAuth } from '../features/auth/AuthContext'
import { endpoints } from '../services/api'
import { useResource } from '../hooks/useResource'
import { Badge, Empty, ErrorNotice, Loading, PageHeader, Panel, TextLink, dateTime } from '../components/ui'
import type { DiseaseCase } from '../types'
export function CaseList({ cases }: { cases: DiseaseCase[] }) {
  if (!cases.length) return <Empty title="No health reports yet">Reports will appear here as they are submitted.</Empty>
  return <div data-guide="case-list" className="table-wrap"><table><thead><tr><th>Animal / report</th><th>Location</th><th>Assessment</th><th>Status</th><th>Reported</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{cases.map(c => <tr key={c.id}><td><Link className="record-name" to={`/cases/${c.id}`}>{c.animal_name || c.pashu_id}</Link><small className="table-sub">{c.pashu_id} · {c.species}</small></td><td>{c.village}</td><td>{c.risk ? <Badge value={c.risk.level}/> : <span className="muted small">Awaiting assessment</span>}</td><td><Badge value={c.status}/></td><td className="small muted">{dateTime(c.reported_at)}</td><td><Link className="row-link" to={`/cases/${c.id}`} aria-label={`Open report for ${c.animal_name}`}><ArrowRight size={17}/></Link></td></tr>)}</tbody></table></div>
}
export function DashboardPage() {
  const { user } = useAuth()
  const role = user!.role
  const resource = useResource(async () => role === 'lab' ? { animals: [], cases: [] } : { animals: await endpoints.animals(), cases: await endpoints.cases() }, role)
  const field = role === 'farmer' || role === 'paravet'
  const data = resource.data
  const active = data?.cases.filter(c => c.status !== 'closed') || []
  const titles = { farmer: 'Your herd, in good hands.', paravet: 'A healthier village starts here.', vet: 'Your clinical review workspace.', lab: 'Evidence that informs care.', admin: 'Your district health overview.' }
  return <><PageHeader eyebrow={`${new Date().toLocaleDateString('en-IN', { weekday: 'long', day: 'numeric', month: 'long' })} · ${user!.district}`} title={titles[role]} description={`Welcome, ${user!.name.split(' ')[0]}. ${field ? 'Keep records up to date and report changes early.' : 'Review the latest records from your district.'}`} action={field && <Link className="button primary" to="/report"><Plus size={18}/>Report symptoms</Link>}/>
  {resource.error && <ErrorNotice message={resource.error} retry={resource.reload}/>}
  {resource.loading ? <Loading/> : role === 'lab' ? <LaboratoryIntro/> : data && <>
    <div className="stat-grid"><Stat icon={<PawPrint/>} label={role === 'farmer' ? 'My animals' : 'Registered animals'} value={data.animals.length} hint="Digital health records"/><Stat icon={<ClipboardList/>} label="Active reports" value={active.length} hint="Reports not yet closed"/><Stat icon={<Activity/>} label="High / critical risk" value={active.filter(c => ['HIGH', 'CRITICAL'].includes(c.risk?.level || '')).length} hint="From assessed reports"/><Stat icon={<ShieldCheck/>} label="Completed cases" value={data.cases.filter(c => c.status === 'closed').length} hint="Care journey closed"/></div>
    {field && <div className="dashboard-actions"><div className="action-card"><span className="icon-tile"><PawPrint/></span><div><p className="eyebrow">ANIMAL DIGITAL HEALTH RECORD</p><h2>A familiar identity. A complete history.</h2><p>Find an animal using its simulated 12-digit Pashu Aadhaar and access its care record.</p><Link className="button secondary" to="/animals">Find an animal<ArrowRight size={16}/></Link></div></div><div className="care-card"><ShieldCheck size={28}/><h3>Notice something unusual?</h3><p>Record changes in appetite, activity, milk production or visible symptoms. Early information helps veterinary review.</p><Link to="/report">Create a health report<ArrowRight size={16}/></Link></div></div>}
    <Panel title={role === 'vet' ? 'Cases for attention' : 'Recent health reports'} subtitle="Live records from your authorized workspace" action={<TextLink to="/cases">View all reports</TextLink>}><CaseList cases={[...data.cases].sort((a,b) => b.reported_at.localeCompare(a.reported_at)).slice(0, 5)}/></Panel>
    <div className="bottom-grid"><Panel title="Connected care" subtitle="A recorded journey from observation to response"><div className="journey"><div><ClipboardList/><strong>Report</strong><small>Structured observations</small></div><ArrowRight/><div><Stethoscope/><strong>Review</strong><small>Veterinary assessment</small></div><ArrowRight/><div><FlaskConical/><strong>Confirm</strong><small>Laboratory evidence</small></div></div></Panel><Panel title="Workspace scope"><div className="scope-content"><MapPin/><div><strong>{user!.district} district</strong><p>{role === 'farmer' ? 'You can access your own animals and their reports.' : 'Your role and district determine which records you can access.'}</p><small className="muted">Demo records are simulated, not government data.</small></div></div></Panel></div>
  </>}
  </>
}
function Stat({ icon, label, value, hint }: { icon: React.ReactNode; label: string; value: number; hint: string }) { return <div className="stat"><div className="stat-head"><span>{label}</span><span className="stat-icon">{icon}</span></div><strong>{value.toLocaleString('en-IN')}</strong><small>{hint}</small></div> }
export function LaboratoryIntro() { return <Panel title="Laboratory workspace" subtitle="Sample requests and results are restricted to laboratory staff"><Empty title="Laboratory workflow is being prepared">Sample receipt, testing and result reporting will be available after the response workflow phase. No laboratory connectivity is simulated here.</Empty></Panel> }
export function CasesPage() { const { data, loading, error, reload } = useResource(endpoints.cases); return <><PageHeader eyebrow="CASE MANAGEMENT" title="Health reports" description="Track each observation through its care journey."/>{error && <ErrorNotice message={error} retry={reload}/>}<Panel>{loading ? <Loading/> : data && <CaseList cases={data}/>}</Panel></> }
