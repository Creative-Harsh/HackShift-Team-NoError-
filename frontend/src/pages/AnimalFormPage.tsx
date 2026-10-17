import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, LocateFixed, Save } from 'lucide-react'
import { endpoints, errorMessage } from '../services/api'
import { useAuth } from '../features/auth/AuthContext'
import { ErrorNotice, Field, Loading, PageHeader, Panel } from '../components/ui'
import type { FarmerOption } from '../types'
const schema = z.object({ name: z.string().min(1, 'Enter an animal name').max(80), pashu_id: z.string().refine(v => !v || /^\d{12}$/.test(v), 'Use exactly 12 digits'), species: z.enum(['cattle','buffalo','goat','sheep','pig']), breed: z.string().min(1, 'Enter a breed'), age_months: z.number().int().min(0).max(480), gender: z.enum(['female','male']), owner_id: z.string().optional(), longitude: z.number().min(-180).max(180), latitude: z.number().min(-90).max(90), village: z.string().min(1, 'Enter a village'), district: z.string().min(1) })
type Values = z.infer<typeof schema>
export function AnimalFormPage() {
  const { id } = useParams(); const { user } = useAuth(); const navigate = useNavigate()
  const [error, setError] = useState(''); const [loading, setLoading] = useState(!!id); const [farmers, setFarmers] = useState<FarmerOption[]>([])
  const { register, handleSubmit, reset, setValue, formState: { errors, isSubmitting } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { name: '', pashu_id: '', species: 'cattle', breed: '', age_months: 36, gender: 'female', longitude: 73.8567, latitude: 18.5204, village: '', district: user!.district } })
  useEffect(() => {
    if (user!.role === 'paravet') endpoints.farmers().then(setFarmers).catch(e => setError(errorMessage(e)))
    if (id) endpoints.animal(id).then(a => reset({ ...a, pashu_id: a.pashu_id, species: a.species as Values['species'], longitude: a.location.coordinates[0], latitude: a.location.coordinates[1] })).catch(e => setError(errorMessage(e))).finally(() => setLoading(false))
  }, [id, user, reset])
  const gps = () => { setError(''); if (!navigator.geolocation) { setError('GPS is unavailable. Enter coordinates manually.'); return } navigator.geolocation.getCurrentPosition(p => { setValue('longitude', Number(p.coords.longitude.toFixed(6))); setValue('latitude', Number(p.coords.latitude.toFixed(6))) }, () => setError('Location permission was unavailable. Enter coordinates manually.')) }
  return <><Link className="back-link" to={id ? `/animals/${id}` : '/animals'}><ArrowLeft size={16}/>Back to records</Link><PageHeader eyebrow="ANIMAL REGISTRY" title={id ? 'Update animal record' : 'Register an animal'} description="Start with the basics. Every future report connects to this record."/>{error && <ErrorNotice message={error}/>}{loading ? <Loading/> : <form onSubmit={handleSubmit(async values => { setError(''); if (user!.role === 'paravet' && !values.owner_id) { setError('Select the farmer who owns this animal.'); return } try { const { longitude, latitude, ...rest } = values; const animal = await endpoints.saveAnimal({ ...rest, pashu_id: rest.pashu_id || undefined, owner_id: user!.role === 'farmer' ? undefined : values.owner_id, location: { type: 'Point', coordinates: [longitude, latitude] } }, id); navigate(`/animals/${animal.id}`) } catch(e) { setError(errorMessage(e)) } })} className="form-stack max-form">
  <Panel title="Animal identity" subtitle="Bharat Pashudhan-compatible identity simulation"><div className="form-grid padded">
    <Field label="Animal name" error={errors.name?.message}><input {...register('name')} placeholder="e.g. Gauri"/></Field><Field label="Simulated 12-digit Pashu Aadhaar" error={errors.pashu_id?.message} hint="Leave empty to generate an identity automatically."><input inputMode="numeric" maxLength={12} {...register('pashu_id')}/></Field>
    <Field label="Species" error={errors.species?.message}><select {...register('species')}><option value="cattle">Cattle</option><option value="buffalo">Buffalo</option><option value="goat">Goat</option><option value="sheep">Sheep</option><option value="pig">Pig</option></select></Field><Field label="Breed" error={errors.breed?.message}><input {...register('breed')} placeholder="e.g. Gir"/></Field>
    <Field label="Age in months" error={errors.age_months?.message}><input type="number" min={0} max={480} {...register('age_months', { valueAsNumber: true })}/></Field><Field label="Gender"><select {...register('gender')}><option value="female">Female</option><option value="male">Male</option></select></Field>
    {user!.role === 'paravet' && <Field label="Animal owner" error={errors.owner_id?.message}><select {...register('owner_id')}><option value="">Select a registered farmer</option>{farmers.map(f => <option key={f.id} value={f.id}>{f.name} · {f.email}</option>)}</select></Field>}
  </div></Panel><Panel title="Location" subtitle="Use the animal’s usual location; review coordinates before saving." action={<button type="button" className="button secondary compact" onClick={gps}><LocateFixed size={16}/>Use GPS</button>}><div className="form-grid padded"><Field label="Village" error={errors.village?.message}><input {...register('village')}/></Field><Field label="District" error={errors.district?.message}><input readOnly {...register('district')}/></Field><Field label="Latitude" error={errors.latitude?.message}><input type="number" step="any" {...register('latitude', { valueAsNumber: true })}/></Field><Field label="Longitude" error={errors.longitude?.message}><input type="number" step="any" {...register('longitude', { valueAsNumber: true })}/></Field></div></Panel>
  <div className="form-actions"><Link className="button secondary" to="/animals">Cancel</Link><button className="button primary" disabled={isSubmitting}><Save size={17}/>{isSubmitting ? 'Saving record…' : 'Save animal record'}</button></div></form>}</>
}
