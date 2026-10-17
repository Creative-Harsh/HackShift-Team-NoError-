import { CareActions } from '../features/workflow/CareActions'
import { PrivateAttachment } from '../components/PrivateAttachment'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle2, Clock, MapPin, RefreshCw } from 'lucide-react'
import { useResource } from '../hooks/useResource'
import { endpoints } from '../services/api'
import { Badge, ErrorNotice, Loading, PageHeader, Panel, SafetyNotice, dateTime, human } from '../components/ui'
import { ReasoningPanel, RiskPanel, SafeActionsPanel, TriagePanel } from '../features/assessment/AssessmentPanels'

export function CaseDetailPage() {
  const { id } = useParams()
  const location = useLocation()
  const resource = useResource(() => endpoints.case(id!), id)
  const c = resource.data
  return <>
    <Link className="back-link" to="/cases"><ArrowLeft size={16}/>All reports</Link>
    {location.state?.submitted && <div className="success-notice" role="status"><CheckCircle2 size={19}/>Report submitted successfully. Your observations are saved in the animal’s health record.</div>}
    {resource.error && <ErrorNotice message={resource.error} retry={resource.reload}/>}
    {resource.loading ? <Loading/> : c && <>
      <PageHeader eyebrow={`HEALTH REPORT · ${c.id.slice(0, 8).toUpperCase()}`} title={`${c.animal_name}’s health report`}
        description={`${c.pashu_id} · ${c.village} · Reported ${dateTime(c.reported_at)}`}
        action={<div className="button-row"><Badge value={c.status}/><button className="button secondary compact" onClick={resource.reload}><RefreshCw size={16}/>Refresh</button></div>}/>
      <SafetyNotice/>
      <div className="case-layout"><div className="form-stack">
        <CareActions value={c} refresh={resource.reload}/><TriagePanel triage={c.triage}/>
        {(c.report.image_url || c.report.voice_note_url) && <Panel title="Report attachments"><div className="padded form-stack">
          {c.report.image_url && <PrivateAttachment url={c.report.image_url} label="Animal photo" kind="image"/>}
          {c.report.voice_note_url && <PrivateAttachment url={c.report.voice_note_url} label="Voice note" kind="audio"/>}
        </div></Panel>}
        {c.risk && <RiskPanel risk={c.risk}/>}
        {c.triage && <><SafeActionsPanel actions={c.triage.safe_actions || []}/><ReasoningPanel triage={c.triage}/></>}
        <Panel title="Recorded symptoms"><div className="padded">
          <div className="symptom-tags">{c.report.symptoms.length ? c.report.symptoms.map(symptom => <span key={symptom}>{human(symptom)}</span>) : <p className="muted">No listed symptoms selected.</p>}</div>
          <dl className="detail-list compact-details">
            <div><dt>Temperature</dt><dd>{c.report.temperature_c ? `${c.report.temperature_c} °C` : 'Not measured'}</dd></div>
            <div><dt>Appetite / activity</dt><dd>{human(c.report.appetite)} / {human(c.report.activity)}</dd></div>
            <div><dt>Milk production drop</dt><dd>{c.report.milk_drop_percent}%</dd></div>
            <div><dt>Duration</dt><dd>{c.report.duration_hours} hours</dd></div>
            <div><dt>Vaccination status</dt><dd>{human(c.report.vaccination_status)}</dd></div>
            <div><dt>Recent contact / movement</dt><dd>{c.report.recent_contact ? 'Yes' : 'No'}</dd></div>
            <div><dt>Herd mortality reported</dt><dd>{c.report.mortality_count}</dd></div>
            <div><dt>Report coordinates</dt><dd>{c.location.coordinates[1].toFixed(5)}, {c.location.coordinates[0].toFixed(5)}</dd></div>
          </dl>
        </div></Panel>
      </div><aside className="form-stack">
        <Panel guide="case-status" title="Care journey"><ol className="timeline padded">{c.timeline.map((event, index) => <li key={index}>
          <span className="timeline-dot"><Clock size={13}/></span><strong>{human(event.status)}</strong>
          {(event.at || event.timestamp) && <small>{dateTime((event.at || event.timestamp)!)}</small>}
          {event.note && <p>{event.note}</p>}
        </li>)}</ol></Panel>
        <Panel title="Linked animal record"><div className="padded"><h3>{c.animal_name}</h3><p className="mono">{c.pashu_id}</p>
          <p className="inline-icon muted"><MapPin size={16}/>{c.village}, {c.district}</p>
          <Link className="button secondary" to={`/animals/${c.animal_id}`}>View health history</Link>
        </div></Panel>
        <Panel title="Confirmation status"><div className="padded"><Badge value={c.confirmation_status}/>
          <p className="small muted">Confirmed disease and preliminary assessment are recorded separately.</p>
        </div></Panel>
      </aside></div>
    </>}
  </>
}

