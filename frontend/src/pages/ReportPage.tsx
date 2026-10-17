import { useEffect, useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Activity, ArrowRight, Check, Droplets, HeartPulse, LocateFixed, ShieldCheck, Thermometer, Wind, CircleDot, Footprints, Waves } from 'lucide-react'
import { endpoints, errorMessage } from '../services/api'
import { useAuth } from '../features/auth/AuthContext'
import type { Attachment } from '../features/offline/store'
import { enqueue, queueRows } from '../features/offline/store'
import { syncReports } from '../features/offline/sync'
import { useResource } from '../hooks/useResource'
import { ErrorNotice, Field, Loading, PageHeader, Panel, SafetyNotice } from '../components/ui'
const symptoms = [ { key: 'fever', label: 'Fever', hint: 'बुखार', icon: Thermometer }, { key: 'cough', label: 'Coughing', hint: 'खांसी', icon: Wind }, { key: 'nasal_discharge', label: 'Nasal discharge', hint: 'नाक बहना', icon: Droplets }, { key: 'drooling', label: 'Drooling', hint: 'लार टपकना', icon: Droplets }, { key: 'skin_lesions', label: 'Skin lesions / nodules', hint: 'त्वचा पर गांठें', icon: CircleDot }, { key: 'mouth_foot_lesions', label: 'Mouth / foot lesions', hint: 'मुंह या पैर में घाव', icon: Footprints }, { key: 'diarrhea', label: 'Diarrhea', hint: 'दस्त', icon: Waves }, { key: 'weakness', label: 'Weakness', hint: 'कमजोरी', icon: Activity }, { key: 'swelling', label: 'Swelling', hint: 'सूजन', icon: HeartPulse } ]
const schema = z.object({ animal_id: z.string().min(1, 'Select an animal'), symptoms: z.array(z.string()), temperature_c: z.number().min(30).max(45).optional(), appetite: z.enum(['normal','reduced','none']), milk_drop_percent: z.number().min(0).max(100), activity: z.enum(['normal','reduced','recumbent']), recent_contact: z.boolean(), vaccination_status: z.enum(['up_to_date','overdue','unknown']), mortality_count: z.number().int().min(0).max(1000), duration_hours: z.number().min(0).max(2160), longitude: z.number().min(-180).max(180), latitude: z.number().min(-90).max(90) })
type Values = z.infer<typeof schema>
export function ReportPage() {
  const [params] = useSearchParams(); const navigate = useNavigate(); const animals = useResource(endpoints.animals); const { user } = useAuth()
  const [error, setError] = useState(''); const [offlineSaved, setOfflineSaved] = useState(false); const [attachments, setAttachments] = useState<Attachment[]>([]); const [gpsStatus, setGpsStatus] = useState('Location starts from the selected animal’s record. Review it before submitting.')
  const reportId = useRef(crypto.randomUUID())
  const { register, handleSubmit, watch, setValue, reset, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { animal_id: params.get('animal') || '', symptoms: [], appetite: 'normal', milk_drop_percent: 0, activity: 'normal', recent_contact: false, vaccination_status: 'unknown', mortality_count: 0, duration_hours: 24, longitude: 73.8567, latitude: 18.5204 } })
  const animalId = watch('animal_id'); const selectedSymptoms = watch('symptoms'); const animal = animals.data?.find(a => a.id === animalId)
  useEffect(() => { if (animal) { setValue('longitude', animal.location.coordinates[0]); setValue('latitude', animal.location.coordinates[1]); setGpsStatus(`Using ${animal.name}’s recorded location in ${animal.village}.`) } }, [animal, setValue])
  const gps = () => { if (!navigator.geolocation) { setGpsStatus('GPS is not supported. Enter coordinates manually.'); return } setGpsStatus('Finding your location…'); navigator.geolocation.getCurrentPosition(p => { setValue('longitude', Number(p.coords.longitude.toFixed(6))); setValue('latitude', Number(p.coords.latitude.toFixed(6))); setGpsStatus(`GPS captured. Approximate accuracy: ${Math.round(p.coords.accuracy)} metres.`) }, () => setGpsStatus('GPS unavailable or permission denied. Review the coordinates manually.'), { enableHighAccuracy: true, timeout: 15000 }) }
  async function submit(values: Values) {
    if(!user)return
    setError('')
    try {
      const { latitude, longitude, ...rest }=values
      await enqueue(user.id,{...rest, client_report_id:reportId.current, reported_at:new Date().toISOString(),
        location:{type:'Point',coordinates:[longitude,latitude]}},attachments)
      setOfflineSaved(true)
      await syncReports(user.id,true)
      const row=(await queueRows(user.id)).find(item=>item.payload.client_report_id===reportId.current)
      if(row?.state==='synced')navigate(`/cases/${row.caseId}`,{state:{submitted:true}})
    } catch(e) {setError(errorMessage(e))}
  }
  function chooseFile(kind: Attachment['kind'], file?: File) {
    setError('')
    if(file && file.size>8*1024*1024){setError('Choose an attachment no larger than 8 MB.');return}
    setAttachments(current=>[...current.filter(item=>item.kind!==kind),...(file?[{id:crypto.randomUUID(),kind,file,name:file.name}]:[])])
  }
  return <><PageHeader eyebrow="EARLY REPORTING · प्रारंभिक सूचना" title="How is your animal feeling?" description="Choose what you observe. A clear report helps the care team respond."/>
    <SafetyNotice/>{animals.error && <ErrorNotice message={animals.error} retry={animals.reload}/>}{error && <ErrorNotice message={error}/>}
    {offlineSaved ? <Panel title="Report saved on this device"><div className="padded form-stack"><p>Your observations are safely queued. Synchronization status and any errors appear below.</p>
      <button className="button secondary" onClick={()=>{reportId.current=crypto.randomUUID();setOfflineSaved(false);setAttachments([]);reset()}}>Create another report</button></div></Panel>
    : animals.loading ? <Loading/> : <form onSubmit={handleSubmit(submit)} className="report-layout"><div className="form-stack">
  <Panel title="1. Choose your animal" subtitle="The report is linked to its existing digital health record"><div className="padded"><Field label="Animal" error={errors.animal_id?.message}><select data-guide="animal-selector" {...register('animal_id',{onChange:()=>window.dispatchEvent(new Event('pashumitra:animal-changed'))})}><option value="">Select an animal</option>{animals.data?.map(a => <option value={a.id} key={a.id}>{a.name} · {a.pashu_id} · {a.village}</option>)}</select></Field>{!animals.data?.length && <p className="small muted">Register an animal before creating a report. <Link to="/animals/new">Add an animal</Link></p>}</div></Panel>
  <Panel title="2. What symptoms can you see?" subtitle="Select all that apply · जो लक्षण दिखें उन्हें चुनें"><div className="symptom-grid padded">{symptoms.map(s => <label data-guide={`symptom-${s.key}`} key={s.key} className={`symptom-option ${selectedSymptoms.includes(s.key) ? 'selected' : ''}`}><input type="checkbox" value={s.key} {...register('symptoms')}/><s.icon size={23}/><strong>{s.label}</strong><small>{s.hint}</small><span className="symptom-check">{selectedSymptoms.includes(s.key) && <Check size={13}/>}</span></label>)}</div></Panel>
  <Panel title="3. Health observations" subtitle="Use measured values where possible. Leave temperature blank if unknown."><div className="form-grid padded">
    <Field label="Temperature (°C)" error={errors.temperature_c?.message}><input data-guide="temperature" type="number" step="0.1" min={30} max={45} placeholder="e.g. 39.5" {...register('temperature_c', { setValueAs: v => v === '' ? undefined : Number(v) })}/></Field>
    <div><Field label="Symptoms noticed for (hours)" error={errors.duration_hours?.message}><input data-guide="duration" type="number" min={0} max={2160} {...register('duration_hours', { valueAsNumber: true })}/></Field><div className="duration-options" role="group" aria-label="Choose symptom duration">{[6,12,24,48,72].map(hours => <button key={hours} type="button" aria-pressed={watch('duration_hours') === hours} onClick={() => setValue('duration_hours', hours, { shouldValidate: true })}>{hours}h</button>)}</div></div>
    <Field label="Appetite"><select data-guide="appetite" {...register('appetite')}><option value="normal">Eating normally</option><option value="reduced">Eating less</option><option value="none">Not eating</option></select></Field>
    <Field label="Activity"><select data-guide="activity" {...register('activity')}><option value="normal">Moving normally</option><option value="reduced">Less active</option><option value="recumbent">Unable to stand / lying down</option></select></Field>
    <Field label="Milk production drop (%)" error={errors.milk_drop_percent?.message} hint="Enter 0 if unchanged or not applicable."><input data-guide="milk" type="number" min={0} max={100} {...register('milk_drop_percent', { valueAsNumber: true })}/></Field>
    <Field label="Deaths observed in the herd" error={errors.mortality_count?.message}><input data-guide="mortality" type="number" min={0} max={1000} {...register('mortality_count', { valueAsNumber: true })}/></Field>
    <Field label="Vaccination status"><select data-guide="vaccination-status" {...register('vaccination_status')}><option value="unknown">Not sure</option><option value="up_to_date">Up to date</option><option value="overdue">Overdue / not vaccinated</option></select></Field>
    <label data-guide="contact" className="large-checkbox"><input type="checkbox" {...register('recent_contact')}/><span><strong>Recent animal contact or movement</strong><small>New animals, shared grazing, market or travel</small></span></label>
  </div></Panel>
  <Panel title="4. Report location" subtitle={gpsStatus} action={<button type="button" className="button secondary compact" onClick={gps}><LocateFixed size={16}/>Use GPS</button>}><div className="form-grid padded"><Field label="Latitude" error={errors.latitude?.message}><input type="number" step="any" {...register('latitude', { valueAsNumber: true })}/></Field><Field label="Longitude" error={errors.longitude?.message}><input type="number" step="any" {...register('longitude', { valueAsNumber: true })}/></Field></div></Panel>
  <Panel title="5. Optional attachments" subtitle="Private attachments for the care team. Maximum 8 MB each; no automated image diagnosis or voice transcription."><div className="form-grid padded">
    <Field label="Animal photo"><input data-guide="animal-photo" type="file" accept="image/jpeg,image/png" onChange={event=>chooseFile('image',event.target.files?.[0])}/></Field>
    <Field label="Voice note file"><input data-guide="voice-note" type="file" accept="audio/mpeg,audio/wav,audio/ogg,audio/webm" onChange={event=>chooseFile('voice_note',event.target.files?.[0])}/></Field>
  </div></Panel>
  <div className="form-actions"><Link className="button secondary" to="/animals">Cancel</Link><button data-guide="submit-report" className="button primary" disabled={isSubmitting || !animals.data?.length}>{isSubmitting ? 'Submitting report…' : 'Submit health report'}<ArrowRight size={17}/></button></div>
  </div><aside className="report-summary"><Panel title="Before you submit"><div className="padded"><span className="icon-tile"><ShieldCheck/></span><h3>Observation comes first.</h3><p>This report records symptoms. A veterinarian makes the professional diagnosis.</p><ul className="plain-list"><li>Check the correct animal is selected.</li><li>Record only what you observe.</li><li>Review the report location.</li></ul><div className="summary-count"><strong>{selectedSymptoms.length}</strong> symptoms selected</div><p className="small muted">Reports and selected attachments are saved on this device before synchronization.</p></div></Panel></aside></form>}</>
}
