import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAuth } from '../features/auth/AuthContext'
import { api, errorMessage } from '../services/api'
import { useResource } from '../hooks/useResource'
import { Badge, Empty, ErrorNotice, Field, Loading, PageHeader, Panel, dateTime, human } from '../components/ui'
import { CaseList, DashboardPage } from './DashboardPage'
import { SurveillanceMap } from '../features/surveillance/SurveillanceMap'
import { PrivateAttachment } from '../components/PrivateAttachment'
import type { DiseaseCase, DistrictDashboard, LabTest, Notification, OutbreakMapData } from '../types'

export default function WorkspaceHome() {
  const { user } = useAuth()
  if (user?.role === 'admin') return <AuthorityPage/>
  if (user?.role === 'lab') return <LaboratoryPage/>
  if (user?.role === 'vet') return <VeterinarianPage/>
  return <DashboardPage/>
}

function Notifications() {
  const { user } = useAuth()
  const data = useResource(() => api.get<Notification[]>('/notifications').then(r => r.data))
  return <Panel title="In-app notifications" subtitle="Recorded application updates; no external messages are sent">
    {data.error && <ErrorNotice message={data.error} retry={data.reload}/>}
    <div className="padded form-stack">{data.data?.slice(0, 6).map(n => <div key={n.id} className="notification-row"><div><strong>{n.title}</strong><p>{n.message}</p><small>{dateTime(n.created_at)}</small>{n.case_id && user?.role !== 'lab' && <p><Link to={`/cases/${n.case_id}`}>Open case</Link></p>}</div>{!n.read_by.includes(user!.id) && <button className="button secondary compact" onClick={() => void api.post(`/notifications/${n.id}/read`).then(data.reload).catch(e => alert(errorMessage(e)))}>Mark read</button>}</div>)}{data.data?.length === 0 && <p>No notifications yet.</p>}</div>
  </Panel>
}

export function VeterinarianPage() {
  const data = useResource(() => api.get<DiseaseCase[]>('/vet/queue').then(r => r.data))
  useEffect(() => { const timer = setInterval(data.reload, 20000); return () => clearInterval(timer) }, [data.reload])
  return <><PageHeader eyebrow="VETERINARY RESPONSE" title="Cases requiring your attention" description="High-risk or urgent reports arrive automatically. Your assigned cases remain here until closed." action={<button className="button secondary" onClick={data.reload}>Refresh worklist</button>}/>{data.error && <ErrorNotice message={data.error} retry={data.reload}/>}<Panel guide="vet-queue" title="Priority worklist" subtitle="Ordered by current calculated risk">{data.loading ? <Loading/> : data.data && <CaseList cases={data.data}/>}</Panel><Notifications/></>
}

export function LaboratoryPage() {
  const data = useResource(() => api.get<LabTest[]>('/lab/requests').then(r => r.data))
  const [selectedId, setSelectedId] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [result, setResult] = useState('positive'), [notes, setNotes] = useState('')
  const [attachment,setAttachment]=useState<{id:string;file:File}|null>(null)
  const selected = data.data?.find(t => t.id === selectedId)
  useEffect(() => { const timer = setInterval(data.reload, 20000); return () => clearInterval(timer) }, [data.reload])
  async function update(status: string) {
    if (!selected) return
    setBusy(true); setError('')
    try {
      let attachment_url: string|undefined
      if(attachment && ['positive','negative','inconclusive'].includes(status)) {
        const form=new FormData();form.append('file',attachment.file);form.append('kind','lab_report');form.append('client_upload_id',attachment.id)
        attachment_url=(await api.post<{url:string}>('/media',form)).data.url
      }
      await api.put(`/lab/tests/${selected.id}`, { operation_id: crypto.randomUUID(), expected_version: selected.case_version,
      status, result_notes: notes, attachment_url, ...(status === 'positive' ? { confirmed_disease: selected.disease_code } : {}) }); data.reload(); setNotes('');setAttachment(null) }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  return <><PageHeader eyebrow="LABORATORY EVIDENCE" title="Sample requests and results" description="Local application workflow. Demo accounts and tests do not represent a connected external laboratory." action={<button className="button secondary" onClick={data.reload}>Refresh requests</button>}/>
    {data.error && <ErrorNotice message={data.error} retry={data.reload}/>}{error && <ErrorNotice message={error} retry={data.reload}/>}
    <div className="professional-grid"><Panel guide="lab-requests" title="Requests in your district">{data.loading ? <Loading/> : data.data?.length ? <div className="padded form-stack">{data.data.map(t => <button key={t.id} className={`lab-request ${selectedId === t.id ? 'selected' : ''}`} onClick={() => { setSelectedId(t.id); setNotes(''); setError(''); setAttachment(null); setResult('positive') }}><strong>{t.animal_name} · {t.test_type}</strong><span>{t.pashu_id} · {t.village}</span><Badge value={t.status}/><small>{dateTime(t.requested_at)}</small></button>)}</div> : <Empty title="No sample requests">Requested tests will appear after a veterinarian submits them.</Empty>}</Panel>
    <Panel title="Sample processing">{selected ? <div className="padded form-stack"><h3>{selected.test_type}</h3><p>{selected.animal_name} · {selected.pashu_id}</p><p>Requested by {selected.requested_by_name}. Target: {human(selected.disease_code)}.</p><p>{selected.notes || 'No additional sample instructions.'}</p><Badge value={selected.status}/>
      {selected.status === 'requested' && <button className="button primary" disabled={busy} onClick={() => void update('received')}>Mark sample received</button>}
      {selected.status === 'received' && <button className="button primary" disabled={busy} onClick={() => void update('testing')}>Start testing</button>}
      {selected.status === 'testing' && <form className="form-stack" onSubmit={e => { e.preventDefault(); void update(result) }}><Field label="Laboratory outcome"><select value={result} onChange={e => setResult(e.target.value)}><option value="positive">Positive for requested category</option><option value="negative">Negative</option><option value="inconclusive">Inconclusive</option></select></Field><Field label="Laboratory findings" hint="A final result is immutable. Inconclusive results can be followed by a new veterinarian-requested test."><textarea data-guide="lab-result" required minLength={3} maxLength={4000} value={notes} onChange={e => setNotes(e.target.value)}/></Field><Field label="Result report attachment" hint="Optional PDF, PNG or JPEG, up to 8 MB"><input key={selected.id} type="file" accept="application/pdf,image/png,image/jpeg" onChange={e=>{const file=e.target.files?.[0];if(file && file.size>8*1024*1024){setError("Maximum attachment size is 8 MB.");setAttachment(null)}else setAttachment(file?{id:crypto.randomUUID(),file}:null)}}/></Field><button className="button primary" disabled={busy}>Record final laboratory result</button></form>}
      {selected.result_notes && <div><h3>Recorded findings</h3><p>{selected.result_notes}</p></div>}
      {selected.attachment_url && <PrivateAttachment url={selected.attachment_url} label="Laboratory report"/>}
    </div> : <Empty title="Select a request">Inspect its target and sample instructions before processing.</Empty>}</Panel></div><Notifications/></>
}

function CountChart({ title, values, line = false }: { title: string; values: { name: string; count: number }[]; line?: boolean }) {
  return <Panel title={title} subtitle="Database observations from the last 30 days"><div className="chart-area"><ResponsiveContainer width="100%" height={230}>{line ? <LineChart data={values}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" tickFormatter={v => String(v).slice(5)}/><YAxis allowDecimals={false}/><Tooltip/><Line dataKey="count" stroke="#087f79" dot={false}/></LineChart> : <BarChart data={values}><CartesianGrid strokeDasharray="3 3"/><XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0}/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" fill="#087f79"/></BarChart>}</ResponsiveContainer></div></Panel>
}

export function AuthorityPage() {
  const { user } = useAuth(), navigate = useNavigate()
  const data = useResource(async () => ({ dashboard: (await api.get<DistrictDashboard>('/admin/dashboard')).data,
    map: (await api.get<OutbreakMapData>('/outbreaks/map')).data, tests: (await api.get<LabTest[]>('/lab/requests')).data }))
  const [clusterId, setClusterId] = useState(''), [testId, setTestId] = useState(''), [note, setNote] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { const timer = setInterval(data.reload, 20000); return () => clearInterval(timer) }, [data.reload])
  const value = data.data, cluster = value?.dashboard.recent_clusters.find(c => c.id === clusterId)
  const evidence = value?.tests.filter(t => t.status === 'positive' && cluster?.case_ids.includes(t.case_id) && t.confirmed_disease === cluster.disease_code) || []
  async function confirm() {
    setBusy(true); setError('')
    try { await api.post(`/outbreaks/${clusterId}/confirm`, { evidence_test_ids: [testId], note }); data.reload(); setTestId(''); setNote('') }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  return <><PageHeader eyebrow={`${user?.district.toUpperCase()} · SURVEILLANCE`} title="District health overview" description="Current operational workload, observed disease activity and recorded professional evidence." action={<button className="button secondary" onClick={data.reload}>Refresh overview</button>}/>{data.error && <ErrorNotice message={data.error} retry={data.reload}/>}
    {data.loading && !value ? <Loading/> : value && <>
      <div className="stat-grid authority-stats">{Object.entries(value.dashboard.kpis).map(([key, count]) => <div className="stat" key={key}><span>{human(key)}</span><strong>{count}</strong><small>{key === 'high_risk_cases' ? 'Risk 60+, including critical' : 'From district records'}</small></div>)}</div>
      <Panel title="Outbreak density" action={<Link className="text-link" to="/outbreaks">Open detailed map and replay</Link>}><SurveillanceMap cases={value.map.cases} clusters={value.map.clusters} selected={null} select={() => navigate('/outbreaks')} filterKey="authority" markers density groupMarkers/></Panel>
      <div className="professional-grid"><CountChart title="Cases over time" values={value.dashboard.cases_over_time} line/><CountChart title="Disease distribution" values={value.dashboard.disease_distribution}/><CountChart title="Species distribution" values={value.dashboard.species_distribution}/><CountChart title="Risk distribution" values={value.dashboard.risk_distribution}/></div>
      <Panel title="Unresolved critical cases"><CaseList cases={value.dashboard.critical_cases}/></Panel>
      <div className="professional-grid"><Panel guide="admin-clusters" title="Recent clusters"><div className="padded form-stack">{value.dashboard.recent_clusters.map(c => <button className="lab-request" key={c.id} onClick={() => { setClusterId(c.id); setTestId('') }}><strong>{c.suspected_disease} · {c.animal_count} animals</strong><span>Cluster score {c.score} / 100</span><Badge value={c.status}/></button>)}{!value.dashboard.recent_clusters.length && <p>No active scored clusters.</p>}</div></Panel>
      <Panel guide="admin-confirmation" title="Authority outbreak confirmation" subtitle="Explicit decision using laboratory evidence; demo confirmation stays within this application"><div className="padded form-stack">{error && <ErrorNotice message={error}/>}{cluster ? <><h3>{cluster.suspected_disease}</h3><Badge value={cluster.status}/>{cluster.status !== 'confirmed_outbreak' && <form className="form-stack" onSubmit={e => { e.preventDefault(); void confirm() }}><Field label="Positive laboratory evidence"><select required value={testId} onChange={e => setTestId(e.target.value)}><option value="">Choose matching confirmed test</option>{evidence.map(t => <option key={t.id} value={t.id}>{t.animal_name} · {t.test_type}</option>)}</select></Field>{!evidence.length && <p>A matching positive result is required before confirmation.</p>}<Field label="Authority investigation note"><textarea required minLength={10} maxLength={2000} value={note} onChange={e => setNote(e.target.value)}/></Field><button className="button primary" disabled={busy || !evidence.length}>Record authority confirmation</button></form>}</> : <p>Select a cluster to review its confirmation evidence.</p>}</div></Panel></div>
      <Panel title="Operational evaluation"><div className="padded"><p>Mean report receipt → veterinarian assignment: <strong>{value.dashboard.operational.mean_report_to_assignment_minutes === null ? 'No assignments yet' : `${value.dashboard.operational.mean_report_to_assignment_minutes.toFixed(1)} minutes`}</strong> across {value.dashboard.operational.assigned_case_count} assigned cases.</p><p className="small muted">This measures application actions, including demo actions, and does not claim live veterinary response time.</p></div></Panel>
    </>}<Notifications/>
  </>
}
