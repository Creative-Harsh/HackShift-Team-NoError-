import { cachedAnimals, cacheAnimals, storedUserId } from '../features/offline/store'
import axios from 'axios'
import type { Animal, AnimalHistory, AnimalInput, AuthResult, DemoReplay, DemoStatus, DiseaseCase, FarmerOption, OutbreakFilters, OutbreakMapData, ReportInput, User, Vaccination } from '../types'

export const TOKEN_KEY = 'pashuraksha.access_token'
export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL || '/api', timeout: 45000 })
api.interceptors.request.use(config => {
  const token = sessionStorage.getItem(TOKEN_KEY)
  if (token && !config.headers.Authorization) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(response => response, error => {
  if (error.response?.status === 401 && !String(error.config?.url).includes('/auth/login') && error.config?.headers?.Authorization === `Bearer ${sessionStorage.getItem(TOKEN_KEY)}`) {
    sessionStorage.removeItem(TOKEN_KEY)
    window.dispatchEvent(new Event('auth:expired'))
  }
  return Promise.reject(error)
})
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map(item => `${item.loc?.slice(1).join(' ')}: ${item.msg}`).join('. ')
    if (!error.response) return 'Unable to reach the server. Check your connection and try again.'
  }
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}
async function animalRecords(): Promise<Animal[]> {
  const userId=storedUserId()
  if(!userId)throw new Error('Sign in to access animal records.')
  try {
    const {data}=await api.get<Animal[]>('/animals')
    if(storedUserId()===userId)await cacheAnimals(userId,data).catch(()=>console.warn('Offline animal cache could not be updated.'))
    return data
  } catch(error) {
    if(axios.isAxiosError(error) && !error.response) {
      const cached=await cachedAnimals(userId)
      if(cached.length)return cached
    }
    throw error
  }
}
async function cachedRecord(path: string, matches:(a:Animal)=>boolean) {
  try{return (await api.get<Animal>(path)).data}
  catch(error) {
    if(axios.isAxiosError(error) && !error.response) {
      const found=(await cachedAnimals(storedUserId()||'')).find(matches)
      if(found)return found
    }
    throw error
  }
}
async function animalHistory(id: string): Promise<AnimalHistory & { offline?: boolean }> {
  try { return (await api.get<AnimalHistory>(`/animals/${id}/history`)).data }
  catch(error) {
    if(axios.isAxiosError(error) && !error.response) {
      const animal=(await cachedAnimals(storedUserId() || '')).find(a=>a.id===id)
      if(animal)return { animal, cases: [], lab_tests: [], offline: true }
    }
    throw error
  }
}
export const endpoints = {
  login: (input: { email: string; password: string }) => api.post<AuthResult>('/auth/login', input).then(r => r.data),
  register: (input: { name: string; email: string; password: string; district: string }) => api.post<AuthResult>('/auth/register', input).then(r => r.data),
  me: () => api.get<User>('/auth/me').then(r => r.data),
  logout: () => api.post('/auth/logout'),
  animals: animalRecords,
  animal: (id: string) => cachedRecord(`/animals/${id}`, a=>a.id===id),
  lookup: (pashuId: string) => cachedRecord(`/animals/pashu-id/${pashuId}`, a=>a.pashu_id===pashuId),
  history: animalHistory,
  saveAnimal: (input: AnimalInput, id?: string) => (id ? api.put<Animal>(`/animals/${id}`, input) : api.post<Animal>('/animals', input)).then(r => r.data),
  vaccinate: (id: string, input: Vaccination) => api.post<Animal>(`/animals/${id}/vaccinations`, input).then(r => r.data),
  farmers: () => api.get<FarmerOption[]>('/users/farmers').then(r => r.data),
  report: (input: ReportInput) => api.post<DiseaseCase>('/reports', input).then(r => r.data),
  cases: () => api.get<DiseaseCase[]>('/cases').then(r => r.data),
  case: (id: string) => api.get<DiseaseCase>(`/cases/${id}`).then(r => r.data),
  outbreakMap: (filters: OutbreakFilters, signal?: AbortSignal) => api.get<OutbreakMapData>('/outbreaks/map', { params: Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '')), signal }).then(r => r.data),
  demoStatus: (signal?: AbortSignal) => api.get<DemoStatus>('/demo/status', { signal }).then(r => r.data),
  demoReplay: () => api.post<DemoReplay>('/demo/replay', { steps: 1 }).then(r => r.data),
}
