import { useEffect, useState } from 'react'
import { api, errorMessage } from '../services/api'

export function PrivateAttachment({url,label,kind='download'}:{url:string;label:string;kind?:'image'|'audio'|'download'}) {
  const [source,setSource]=useState(''),[error,setError]=useState('')
  useEffect(()=>{
    setSource('');setError('')
    let objectUrl='',active=true
    const controller=new AbortController()
    void api.get<Blob>(url.replace(/^\/api/,''),{responseType:'blob',signal:controller.signal}).then(({data})=>{
      if(active){objectUrl=URL.createObjectURL(data);setSource(objectUrl)}
    }).catch(e=>{if(active)setError(errorMessage(e))})
    return()=>{active=false;controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl)}
  },[url])
  return <div className="private-attachment">{error?<p role="alert">{error}</p>:source?<>
    {kind==='image'&&<img src={source} alt={label}/>}{kind==='audio'&&<audio src={source} controls aria-label={label}/>}
    <a className="text-link" href={source} download={label}>{kind==='download'?label:'Download '+label}</a>
  </>:<p>Loading {label.toLowerCase()}…</p>}</div>
}
