import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { ArrowUpRight, Check, MessageCircle, Mic, Minimize2, ShieldCheck, Volume2, VolumeX, X } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'
import { catalog, label, localIntent, statusText, text } from './catalog'
import type { Language, TargetId } from './catalog'
import { mergeObservations, observationItems, parseObservations } from './conversation'
import type { Parsed } from './conversation'
import { contextSnapshot, locateGuide } from './registry'
import type { GuidePosition } from './registry'
import { assistantAnimals, askAssistant, capabilities, checkConcern } from './client'
import type { Concern } from './client'
import type { Animal } from '../../types'
import { Mascot } from './Mascot'
import { useVoice } from './useVoice'
import './assistant.css'

interface Turn {who:'user'|'mitra';message:string}
export function PashuMitra() {
  const {user}=useAuth(), {pathname}=useLocation()
  const [open,setOpen]=useState(false),[input,setInput]=useState(''),[language,setLanguage]=useState<Language>('en')
  const [turns,setTurns]=useState<Turn[]>([]),[consent,setConsent]=useState(false),[external,setExternal]=useState(false),[provider,setProvider]=useState(false),[speechConsent,setSpeechConsent]=useState(false)
  const [busy,setBusy]=useState(false),[muted,setMuted]=useState(true),[notice,setNotice]=useState('')
  const [guide,setGuide]=useState<GuidePosition|null>(null),[target,setTarget]=useState<TargetId|null>(null)
  const [parsed,setParsed]=useState<Parsed|null>(null),[animals,setAnimals]=useState<Animal[]>([]),[animalId,setAnimalId]=useState(''),[verified,setVerified]=useState(false),[concern,setConcern]=useState<Concern|null>(null)
  const generation=useRef(0),pending=useRef<AbortController|null>(null),guideTimer=useRef<ReturnType<typeof setTimeout>|null>(null)
  const voice=useVoice(language,speechConsent,muted,question=>void send(question))
  const speakRef=useRef(voice.speak);speakRef.current=voice.speak
  const stopRef=useRef(voice.stop);stopRef.current=voice.stop
  const cancel=()=>{generation.current++;pending.current?.abort();pending.current=null;setBusy(false);stopRef.current()}
  const clearGuide=()=>{setGuide(null);setTarget(null);if(guideTimer.current)clearTimeout(guideTimer.current)}
  const resetSymptoms=()=>{setParsed(null);setVerified(false);setConcern(null);setAnimalId('')}
  useEffect(()=>{
    cancel();clearGuide()
    if(/^\/animals\/[^/]+/.test(pathname)){resetSymptoms();setTurns([])}
    return()=>{generation.current++;pending.current?.abort();stopRef.current();if(guideTimer.current)clearTimeout(guideTimer.current)}
  },[pathname,user?.id])
  useEffect(()=>{const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){cancel();clearGuide();setOpen(false)}};document.addEventListener('keydown',escape);return()=>document.removeEventListener('keydown',escape)},[])
  useEffect(()=>{const hide=()=>{if(document.hidden){cancel();clearGuide()}};document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide)},[])
  useEffect(()=>{
    if(!target || !consent || !user)return
    const update=()=>setGuide(locateGuide(target,user.role,language,consent,pathname))
    let frame=0
    const schedule=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(update)}
    window.addEventListener('scroll',schedule,true);window.addEventListener('resize',schedule)
    const observer=new MutationObserver(records=>{if(records.some(r=>!(r.target instanceof Element)||!r.target.closest('.pashumitra')))schedule()});observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','hidden','disabled']})
    return()=>{cancelAnimationFrame(frame);observer.disconnect();window.removeEventListener('scroll',schedule,true);window.removeEventListener('resize',schedule)}
  },[target,consent,user?.role,language,pathname])
  useEffect(()=>{const animalChanged=()=>{cancel();clearGuide();resetSymptoms();setTurns([])};window.addEventListener('pashumitra:animal-changed',animalChanged);return()=>window.removeEventListener('pashumitra:animal-changed',animalChanged)},[])
  if(!user)return null
  const t=(en:string,hi:string)=>language==='hi'?hi:en
  const fieldRole=['farmer','paravet'].includes(user.role)
  const append=(message:string,who:Turn['who']='mitra')=>{setTurns(v=>[...v.slice(-9),{who,message}]);if(who==='mitra')speakRef.current(message)}
  function show(id:TargetId, prefix='') {
    cancel();clearGuide()
    if(!consent){append(text('consent',language));return}
    const result=locateGuide(id,user!.role,language,true,pathname)
    if(!result){append(text('missing',language));return}
    setTarget(id);setGuide(result);append(prefix+result.message)
    guideTimer.current=setTimeout(clearGuide,12000)
  }
  async function send(spoken?:string) {
    const question=(spoken??input).trim();if(!question || question.length>1200)return
    cancel();clearGuide();setInput('');setNotice('');append(question,'user')
    const result=parseObservations(question)
    const mentionedStatus=Object.keys(catalog.statuses).find(s=>question.toLowerCase().includes(s.replaceAll('_',' ')))
    if(mentionedStatus && /mean|matlab|explain|मतलब|अर्थ/i.test(question)){append(statusText(mentionedStatus,language)!);return}
    if(result.mixed){resetSymptoms();append(text('mixed',language));return}
    if(result.found && fieldRole && !/checkbox|which option|कौन सा विकल्प/i.test(question)){
      const merged=mergeObservations(parsed,result);setParsed(merged);setVerified(false);setConcern(null)
      append(observationItems(merged.observations,language).map(i=>i.description).join('; ')+'. '+text('clarify',language));return
    }
    if(result.found && fieldRole && /checkbox|which option|कौन सा विकल्प/i.test(question)){const first=observationItems(result.observations,language)[0];if(first){show(first.target);return}}
    const intent=localIntent(question,user!.role)
    if(intent.id==='denied'){append(text('denied',language));return}
    if(intent.target && intent.id!=='track'){show(intent.target);return}
    if(!navigator.onLine){if(intent.target)show(intent.target);else append(text('unknown',language));return}
    const controller=new AbortController();pending.current=controller;const token=++generation.current;setBusy(true)
    try{
      const response=await askAssistant(question,language,external,consent?contextSnapshot(pathname,user!.role):null,controller.signal)
      if(token!==generation.current)return
      setBusy(false)
      if(response.case_status){if(response.target)show(response.target as TargetId,statusText(response.case_status,language)+' ');else append(statusText(response.case_status,language)!)}
      else if(response.target)show(response.target as TargetId,response.message_key==='statusMissing'?text('statusMissing',language)+' ':'')
      else append(text(response.message_key,language))
    }catch{if(token===generation.current){setBusy(false);append(text('offline',language))}}
  }
  async function loadAnimals() {
    if(!consent){append(text('consent',language));return}
    cancel();const controller=new AbortController();pending.current=controller;const token=++generation.current;setBusy(true)
    try{const list=await assistantAnimals(controller.signal);if(token===generation.current){setAnimals(list);setBusy(false);if(!list.length)setNotice(t('No available animal records. Register an animal first.','पहले पशु का रिकॉर्ड दर्ज करें।'))}}
    catch{if(token===generation.current){setBusy(false);setNotice(text('offline',language))}}
  }
  async function verify() {
    if(!parsed || !animalId || parsed.ambiguous.length || !consent)return
    cancel();setVerified(true);append(text('verified',language));setConcern(null)
    if(!navigator.onLine){setNotice(text('offline',language));return}
    const controller=new AbortController();pending.current=controller;const token=++generation.current;setBusy(true)
    try{const result=await checkConcern(animalId,parsed.observations,controller.signal);if(token===generation.current){setConcern(result);setBusy(false);append(text(result.message_key,language))}}
    catch{if(token===generation.current){setBusy(false);setNotice(text('offline',language))}}
  }
  const items=parsed?observationItems(parsed.observations,language):[]
  return <div className="pashumitra" data-testid="pashumitra">
    {open && !guide && <section className="mitra-panel" aria-label="PashuMitra companion">
      <header><span className="mitra-avatar"><Mascot state={voice.state!=='idle'?voice.state:busy?'thinking':'idle'}/></span><div><strong>PashuMitra</strong><small>{t('Your livestock companion','आपका पशु स्वास्थ्य साथी')}</small></div><button type="button" aria-label="Minimize PashuMitra" onClick={()=>{cancel();clearGuide();setOpen(false)}}><Minimize2 size={17}/></button><button type="button" aria-label="Close and clear PashuMitra" onClick={()=>{cancel();clearGuide();resetSymptoms();setTurns([]);setInput('');setExternal(false);setConsent(false);setSpeechConsent(false);setAnimals([]);setOpen(false)}}><X size={18}/></button></header>
      <div className="mitra-body">
        <div className="mitra-language"><label>{t('Language','भाषा')}<select aria-label="PashuMitra language" value={language} onChange={e=>{cancel();clearGuide();setLanguage(e.target.value as Language)}}><option value="en">English</option><option value="hi">हिन्दी</option><option value="hinglish">Hinglish</option></select></label><button type="button" aria-label={muted?'Unmute PashuMitra':'Mute PashuMitra'} onClick={()=>{voice.stop();setMuted(v=>!v);if(muted){const last=turns.filter(turn=>turn.who==='mitra').at(-1);if(last)voice.speak(last.message,true)}}}>{muted?<VolumeX size={18}/>:<Volume2 size={18}/>}</button></div>
        <div className="mitra-privacy"><ShieldCheck size={16}/><span>{t('I point and explain. You click, select and submit.','मैं विकल्प दिखाता हूँ। क्लिक, चयन और सबमिट आप करते हैं।')}</span></div>
        <label className="mitra-consent"><input type="checkbox" checked={consent} onChange={e=>{cancel();clearGuide();setConsent(e.target.checked);if(!e.target.checked){resetSymptoms();setAnimals([])}}}/><span>{t('Allow current-page guidance','इस पेज के मार्गदर्शन की अनुमति दें')}<small>{t('Registered controls only; no screenshots or form contents. Uncheck to revoke.','केवल विकल्पों के नाम; स्क्रीनशॉट या फ़ॉर्म की जानकारी नहीं। अनुमति कभी भी हटाएं।')}</small></span></label>
        <label className="mitra-consent"><input type="checkbox" checked={speechConsent} onChange={e=>{voice.stop();setSpeechConsent(e.target.checked)}}/><span>{t('Allow browser speech processing','ब्राउज़र की आवाज़ सेवा की अनुमति दें')}<small>{t('Microphone starts only when tapped. Your browser may send audio or spoken text to its speech service. Stops after one turn or 20 seconds.','माइक केवल दबाने पर चालू होगा। ब्राउज़र अपनी आवाज़ सेवा को ऑडियो या पाठ भेज सकता है। एक बारी या 20 सेकंड बाद बंद होगा।')}</small></span></label>
        <p className="mitra-voice-status" role="status">{voice.state==='listening'?t('Listening… tap Stop when finished.','सुन रहा हूँ… समाप्त करने के लिए रोकें दबाएं।'):voice.state==='speaking'?t('Speaking…','बोल रहा हूँ…'):muted?t('Text mode · tap the speaker for spoken replies.','पाठ मोड · आवाज़ में जवाब के लिए स्पीकर दबाएं।'):t('Spoken replies enabled.','आवाज़ में जवाब चालू है।')}</p>
        {voice.error&&<p className="mitra-notice" role="status">{voice.error}</p>}
        {provider && <label className="mitra-consent"><input type="checkbox" checked={external} onChange={e=>{cancel();setExternal(e.target.checked)}}/><span>{t('Allow external language understanding','बाहरी भाषा सेवा की अनुमति दें')}<small>{t('Unrecognized questions may send sanitized text to Google Gemini. No animal records or page contents are sent.','अनपहचाने सवाल का सीमित पाठ Google Gemini को भेजा जा सकता है। पशु रिकॉर्ड या पेज की जानकारी नहीं भेजी जाती।')}</small></span></label>}
        <div className="mitra-transcript" aria-live="polite" aria-relevant="additions" role="log">{turns.map((turn,i)=><p key={i} className={`mitra-turn ${turn.who}`}>{turn.message}</p>)}{busy&&<p role="status">{t('Thinking…','सोच रहा हूँ…')}</p>}</div>
        {notice&&<p className="mitra-notice" role="status">{notice}</p>}
        {parsed && fieldRole && <section className="mitra-observations" aria-label="PashuMitra observations"><strong>{t('Verify what you observed','बताए गए लक्षण जांचें')}</strong><ul>{items.map(i=><li key={i.key}><span>{i.description}</span>{verified&&<button type="button" aria-label={`Show ${i.description} control`} onClick={()=>show(i.target,i.description+'. ')}><ArrowUpRight size={15}/>{t('Show','दिखाएं')}</button>}</li>)}</ul>
          {!!parsed.ambiguous.length&&<p>{t('Some observations are uncertain or contradictory. Describe them again before verification.','कुछ बातें अनिश्चित या विरोधी हैं। सत्यापन से पहले फिर बताइए।')}</p>}
          <button type="button" className="mitra-secondary" disabled={!consent||busy} onClick={()=>void loadAnimals()}>{t('Load my animals for verification','सत्यापन के लिए मेरे पशु लाएं')}</button>
          <label>{t('Animal for this conversation','इस बातचीत का पशु')}<select aria-label="PashuMitra animal" value={animalId} onChange={e=>{cancel();if(animalId){setParsed(null);setTurns([{who:'mitra',message:text('mixed',language)}])}setAnimalId(e.target.value);setVerified(false);setConcern(null)}}><option value="">{t('Choose one animal','एक पशु चुनें')}</option>{animals.map(a=><option key={a.id} value={a.id}>{a.name} · {a.pashu_id}</option>)}</select></label>
          <button type="button" className="mitra-primary" disabled={!animalId||!consent||!!parsed.ambiguous.length||busy||verified} onClick={()=>void verify()}><Check size={16}/>{verified?t('Verified for this animal','इस पशु के लिए सत्यापित'):t('These observations are correct','ये लक्षण सही हैं')}</button>
          {concern&&<div className={`mitra-concern ${concern.message_key}`}><p>{text(concern.message_key,language)}</p><small>{t('Existing rule engine • no numeric score from incomplete information','मौजूदा नियम प्रणाली • अधूरी जानकारी से अंक नहीं बनाए गए')}</small><details><summary>{t('Evidence and missing information','कारण और अधूरी जानकारी')}</summary><ul>{concern.triggered_rules.map(s=><li key={s}>{s}</li>)}</ul><p>{t('Unknown','अज्ञात')}: {concern.missing_information.join(', ')}</p></details></div>}
          <button type="button" className="mitra-text" onClick={()=>{cancel();resetSymptoms();setTurns([])}}>{t('Start over / different animal','फिर शुरू करें / दूसरा पशु')}</button>
        </section>}
        <div className="mitra-topics">{(fieldRole?['nav-report','nav-cases','animal-photo','register-animal']:user.role==='vet'?['vet-queue','vet-diagnosis','sample-request']:user.role==='lab'?['lab-requests','lab-result']:['outbreak-map','admin-clusters']).map(id=><button type="button" key={id} onClick={()=>show(id as TargetId)}>{label(id as TargetId,language)}</button>)}</div>
      </div>
      <form className="mitra-input" onSubmit={e=>{e.preventDefault();void send()}}><label className="sr-only" htmlFor="mitra-question">Ask PashuMitra</label><textarea id="mitra-question" value={input} onChange={e=>setInput(e.target.value)} maxLength={1200} rows={2} placeholder={t('Describe symptoms or ask for help…','लक्षण बताएं या मदद मांगें…')}/><div><button type="button" aria-label={voice.state==='listening'?'Stop listening':voice.state==='speaking'?'Stop speaking':'Talk to PashuMitra'} aria-pressed={voice.state==='listening'} disabled={busy} onClick={()=>{if(voice.state!=='idle')voice.stop();else voice.listen()}}><Mic size={18}/><span>{voice.state!=='idle'?t('Stop','रोकें'):t('Talk','बोलें')}</span></button><button type="submit" disabled={busy||!input.trim()} className="mitra-primary">{t('Ask','पूछें')}</button></div></form>
    </section>}
    {guide&&<div className="mitra-guide" aria-live="polite">{guide.box&&<div data-testid="mitra-highlight" className="mitra-highlight" style={guide.box}/>}<div className="mitra-traveller" style={{left:guide.x,top:guide.y}}><Mascot state="guiding"/><ArrowUpRight className="mitra-point" style={guide.box?{transform:`rotate(${Math.atan2(guide.box.top+guide.box.height/2-guide.y-17,guide.box.left+guide.box.width/2-guide.x-99)*180/Math.PI+45}deg)`}:undefined}/><span>{guide.message}</span></div></div>}
    <button type="button" className="mitra-launcher" aria-label={guide?'Stop PashuMitra guidance':open?'Minimize PashuMitra':'Open PashuMitra'} aria-expanded={open} onClick={()=>{cancel();if(guide){clearGuide();setOpen(true);return}setOpen(v=>!v);if(!open){if(!turns.length)append(text('intro',language));const token=generation.current;void capabilities().then(c=>{if(token===generation.current)setProvider(c.provider_available)}).catch(()=>{if(token===generation.current)setProvider(false)})}}}>{guide?<MessageCircle size={27}/>:<Mascot state="idle"/>}<span>{guide?t('Back to chat','बातचीत पर लौटें'):t('PashuMitra','पशुमित्र')}</span></button>
  </div>
}
