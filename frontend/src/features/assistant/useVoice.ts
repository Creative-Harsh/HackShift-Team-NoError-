import { useEffect, useRef, useState } from 'react'
import type { Language } from './catalog'

interface Recognition {
  lang:string; continuous:boolean; interimResults:boolean; maxAlternatives:number
  onresult:((event:{results:ArrayLike<ArrayLike<{transcript:string}>>})=>void)|null
  onerror:((event:{error:string})=>void)|null; onend:(()=>void)|null
  start():void; abort():void
}
type SpeechWindow = Window & { SpeechRecognition?:new()=>Recognition; webkitSpeechRecognition?:new()=>Recognition }

/** Voice is an explicit, bounded session. No restart, background capture or audio storage. */
export function useVoice(language:Language, consent:boolean, muted:boolean, onText:(text:string)=>void) {
  const [state,setState]=useState<'idle'|'listening'|'speaking'>('idle'),[error,setError]=useState('')
  const recognition=useRef<Recognition|null>(null),timer=useRef<ReturnType<typeof setTimeout>|null>(null),epoch=useRef(0)
  const callback=useRef(onText);callback.current=onText
  const locale=language==='en'?'en-IN':'hi-IN'
  const say=(en:string,hi:string)=>language==='hi'?hi:en
  const constructor=(window as SpeechWindow).SpeechRecognition||(window as SpeechWindow).webkitSpeechRecognition
  function stop() {
    epoch.current++
    if(timer.current){clearTimeout(timer.current);timer.current=null}
    const current=recognition.current;recognition.current=null
    if(current){current.onresult=null;current.onerror=null;current.onend=null;try{current.abort()}catch{/* Already ended. */}}
    window.speechSynthesis?.cancel();setState('idle')
  }
  function listen() {
    stop();setError('')
    if(!consent){setError(say('Allow browser speech processing before using the microphone.','माइक इस्तेमाल करने से पहले ब्राउज़र की आवाज़ सेवा को अनुमति दें।'));return}
    if(!constructor){setError(say('Voice input is unavailable in this browser. Type your question below.','इस ब्राउज़र में आवाज़ से इनपुट उपलब्ध नहीं है। नीचे अपना सवाल लिखें।'));return}
    if(!navigator.onLine){setError(say('Voice recognition may need internet. Type your question while offline.','आवाज़ पहचानने के लिए इंटरनेट चाहिए हो सकता है। ऑफलाइन अपना सवाल लिखें।'));return}
    const current=new constructor(),token=epoch.current
    recognition.current=current;current.lang=locale;current.continuous=false;current.interimResults=false;current.maxAlternatives=1
    current.onresult=event=>{
      if(token!==epoch.current)return
      const transcript=Array.from(event.results).map(r=>r[0]?.transcript||'').join(' ').trim().slice(0,1200)
      stop();if(transcript)callback.current(transcript)
    }
    current.onerror=event=>{
      if(token!==epoch.current)return
      stop()
      setError(event.error==='not-allowed'||event.error==='service-not-allowed'
        ?say('Microphone permission was denied. You can type instead.','माइक की अनुमति नहीं मिली। आप सवाल लिख सकते हैं।')
        :say('Voice input could not finish. Please try again or type your question.','आवाज़ से इनपुट पूरा नहीं हुआ। फिर कोशिश करें या सवाल लिखें।'))
    }
    current.onend=()=>{if(token===epoch.current)stop()}
    try{current.start();setState('listening');timer.current=setTimeout(()=>{stop();setError(say('Listening stopped after 20 seconds. Tap the microphone to start again.','20 सेकंड बाद माइक बंद हो गया। फिर शुरू करने के लिए माइक दबाएं।'))},20000)}
    catch{stop();setError(say('The microphone could not start. Type your question instead.','माइक चालू नहीं हो पाया। अपना सवाल लिखें।'))}
  }
  function speak(value:string, force=false) {
    if(muted&&!force)return
    stop();setError('')
    if(!window.speechSynthesis||!window.SpeechSynthesisUtterance){setError(say('Spoken replies are unavailable. Read the transcript below.','आवाज़ में जवाब उपलब्ध नहीं है। नीचे जवाब पढ़ें।'));return}
    const voices=window.speechSynthesis.getVoices().filter(v=>v.lang.toLowerCase().startsWith(locale.slice(0,2)))
    const voice=voices.find(v=>v.localService)|| (consent?voices[0]:undefined)
    if(!voice){setError(say('No permitted voice for this language is available yet. Use text, or enable browser speech processing and retry.','इस भाषा की अनुमत आवाज़ उपलब्ध नहीं है। पाठ पढ़ें या ब्राउज़र की आवाज़ सेवा सक्षम करके फिर कोशिश करें।'));return}
    // Hindi voices often misread Roman Hindi; the Hinglish transcript remains
    // visible. Use the English voice for Roman text when available.
    const utterance=new SpeechSynthesisUtterance(value.slice(0,1800)),token=epoch.current
    utterance.voice=language==='hinglish'?(window.speechSynthesis.getVoices().find(v=>v.lang.startsWith('en')&&(v.localService||consent))||voice):voice
    utterance.lang=utterance.voice.lang;utterance.rate=.94
    utterance.onstart=()=>{if(token===epoch.current)setState('speaking')}
    utterance.onend=()=>{if(token===epoch.current)setState('idle')}
    utterance.onerror=()=>{if(token===epoch.current){setState('idle');setError(say('Spoken reply could not play. The transcript is available.','आवाज़ में जवाब नहीं चल पाया। पाठ में जवाब उपलब्ध है।'))}}
    window.speechSynthesis.speak(utterance)
  }
  useEffect(()=>{
    // Warm up voice inventory without speaking or accessing the microphone.
    window.speechSynthesis?.getVoices()
    const hidden=()=>{if(document.hidden)stop()}
    document.addEventListener('visibilitychange',hidden)
    return()=>{stop();document.removeEventListener('visibilitychange',hidden)}
  },[])
  useEffect(()=>{stop();setError('')},[language,consent])
  return {state,error,supported:!!constructor,listen,speak,stop}
}
