import { allowed, catalog, isTarget, label, pageId, targetIds, text } from './catalog'
import type { Language, TargetId } from './catalog'
import type { Role } from '../../types'

export interface GuidePosition { id:TargetId; x:number; y:number; box:{left:number;top:number;width:number;height:number}|null; message:string }
const mounted=(element:HTMLElement)=>element.isConnected && getComputedStyle(element).display!=='none' && getComputedStyle(element).visibility!=='hidden' && element.getClientRects().length>0
function elements(id:TargetId) { return Array.from(document.querySelectorAll<HTMLElement>(`[data-guide="${id}"]`)).filter(mounted) }
function visible(element:HTMLElement) {const r=element.getBoundingClientRect();return r.width>0&&r.height>0&&r.right>0&&r.left<innerWidth&&r.bottom>(element.closest('.topbar')?0:70)&&r.top<innerHeight}

/** Read-only registry capability. There is deliberately no click, focus, scroll or value API. */
export function contextSnapshot(path:string, role:Role) {
  const page=pageId(path)
  const targets=targetIds.filter(id=>allowed(id,role)&&((catalog.targets[id].pages as string[]).includes('*')||(catalog.targets[id].pages as string[]).includes(page))&&elements(id).some(visible))
  return {page,targets,...(page==='case_detail'?{case_id:path.split('/')[2]}:{})}
}
export function locateGuide(value:unknown, role:Role, language:Language, consent:boolean, path:string):GuidePosition|null {
  if(!consent || !isTarget(value) || !allowed(value,role))return null
  let id:TargetId=value
  const visited=new Set<TargetId>()
  while(!visited.has(id)){
    visited.add(id)
    const entry=catalog.targets[id], candidates=((entry.pages as string[]).includes('*')||(entry.pages as string[]).includes(pageId(path)))?elements(id):[]
    const element=candidates.find(visible)
    if(element){
      const r=element.getBoundingClientRect(), width=104,height=172,gap=12
      const candidates=[{x:r.right+gap,y:Math.max(72,r.top)},{x:r.left-width-gap,y:Math.max(72,r.top)},{x:r.left,y:Math.max(72,r.bottom+gap)},{x:r.left,y:r.top-height-gap}]
      const position=candidates.find(p=>p.x>=8&&p.x+width<=innerWidth-8&&p.y>=72&&p.y+height<=innerHeight-8)
      const fallback={x:Math.max(8,innerWidth-width-12),y:Math.max(76,innerHeight-height-12)}
      return {id,...(position||fallback),box:{left:Math.max(0,r.left),top:Math.max(0,r.top),width:Math.min(r.right,innerWidth)-Math.max(0,r.left),height:Math.min(r.bottom,innerHeight)-Math.max(0,r.top)},message:label(id,language)+'. '+text('point',language)}
    }
    // A translated mobile sidebar is mounted but outside the viewport. Point at
    // its actual menu opener, rather than inventing a vertical scroll direction.
    if(candidates.length && id.startsWith('nav-') && elements('menu').some(visible)){id='menu';continue}
    if(candidates.length){
      const r=candidates[0].getBoundingClientRect()
      return {id,x:Math.max(18,innerWidth-116),y:r.top>=innerHeight?Math.max(76,innerHeight-184):76,box:null,message:label(id,language)+'. '+text(r.top>=innerHeight?'down':'up',language)}
    }
    const fallback=entry.fallback
    if(!isTarget(fallback)||!allowed(fallback,role))return null
    id=fallback
  }
  return null
}
