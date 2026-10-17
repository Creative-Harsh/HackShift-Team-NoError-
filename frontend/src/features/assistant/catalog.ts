import data from '../../../../backend/app/assistant/catalog.json' with { type: 'json' }
import type { Role } from '../../types'

export type Language = 'en' | 'hi' | 'hinglish'
export type TargetId = keyof typeof data.targets
export type PageId = 'home' | 'animals' | 'animal_new' | 'animal_detail' | 'report' | 'cases' | 'case_detail' | 'laboratory' | 'outbreaks' | 'unknown'
export type Translation = Record<Language,string>
export const catalog = data
export const targetIds = Object.keys(data.targets) as TargetId[]
export function isTarget(value: unknown): value is TargetId { return typeof value==='string' && Object.hasOwn(data.targets,value) }
export function allowed(id: TargetId, role: Role) { return (data.targets[id].roles as string[]).includes(role) }
export function label(id: TargetId, language: Language) { return data.targets[id].label[language] }
export function text(key: string, language: Language) { return (data.messages as Record<string,Translation>)[key]?.[language] || data.messages.unknown[language] }
export function statusText(status: string, language: Language) { return (data.statuses as Record<string,Translation>)[status]?.[language] }
export function pageId(path: string): PageId {
  if(path==='/')return 'home'
  if(path==='/animals/new' || /^\/animals\/[^/]+\/edit$/.test(path))return 'animal_new'
  if(/^\/animals\/[^/]+$/.test(path))return 'animal_detail'
  if(/^\/cases\/[^/]+$/.test(path))return 'case_detail'
  return ['animals','report','cases','laboratory','outbreaks'].includes(path.slice(1))?path.slice(1) as PageId:'unknown'
}
export function localIntent(message: string, role: Role): {id:string;target:TargetId|null} {
  const match=data.intents.find(i=>new RegExp(i.pattern,'iu').test(message))
  if(!match || !isTarget(match.target))return {id:'unknown',target:null}
  return {id:allowed(match.target,role)?match.id:'denied',target:allowed(match.target,role)?match.target:null}
}
