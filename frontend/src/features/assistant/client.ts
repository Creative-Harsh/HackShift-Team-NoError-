import { z } from 'zod'
import { api } from '../../services/api'
import type { Animal } from '../../types'
import { cachedAnimals, storedUserId } from '../offline/store'
import { catalog, isTarget } from './catalog'
import type { Language } from './catalog'
import type { Observations } from './conversation'
import type { contextSnapshot } from './registry'

const responseSchema=z.object({intent:z.string().refine(v=>v==='unknown'||catalog.intents.some(i=>i.id===v)),target:z.string().nullable().refine(v=>v===null||isTarget(v)),message_key:z.enum(['unknown','consent','denied','point','statusMissing']),source:z.enum(['local','gemini','fallback']),case_status:z.string().nullable().refine(v=>v===null||Object.hasOwn(catalog.statuses,v))}).strict()
const concernSchema=z.object({message_key:z.enum(['urgent','attention','insufficient']),severity:z.enum(['low','moderate','high','critical']).nullable(),triggered_rules:z.array(z.string()),missing_information:z.array(z.string()),risk_score:z.null(),saved:z.literal(false),source:z.literal('existing-rule-engine'),animal_id:z.string()}).strict()
export type Concern=z.infer<typeof concernSchema>
export const capabilities=()=>api.get<{provider_available:boolean}>('/assistant/capabilities',{timeout:5000}).then(r=>r.data)
export async function assistantAnimals(signal:AbortSignal):Promise<Animal[]> {
  if(!navigator.onLine)return cachedAnimals(storedUserId()||'')
  return (await api.get<Animal[]>('/animals',{signal,timeout:8000})).data
}
// This module exposes exactly two non-saving requests. No generic request helper
// or application mutations are exposed to the companion's guidance/controller.
export async function askAssistant(text:string,language:Language,external_consent:boolean,context:ReturnType<typeof contextSnapshot>|null,signal:AbortSignal){
  const {data}=await api.post('/assistant/message',{text,language,external_consent,context},{signal,timeout:12000})
  return responseSchema.parse(data)
}
export async function checkConcern(animal_id:string,observations:Observations,signal:AbortSignal){
  const {data}=await api.post('/assistant/concern',{animal_id,observations,verified:true},{signal,timeout:12000})
  return concernSchema.parse(data)
}
