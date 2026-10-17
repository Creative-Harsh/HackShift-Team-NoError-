import { useEffect, useState } from 'react'
import { useAuth } from '../auth/AuthContext'
import { api, errorMessage } from '../../services/api'
import { Badge, ErrorNotice, Field, Panel, dateTime, human } from '../../components/ui'
import type { DiseaseCase } from '../../types'
import { PrivateAttachment } from '../../components/PrivateAttachment'

export function CareActions({ value: c, refresh }: { value: DiseaseCase; refresh: () => void }) {
  const { user } = useAuth()
  const [busy, setBusy] = useState(false), [error, setError] = useState('')
  const [vets, setVets] = useState<{ id: string; name: string }[]>([]), [vet, setVet] = useState('')
  const [diagnosis, setDiagnosis] = useState(''), [recommendations, setRecommendations] = useState('')
  const [test, setTest] = useState(''), [code, setCode] = useState(c.triage?.disease_code === 'undifferentiated' ? '' : c.triage?.disease_code || '')
  const [note, setNote] = useState('')
  useEffect(() => { if (user?.role === 'admin') void api.get<{ id: string; name: string }[]>('/users/veterinarians').then(r => { setVets(r.data); setVet(r.data[0]?.id || '') }).catch(e => setError(errorMessage(e))) }, [user?.role])
  async function act(path: string, fields: Record<string, unknown>, method = 'put') {
    setBusy(true); setError('')
    try { await api.request({ method, url: `/cases/${c.id}/${path}`, data: { operation_id: crypto.randomUUID(), expected_version: c.version, ...fields } }); refresh() }
    catch (e) { setError(errorMessage(e)) } finally { setBusy(false) }
  }
  const assigned = user?.role === 'vet' && c.assigned_vet_id === user.id
  return <>
    {c.professional_review && <Panel title="Veterinarian’s review"><div className="padded"><p className="small muted">{c.professional_review.reviewer_name} · {dateTime(c.professional_review.date)}</p><h3>Professional assessment</h3><p className="preserve-lines">{c.professional_review.diagnosis}</p><h3>Recommendations</h3><p className="preserve-lines">{c.professional_review.recommendations}</p></div></Panel>}
    {!!c.lab_tests?.length && <Panel title="Laboratory evidence"><div className="padded form-stack">{c.lab_tests.map(t => <div key={t.id}><strong>{t.test_type}</strong> <Badge value={t.status}/><p className="small">Target category: {human(t.disease_code)} · Requested {dateTime(t.requested_at)}</p>{t.result_notes && <p>{t.result_notes}</p>}{t.attachment_url && <PrivateAttachment url={t.attachment_url} label="Laboratory report"/>}</div>)}</div></Panel>}
    {['vet', 'admin'].includes(user?.role || '') && <Panel title="Professional response" subtitle={c.assigned_vet_name ? `Assigned to ${c.assigned_vet_name}` : 'Awaiting assignment'}><div className="padded form-stack">
      {error && <ErrorNotice message={error} retry={refresh}/>}
      {['triage', 'vet_assigned', 'vet_review'].includes(c.status) && (user?.role === 'admin' || !c.assigned_vet_id) && <form className="form-stack" onSubmit={e => { e.preventDefault(); void act('assign-vet', user?.role === 'admin' ? { vet_id: vet } : {}, 'post') }}>
        {user?.role === 'admin' && <Field label="Assign veterinarian"><select required value={vet} onChange={e => setVet(e.target.value)}><option value="">Choose veterinarian</option>{vets.map(v => <option key={v.id} value={v.id}>{v.name}</option>)}</select></Field>}
        <button data-guide="vet-claim" className="button primary" disabled={busy}>{user?.role === 'vet' ? 'Claim case' : 'Assign case'}</button>
      </form>}
      {assigned && ['vet_assigned', 'vet_review'].includes(c.status) && <form className="form-stack" onSubmit={e => { e.preventDefault(); void act('vet-review', { diagnosis, recommendations }) }}>
        <Field label="Professional diagnosis / findings"><textarea data-guide="vet-diagnosis" required minLength={3} maxLength={2000} value={diagnosis} onChange={e => setDiagnosis(e.target.value)}/></Field>
        <Field label="Veterinary recommendations"><textarea data-guide="vet-recommendations" required minLength={3} maxLength={4000} value={recommendations} onChange={e => setRecommendations(e.target.value)}/></Field>
        <button className="button primary" disabled={busy}>Save veterinary review</button>
      </form>}
      {assigned && ['vet_review', 'inconclusive', 'rejected'].includes(c.status) && <form className="form-stack" onSubmit={e => { e.preventDefault(); void act('request-lab', { test_type: test, disease_code: code, notes: note }, 'post') }}>
        <Field label="Laboratory test requested"><input data-guide="sample-request" required minLength={3} maxLength={160} value={test} onChange={e => setTest(e.target.value)} placeholder="e.g. LSD PCR / lesion sample"/></Field>
        <Field label="Investigation category"><select required value={code} onChange={e => setCode(e.target.value)}><option value="">Choose category</option><option value="lsd">Lumpy Skin Disease</option><option value="fmd">Foot-and-Mouth Disease</option><option value="respiratory">Respiratory syndrome panel</option><option value="gastrointestinal">Gastrointestinal syndrome panel</option></select></Field>
        <Field label="Sample instructions"><textarea maxLength={2000} value={note} onChange={e => setNote(e.target.value)}/></Field>
        <button className="button primary" disabled={busy}>Request laboratory test</button>
      </form>}
      {assigned && ['vet_review', 'confirmed', 'rejected', 'inconclusive', 'treatment'].includes(c.status) && <form className="form-stack" onSubmit={e => { e.preventDefault(); void act('status', { status: c.status === 'treatment' ? 'closed' : 'treatment', note }) }}>
        <Field label="Treatment / control action note" hint="Professional decisions are recorded by the veterinarian. The system does not prescribe medicine."><textarea data-guide="treatment" required minLength={3} maxLength={4000} value={note} onChange={e => setNote(e.target.value)}/></Field>
        <button className="button secondary" disabled={busy}>{c.status === 'treatment' ? 'Close case' : 'Record treatment / control action'}</button>
      </form>}
      {['sample_requested', 'lab_pending'].includes(c.status) && <p>Awaiting laboratory processing. Sample receipt and results will update this care journey.</p>}
      {c.status === 'closed' && <p>This care episode is closed. Its evidence and timeline remain in the health record.</p>}
    </div></Panel>}
  </>
}
