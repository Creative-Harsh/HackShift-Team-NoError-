import { catalog } from './catalog'
import type { Language, TargetId } from './catalog'

export interface Observations { symptoms: Record<string,boolean|null>; appetite?: 'normal'|'reduced'|'none'; activity?:'normal'|'reduced'|'recumbent'; duration_hours?:number; temperature_c?:number; mortality_count?:number }
export interface Parsed { observations: Observations; ambiguous: string[]; mixed: boolean; found: boolean }
const negated=/(?:\b(?:no|not|without|neither|never|nahi|nahin)\b|नहीं|नही|बिना)/iu
const uncertain=/(?:\b(?:maybe|perhaps|possibly|unsure|shayad|pata nahi|not sure)\b|शायद|पता नहीं)/iu
const numbers:Record<string,number>={one:1,two:2,three:3,four:4,five:5,six:6,seven:7,eight:8,nine:9,ten:10,ek:1,do:2,teen:3,char:4,paanch:5,panch:5,'एक':1,'दो':2,'तीन':3,'चार':4,'पांच':5,'पाँच':5}

/** Conservative phrase extraction, never a diagnosis. Absent concepts remain absent. */
export function parseObservations(input: string): Parsed {
  const value=input.toLowerCase().replace(/[०-९]/g,c=>String(c.charCodeAt(0)-2406)).replaceAll('’',"'")
  const observations:Observations={symptoms:{}}, ambiguous:string[]=[]
  const mixed=/\b(?:another|other animal|second cow|both animals|dusri|do gai|do gaay)\b|दूसर[ाीे]|दो गाय|दो पशु|cow and (?:my )?buffalo|गाय और भैंस/iu.test(value)
  const clauses=value.split(/[,;.!?]|\b(?:but|and|aur|lekin)\b|और|लेकिन/iu)
  for(const concept of catalog.symptoms) {
    const states=clauses.filter(c=>new RegExp(concept.pattern,'iu').test(c)).map(c=>{
      // Without a conjunction, a negative appetite phrase has unclear scope.
      // Ask for clarification instead of turning a reported fever into "absent".
      if(uncertain.test(c)||(negated.test(c)&&/eating|khana|खाना/iu.test(c)))return null
      return !negated.test(c)
    })
    if(states.length) {
      const state=states.some(s=>s===null)||new Set(states).size>1?null:states[0]
      observations.symptoms[concept.key]=state
      if(state===null)ambiguous.push(concept.key)
    }
  }
  const appetite:Observations['appetite'][]=[]
  for(const c of clauses) {
    if(uncertain.test(c))continue
    if(/(?:not|isn't|is not|won't|has stopped) eating|no appetite|not.{0,8}(?:eat|eating)|(?:khana|khaana|chara|bhook).{0,15}nah[ií]n?|खाना.{0,15}नहीं|खा.{0,15}नहीं|भूख.{0,8}नहीं/iu.test(c))appetite.push('none')
    else if(/eating less|reduced appetite|less appetite|appetite loss|kam.{0,5}(?:kha|bhook)|bhook.{0,6}kam|कम.{0,8}खा|भूख.{0,8}कम/iu.test(c) && !negated.test(c))appetite.push('reduced')
    else if(/eating normally|eating well|normal appetite|achh[ae].{0,5}kha|सामान्य.{0,8}खा/iu.test(c) && !negated.test(c))appetite.push('normal')
    if(!/not unable|not that|ऐसा नहीं/iu.test(c)&&/cannot stand|can't stand|unable to stand|khad[ai].{0,10}nahi|खड़[ाीे].{0,10}नहीं/iu.test(c))observations.activity='recumbent'
    else if(!observations.activity && /less active|reduced activity|sust|सुस्त/iu.test(c) && !negated.test(c))observations.activity='reduced'
  }
  if(new Set(appetite).size===1)observations.appetite=appetite[0]
  else if(appetite.length)ambiguous.push('appetite')
  const duration=value.match(/(?:\s|^)(\d+(?:\.\d+)?|one|two|three|four|five|ek|do|teen|char|paanch|एक|दो|तीन|चार|पांच|पाँच)\s*(days?|hours?|din|ghant[ae]|दिन|घंटे|घंटा)/iu)
  if(duration){const n=numbers[duration[1]]??Number(duration[1]);const hours=n*(/day|din|दिन/iu.test(duration[2])?24:1);if(hours<=2160)observations.duration_hours=hours}
  const temperature=value.match(/(\d{2}(?:\.\d+)?)\s*(?:°?\s*c\b|celsius|सेल्सियस)/iu)
  if(temperature && Number(temperature[1])>=30 && Number(temperature[1])<=45)observations.temperature_c=Number(temperature[1])
  const deaths=value.match(/\b(\d+)\s*(?:deaths?|animals? died)\b/iu)
  if(deaths && Number(deaths[1])<=1000)observations.mortality_count=Number(deaths[1])
  return {observations,ambiguous,mixed,found:Object.keys(observations.symptoms).length>0||Object.keys(observations).length>1}
}

/** A follow-up adds explicit observations. Corrections replace the same field;
 * unknown and unrelated observations never become defaults. */
export function mergeObservations(previous:Parsed|null, next:Parsed):Parsed {
  if(!previous||next.mixed)return next
  const updated=new Set([...Object.keys(next.observations).filter(k=>k!=='symptoms'),...Object.keys(next.observations.symptoms),...next.ambiguous])
  const observations={...previous.observations,...next.observations,symptoms:{...previous.observations.symptoms,...next.observations.symptoms}}
  if(next.ambiguous.includes('appetite'))delete observations.appetite
  return {observations,ambiguous:[...new Set([...previous.ambiguous.filter(k=>!updated.has(k)),...next.ambiguous])],mixed:false,found:true}
}
export function observationItems(o:Observations, language:Language): {key:string;description:string;target:TargetId}[] {
  const items:{key:string;description:string;target:TargetId}[]=[]
  for(const [key,value]of Object.entries(o.symptoms)) {
    const target=`symptom-${key}` as TargetId, entry=catalog.targets[target]
    if(!entry)continue
    const prefix=value===true?'':value===false?(language==='hi'?'नहीं: ':language==='hinglish'?'Nahi: ':'Absent: '):(language==='hi'?'अनिश्चित: ':language==='hinglish'?'Uncertain: ':'Uncertain: ')
    items.push({key,description:prefix+entry.label[language],target})
  }
  if(o.appetite)items.push({key:'appetite',target:'appetite',description:language==='hi'?{none:'भूख: बिल्कुल नहीं खा रहा',reduced:'भूख: कम खा रहा',normal:'भूख: सामान्य'}[o.appetite]:`Appetite: ${{none:'Not eating',reduced:'Eating less',normal:'Eating normally'}[o.appetite]}`})
  if(o.activity)items.push({key:'activity',target:'activity',description:language==='hi'?{recumbent:'गतिविधि: खड़ा नहीं हो पा रहा',reduced:'गतिविधि: कम सक्रिय',normal:'गतिविधि: सामान्य'}[o.activity]:`Activity: ${{recumbent:'Unable to stand',reduced:'Less active',normal:'Normal'}[o.activity]}`})
  if(o.duration_hours!==undefined)items.push({key:'duration_hours',target:'duration',description:`${language==='hi'?'अवधि':'Duration'}: ${o.duration_hours} ${language==='hi'?'घंटे':'hours'}`})
  if(o.temperature_c!==undefined)items.push({key:'temperature_c',target:'temperature',description:`${language==='hi'?'तापमान':'Temperature'}: ${o.temperature_c} °C`})
  if(o.mortality_count!==undefined)items.push({key:'mortality_count',target:'mortality',description:`${language==='hi'?'झुंड में मृत्यु':'Herd deaths'}: ${o.mortality_count}`})
  return items
}
