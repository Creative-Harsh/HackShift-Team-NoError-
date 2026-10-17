import axios from 'axios'
import { api, TOKEN_KEY, errorMessage } from '../../services/api'
import type { DiseaseCase } from '../../types'
import { queueRows, saveRow, storedUserId } from './store'
let running: Promise<void> | null = null
export function syncReports(userId: string, force=false): Promise<void> {
  if(running)return running
  const perform=async()=>{
    const token=sessionStorage.getItem(TOKEN_KEY)
    const sameAccount=()=>storedUserId()===userId && sessionStorage.getItem(TOKEN_KEY)===token
    if(!token || !navigator.onLine || !sameAccount())return
    for(const row of (await queueRows(userId)).reverse()) {
      if(!sameAccount() || !navigator.onLine)return
      if(row.state==='synced' || row.state==='blocked' || (!force && row.nextAttempt>Date.now()))continue
      row.state='syncing';row.attempts++;await saveRow(row)
      try {
        for(const attachment of row.attachments) {
          if(!sameAccount()) {row.state='queued';await saveRow(row);return}
          if(!attachment.url) {
            const form=new FormData();form.append('file',attachment.file,attachment.name);form.append('kind',attachment.kind);form.append('client_upload_id',attachment.id)
            const {data}=await api.post<{url:string}>('/media',form,{headers:{Authorization:`Bearer ${token}`}})
            attachment.url=data.url
            if(attachment.kind==='image')row.payload.image_url=data.url;else row.payload.voice_note_url=data.url
            await saveRow(row)
          }
        }
        if(!sameAccount()) {row.state='queued';await saveRow(row);return}
        const {data}=await api.post<DiseaseCase>('/reports',row.payload,{headers:{Authorization:`Bearer ${token}`}})
        row.state='synced';row.caseId=data.id;row.error=undefined;row.attachments=[]
      } catch(error) {
        const status=axios.isAxiosError(error)?error.response?.status:undefined
        row.state=status && status>=400 && status<500 && ![401,408,429].includes(status)?'blocked':'queued'
        row.error=status===401?'Sign in again to sync this report.':errorMessage(error)
        row.nextAttempt=Date.now()+Math.min(60000,2000*2**Math.min(row.attempts,5))
        await saveRow(row)
        if(!status || status===401 || status>=500)return
        continue
      }
      await saveRow(row)
    }
  }
  const attempt = (async () => {
    if (navigator.locks) await navigator.locks.request('pashuraksha-report-sync', perform)
    else await perform()
  })()
  running=attempt.finally(()=>{running=null})
  return running
}
