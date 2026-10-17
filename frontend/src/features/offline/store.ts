import type { Animal, ReportInput } from '../../types'
export const USER_KEY = 'pashuraksha.user'
export interface Attachment { id: string; kind: 'image' | 'voice_note'; file: Blob; name: string; url?: string }
export interface QueuedReport { key: string; userId: string; payload: ReportInput; attachments: Attachment[]; state: 'queued' | 'syncing' | 'blocked' | 'synced'; createdAt: string; attempts: number; nextAttempt: number; error?: string; caseId?: string }
let connection: Promise<IDBDatabase> | undefined
function database() {
  return connection ||= new Promise<IDBDatabase>((resolve, reject) => {
    const request = indexedDB.open('pashuraksha-offline', 1)
    request.onupgradeneeded = () => { request.result.createObjectStore('animals', {keyPath:'userId'}); request.result.createObjectStore('reports', {keyPath:'key'}) }
    request.onsuccess = () => resolve(request.result); request.onerror = () => { connection = undefined; reject(request.error) }
  })
}
async function write(store: string, value: unknown) {
  const db = await database()
  await new Promise<void>((resolve, reject) => { const tx=db.transaction(store,'readwrite');tx.objectStore(store).put(value);tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error || new Error('Local storage transaction failed')) })
}
async function read<T>(store: string, key?: string): Promise<T> {
  const db=await database()
  return new Promise<T>((resolve,reject)=>{const tx=db.transaction(store,'readonly');const req=key?tx.objectStore(store).get(key):tx.objectStore(store).getAll();req.onsuccess=()=>resolve(req.result as T);req.onerror=()=>reject(req.error)})
}
export async function cacheAnimals(userId: string, animals: Animal[]) { await write('animals',{userId,animals,cachedAt:new Date().toISOString()}) }
export async function cachedAnimals(userId: string) { return (await read<{animals:Animal[]}|undefined>('animals',userId))?.animals || [] }
export async function queueRows(userId: string) { return (await read<QueuedReport[]>('reports')).filter(r=>r.userId===userId).sort((a,b)=>b.createdAt.localeCompare(a.createdAt)) }
export async function saveRow(row: QueuedReport) { await write('reports',row);window.dispatchEvent(new Event('queue:changed')) }
export async function enqueue(userId: string, payload: ReportInput, attachments: Attachment[]) {
  const key=userId+':'+payload.client_report_id
  const row:QueuedReport={key,userId,payload,attachments,state:'queued',createdAt:new Date().toISOString(),attempts:0,nextAttempt:0}
  // A single transaction prevents another tab from replacing an in-flight row.
  const db=await database()
  const result=await new Promise<QueuedReport>((resolve,reject)=>{
    const tx=db.transaction('reports','readwrite'), store=tx.objectStore('reports'), request=store.get(key)
    let saved=row
    request.onsuccess=()=>{if(request.result)saved=request.result;else store.add(row)}
    tx.oncomplete=()=>resolve(saved);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error || new Error('Local report could not be saved.'))
  })
  window.dispatchEvent(new Event('queue:changed'));return result
}
export function storedUserId(): string | null { try{return JSON.parse(sessionStorage.getItem(USER_KEY)||'null')?.id||null}catch{return null} }
