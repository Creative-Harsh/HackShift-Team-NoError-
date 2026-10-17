import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, Search, PawPrint, MapPin } from 'lucide-react'
import { endpoints, errorMessage } from '../services/api'
import { useResource } from '../hooks/useResource'
import { useAuth } from '../features/auth/AuthContext'
import { Badge, Empty, ErrorNotice, Loading, PageHeader, Panel, human } from '../components/ui'
export function AnimalsPage() {
  const { user } = useAuth()
  const { data, loading, error, reload } = useResource(endpoints.animals)
  const [query, setQuery] = useState('')
  const [lookupError, setLookupError] = useState('')
  const [busy, setBusy] = useState(false)
  const navigate = useNavigate()
  const writable = ['farmer', 'paravet'].includes(user!.role)
  return <><PageHeader eyebrow="DIGITAL HEALTH RECORDS" title={user!.role === 'farmer' ? 'My animals' : 'Animal records'} description="One identity. An ongoing record of health and care." action={writable && <Link data-guide="register-animal" className="button primary" to="/animals/new"><Plus size={18}/>Register animal</Link>}/>
  <Panel className="lookup-panel"><form onSubmit={async e => { e.preventDefault(); setLookupError(''); if (!/^\d{12}$/.test(query)) { setLookupError('Enter the complete 12-digit simulated Pashu Aadhaar.'); return } setBusy(true); try { const a = await endpoints.lookup(query); navigate(`/animals/${a.id}`) } catch(e) { setLookupError(errorMessage(e)) } finally { setBusy(false) } }}><div><h2>Find by Pashu Aadhaar</h2><p>Bharat Pashudhan-compatible identity simulation</p></div><div className="lookup-control"><Search size={20}/><input data-guide="animal-lookup" aria-label="12-digit Pashu Aadhaar" inputMode="numeric" pattern="[0-9]{12}" maxLength={12} placeholder="Enter 12-digit animal ID" value={query} onChange={e => setQuery(e.target.value.replace(/\D/g, ''))}/><button className="button primary" disabled={busy}>{busy ? 'Finding…' : 'Find record'}</button></div></form>{lookupError && <ErrorNotice message={lookupError}/>}</Panel>
  {error && <ErrorNotice message={error} retry={reload}/>}{loading ? <Loading/> : !data?.length ? <Empty title="Your animal records start here">Register an animal to build its health history.</Empty> : <div data-guide="animal-list" className="animal-grid">{data.map(a => <Link className="animal-card" to={`/animals/${a.id}`} key={a.id}><div className="animal-card-top"><span className="animal-icon"><PawPrint size={27}/></span><Badge value={a.health_status || 'healthy'}/></div><h2>{a.name}</h2><p className="muted">{human(a.breed)} · {human(a.species)}</p><div className="pashu-id">{a.pashu_id.replace(/(\d{4})(?=\d)/g, '$1 ')}</div><dl><div><dt>Age</dt><dd>{a.age_months} months</dd></div><div><dt>Owner</dt><dd>{a.owner_name}</dd></div></dl><footer><MapPin size={14}/>{a.village}<span>View record →</span></footer></Link>)}</div>}</>
}
