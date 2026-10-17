import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { queueRows } from './store'
import type { QueuedReport } from './store'
import { syncReports } from './sync'
import { ErrorNotice, Panel, dateTime, human } from '../../components/ui'
import { errorMessage } from '../../services/api'

export function QueuePanel() {
  const { user }=useAuth()
  const [rows,setRows]=useState<QueuedReport[]>([]), [error,setError]=useState('')
  useEffect(()=>{
    setRows([]);setError('')
    if(!user)return
    let live=true
    const load=()=>void queueRows(user.id).then(value=>{if(live)setRows(value)}).catch(e=>{if(live)setError(errorMessage(e))})
    const sync=()=>void syncReports(user.id).then(load).catch(e=>{if(live)setError(errorMessage(e))})
    load();sync()
    const timer=setInterval(sync,15000)
    window.addEventListener('online',sync);window.addEventListener('queue:changed',load)
    return()=>{live=false;clearInterval(timer);window.removeEventListener('online',sync);window.removeEventListener('queue:changed',load)}
  },[user?.id])
  if(!user || !['farmer','paravet'].includes(user.role))return null
  const pending=rows.filter(r=>r.state!=='synced'), success=rows.filter(r=>r.state==='synced')
  return <div className="offline-panel"><Panel title="Report synchronization" subtitle="Reports saved on this device for your account" action={<button className="button secondary compact" onClick={()=>void syncReports(user.id,true).catch(e=>setError(errorMessage(e)))}>Sync now</button>}>
    <div className="padded"><p role="status" data-testid="queue-counts"><strong>{pending.length}</strong> queued reports · <strong>{success.length}</strong> successful syncs</p>
      {error && <ErrorNotice message={error}/>}
      {pending.map(row=><div className="queue-row" key={row.key}><strong>{row.state==='blocked'?'Needs attention':row.state==='syncing'?'Synchronizing…':'Saved offline — waiting to sync.'}</strong><p>{dateTime(row.createdAt)} · {row.payload.symptoms.map(human).join(', ') || 'Structured observations'}</p>{row.error && <p role="alert">{row.error}{row.state==='blocked'?' This saved report needs correction in a new report; it will not be automatically resent.':''}</p>}</div>)}
      {success.slice(0,3).map(row=><div className="queue-row" key={row.key}><Link className="text-link" to={`/cases/${row.caseId}`}>Synced successfully. Open report →</Link><small>{dateTime(row.createdAt)}</small></div>)}
    </div>
  </Panel></div>
}
