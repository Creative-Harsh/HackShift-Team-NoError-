import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Activity, ChevronRight, Layers, MapPin, Play, RefreshCw } from 'lucide-react'
import { Badge, Empty, ErrorNotice, Field, Loading, PageHeader, Panel, dateTime, human } from '../components/ui'
import { useAuth } from '../features/auth/AuthContext'
import { isConfirmedCluster, riskColors, SurveillanceMap } from '../features/surveillance/SurveillanceMap'
import { useOutbreakMap } from '../hooks/useOutbreakMap'
import { endpoints, errorMessage } from '../services/api'
import type { DemoStatus, Outbreak, OutbreakFilters } from '../types'

const diseases = [{ code: 'lsd', label: 'Lumpy Skin Disease' }, { code: 'fmd', label: 'Foot-and-Mouth Disease' }, { code: 'respiratory', label: 'Respiratory syndrome' }, { code: 'gastrointestinal', label: 'Gastrointestinal syndrome' }, { code: 'undifferentiated', label: 'Undifferentiated symptoms' }]
const bands = ['LOW', 'MODERATE', 'HIGH', 'CRITICAL']

function DemoReplayPanel({ refresh }: { refresh: () => void }) {
  const [status, setStatus] = useState<DemoStatus | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    endpoints.demoStatus(controller.signal).then(setStatus).catch(e => { if (!controller.signal.aborted) setError(errorMessage(e)) })
    return () => controller.abort()
  }, [])
  const advance = async () => {
    setBusy(true); setError(''); setMessage('')
    try {
      const result = await endpoints.demoReplay()
      setStatus(result)
      setMessage(result.new_case_ids.length ? `${result.new_case_ids.length} report added. Triage, risk and cluster calculations have run.` : 'All scenario reports have already been replayed.')
      refresh()
    } catch (failure) {
      setError(errorMessage(failure))
      try { setStatus(await endpoints.demoStatus()); refresh() } catch { /* Preserve the original actionable error. */ }
    } finally { setBusy(false) }
  }
  return <Panel title="Outbreak replay demonstration" subtitle="Synthetic operational records · real backend calculations" className="demo-replay-panel">
    <div className="padded"><p>Replay successive nearby reports against an older baseline. Watch local activity move from an isolated report to a scored cluster as reports arrive. The algorithm determines each outcome.</p>
      {error && <ErrorNotice message={error}/>}
      {status ? <div className="demo-replay-actions"><div><strong>{status.completed} / {status.total}</strong><span> scenario reports replayed</span></div>
        {status.enabled ? <button className="button primary" disabled={busy || status.completed >= status.total} onClick={() => void advance()}><Play size={16}/>{busy ? 'Replaying report…' : status.completed >= status.total ? 'Replay complete' : 'Replay next report'}</button> : <p>Replay is disabled in this environment.</p>}
      </div> : !error && <p className="small muted">Loading replay progress…</p>}
      {message && <p className="replay-message" role="status">{message}</p>}
    </div>
  </Panel>
}

function HotspotDetails({ cluster }: { cluster: Outbreak }) {
  const sum = cluster.factors.reduce((total, factor) => total + factor.points, 0)
  return <Panel title="Hotspot details" subtitle="Why this location was flagged" className="hotspot-details">
    <div className="padded"><div className="hotspot-detail-heading"><Badge value={cluster.status}/><span className="small muted">{cluster.district}</span></div>
      <h3>{cluster.suspected_disease}</h3>
      <p className="small muted">{isConfirmedCluster(cluster) ? 'Official confirmation recorded through the authorized professional workflow.' : 'Suspected activity. This cluster is not an officially confirmed outbreak.'}</p>
      <div className="hotspot-counts"><div><strong>{cluster.case_count}</strong><span>reports</span></div><div><strong>{cluster.animal_count}</strong><span>distinct animals</span></div><div><strong>{cluster.score}<small>/100</small></strong><span>cluster score</span></div></div>
      <dl className="detail-list compact-details"><div><dt>Villages</dt><dd>{cluster.villages.join(', ')}</dd></div><div><dt>First report</dt><dd>{dateTime(cluster.start_time)}</dd></div><div><dt>Latest report</dt><dd>{dateTime(cluster.end_time)}</dd></div><div><dt>Cluster extent</dt><dd>{cluster.radius_km} km from center</dd></div></dl>
      <h3 className="hotspot-section-title">Cluster score factors</h3>
      {cluster.factors.map(factor => <div className="risk-factor" key={factor.key}><span><strong>{factor.label}</strong><small>{factor.detail}</small></span><b>{factor.points >= 0 ? '+' : ''}{factor.points}</b></div>)}
      <div className="factor-total"><span>Factor total</span><strong>{Number(sum.toFixed(2))} / 100</strong></div>
      {Math.abs(sum - cluster.score) > 0.001 && <p className="small" role="alert">The stored score and factor total differ. Review the cluster calculation.</p>}
      <h3 className="hotspot-section-title">Case risk distribution</h3>
      <div className="hotspot-risk-distribution">{bands.map(band => <span key={band}><i style={{ background: riskColors[band] }}/>{human(band)}<strong>{cluster.risk_distribution[band] || 0}</strong></span>)}</div>
      <h3 className="hotspot-section-title">Latest reports</h3>
      <div className="hotspot-reports">{cluster.latest_reports.map(item => <Link key={item.id} to={`/cases/${item.id}`}><div><strong>{item.animal_name || item.pashu_id}</strong><small>{item.village} · {dateTime(item.reported_at)}</small></div>{item.risk && <Badge value={item.risk.level}/>}<ChevronRight size={15}/></Link>)}</div>
    </div>
  </Panel>
}

export default function OutbreakPage() {
  const { user } = useAuth()
  const initial: OutbreakFilters = { days: 3, disease: '', species: '', village: '', district: user!.district }
  const [filters, setFilters] = useState(initial)
  const [draft, setDraft] = useState(initial)
  const resource = useOutbreakMap(filters)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [markers, setMarkers] = useState(true)
  const [density, setDensity] = useState(true)
  const [groupMarkers, setGroupMarkers] = useState(true)
  const [villages, setVillages] = useState<string[]>([])
  const data = resource.data
  useEffect(() => {
    if (data) setVillages(previous => Array.from(new Set([...previous, ...data.cases.map(item => item.village)])).sort())
  }, [data])
  const clusters = data?.clusters.filter(cluster => cluster.active).sort((a, b) => b.score - a.score) || []
  const selected = clusters.find(cluster => cluster.id === selectedId) || null
  const change = (key: keyof OutbreakFilters, value: string | number) => setDraft(previous => ({ ...previous, [key]: value }))
  return <>
    <PageHeader eyebrow="SPATIAL SURVEILLANCE" title="Disease activity, in context." description="Connect recent reports with distance, time, similarity and local history."
      action={<button className="button secondary" disabled={resource.refreshing} onClick={resource.refresh}><RefreshCw size={16} className={resource.refreshing ? 'spin' : ''}/>{resource.refreshing ? 'Refreshing…' : 'Refresh map'}</button>}/>
    <form className="map-filter-form panel padded" onSubmit={event => { event.preventDefault(); setSelectedId(null); setFilters({ ...draft, village: draft.village.trim() }) }}>
      <Field label="Report period"><select value={draft.days} onChange={e => change('days', Number(e.target.value))}><option value={3}>Last 3 days</option><option value={7}>Last 7 days</option><option value={30}>Last 30 days</option></select></Field>
      <Field label="Suspected disease"><select value={draft.disease} onChange={e => change('disease', e.target.value)}><option value="">All suspected diseases</option>{diseases.map(disease => <option key={disease.code} value={disease.code}>{disease.label}</option>)}</select></Field>
      <Field label="Species"><select value={draft.species} onChange={e => change('species', e.target.value)}><option value="">All species</option>{['cattle','buffalo','goat','sheep','pig'].map(species => <option key={species} value={species}>{human(species)}</option>)}</select></Field>
      <Field label="Village"><input list="map-villages" value={draft.village} placeholder="All villages" onChange={e => change('village', e.target.value)}/></Field>
      <datalist id="map-villages">{villages.map(village => <option key={village} value={village}/>)}</datalist>
      <Field label="District"><input value={draft.district} readOnly/></Field>
      <button className="button primary">Apply filters</button>
    </form>
    {resource.error && <ErrorNotice message={resource.error} retry={resource.refresh}/>}
    {resource.loading ? <Loading/> : data && <>
      <div className="map-summary-strip"><span><MapPin size={17}/><strong>{data.total_cases}</strong> matching reports</span><span><Activity size={17}/><strong>{clusters.length}</strong> active scored clusters</span><span className="muted">{data.config.radius_km} km · {data.config.window_hours}h cluster window</span><small>Updated {dateTime(data.generated_at)} · auto-refresh 20s</small></div>
      {data.truncated && <p className="map-data-notice" role="status">The map displays {data.cases.length} of {data.total_cases} reports. Narrow the filters to inspect a complete selection.</p>}
      <Panel title="Outbreak map" subtitle="Dotted report markers are unconfirmed. Dark solid rings indicate lab-confirmed reports.">
        <div className="map-layer-controls"><span><Layers size={17}/>Map layers</span><label><input type="checkbox" checked={markers} onChange={e => setMarkers(e.target.checked)}/>Report markers</label><label><input type="checkbox" checked={density} onChange={e => setDensity(e.target.checked)}/>Density layer</label><label><input type="checkbox" checked={groupMarkers} disabled={!markers} onChange={e => setGroupMarkers(e.target.checked)}/>Group nearby markers</label></div>
        <SurveillanceMap cases={data.cases} clusters={clusters} selected={selected} select={setSelectedId} filterKey={JSON.stringify(filters)} markers={markers} density={density} groupMarkers={groupMarkers}/>
        <div className="map-legend">{bands.map(band => <span key={band}><i style={{ background: riskColors[band] }}/>{human(band)}</span>)}{data.cases.some(item => !item.risk) && <span><i style={{ background: '#73847d' }}/>Unassessed</span>}<span><i className="legend-suspected"/>Suspected cluster</span><span><i className="legend-confirmed"/>Confirmed outbreak</span></div>
        <p className="map-explanation">Density reflects nearby reports weighted by recorded risk. Marker groups organize the view; outbreak alerts use the backend’s spatial and temporal score.</p>
      </Panel>
      <div className="hotspot-layout"><Panel title="Scored hotspots" subtitle="Filters select matching clusters; details retain each cluster's complete evidence.">
        {clusters.length ? <div className="hotspot-list">{clusters.map(cluster => <button key={cluster.id} className={`hotspot-row ${selectedId === cluster.id ? 'selected' : ''}`} onClick={() => setSelectedId(cluster.id)} aria-pressed={selectedId === cluster.id}>
          <div className="hotspot-score" style={{ color: riskColors[cluster.level] || '#425e56' }}>{cluster.score}<small>/100</small></div><div className="hotspot-row-info"><strong>{cluster.suspected_disease}</strong><span>{cluster.villages.join(', ')} · {cluster.animal_count} animals · {cluster.case_count} reports</span><Badge value={cluster.status}/></div><ChevronRight size={17}/>
        </button>)}</div> : <Empty title="No active cluster in this selection">Reports remain visible as individual observations. An isolated report does not automatically declare an outbreak.</Empty>}
      </Panel>{selected ? <HotspotDetails cluster={selected}/> : <Panel title="Hotspot evidence"><Empty title="Inspect the calculation">Select a hotspot from the map or list to see its score factors, reporting period and latest reports.</Empty></Panel>}</div>
    </>}
    {user!.role === 'admin' && <DemoReplayPanel refresh={resource.refresh}/>}
  </>
}
