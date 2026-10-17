import { test, expect } from '@playwright/test'
import { parseObservations, mergeObservations } from '../src/features/assistant/conversation'
import { allowed, catalog, localIntent, pageId, targetIds } from '../src/features/assistant/catalog'

test('English, Hindi and Hinglish retain fever, appetite severity and duration',()=>{
  for(const message of ['My cow has fever and is not eating for two days','मेरी गाय को बुखार है और खाना नहीं खा रही दो दिन से','Meri gaay ko bukhar hai aur khana nahi kha rahi do din se']){
    const result=parseObservations(message)
    expect(result.observations).toMatchObject({symptoms:{fever:true},appetite:'none',duration_hours:48})
    expect(result.observations.temperature_c).toBeUndefined()
    expect(result.ambiguous).toEqual([])
  }
})
test('explicit negatives and uncertain concepts never become positive defaults',()=>{
  expect(parseObservations('no fever or cough').observations.symptoms).toEqual({fever:false,cough:false})
  expect(parseObservations('maybe fever').observations.symptoms.fever).toBeNull()
  expect(parseObservations('fever, no fever').ambiguous).toContain('fever')
  expect(parseObservations('fever not eating').ambiguous).toContain('fever')
  expect(parseObservations('hello').observations).toEqual({symptoms:{}})
  expect(parseObservations('temperature 103 F').observations.temperature_c).toBeUndefined()
})
test('follow-ups accumulate known facts and explicit corrections clear uncertainty',()=>{
  let result=mergeObservations(parseObservations('maybe fever'),parseObservations('not eating for two days'))
  expect(result.ambiguous).toContain('fever')
  result=mergeObservations(result,parseObservations('no fever'))
  expect(result.ambiguous).toEqual([])
  expect(result.observations).toMatchObject({symptoms:{fever:false},appetite:'none',duration_hours:48})
  expect(parseObservations('another cow has fever').mixed).toBe(true)
  expect(parseObservations('my cow and buffalo are sick').mixed).toBe(true)
})
test('roles, routes and fallback references use the same finite catalogue',()=>{
  expect(localIntent('Photo kaha upload karu?','farmer').target).toBe('animal-photo')
  expect(localIntent('sample request','farmer').id).toBe('denied')
  expect(localIntent('मेरी रिपोर्ट कहाँ है?','farmer').target).toBe('nav-cases')
  expect(allowed('admin-confirmation','farmer')).toBe(false)
  expect(pageId('/cases/abc')).toBe('case_detail')
  for(const target of targetIds){const fallback=catalog.targets[target].fallback;if(fallback)expect(targetIds).toContain(fallback)}
})
