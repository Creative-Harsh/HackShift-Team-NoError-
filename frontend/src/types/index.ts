export type Role = 'farmer' | 'paravet' | 'vet' | 'lab' | 'admin'
export const roleNames: Record<Role, string> = { farmer: 'Farmer', paravet: 'Field worker', vet: 'Veterinarian', lab: 'Laboratory operator', admin: 'District administrator' }
export interface User { id: string; name: string; email: string; role: Role; district: string }
export interface GeoPoint { type: 'Point'; coordinates: [number, number] }
export interface Vaccination { vaccine: string; date_given: string; next_due_date: string; recorded_by?: string }
export interface Animal {
  id: string; name: string; pashu_id: string; species: string; breed: string; age_months: number; gender: 'female' | 'male';
  owner_id: string; owner_name: string; location: GeoPoint; village: string; district: string;
  vaccination_history: Vaccination[]; disease_history: Record<string, unknown>[]; treatment_history: Record<string, unknown>[];
  lab_history: Record<string, unknown>[]; health_status: string; created_at: string
}
export interface AnimalInput { name: string; pashu_id?: string; species: string; breed: string; age_months: number; gender: 'female' | 'male'; owner_id?: string; location: GeoPoint; village: string; district: string }
export interface ReportInput {
  client_report_id: string; animal_id: string; symptoms: string[]; temperature_c?: number;
  appetite: 'normal' | 'reduced' | 'none'; milk_drop_percent: number; activity: 'normal' | 'reduced' | 'recumbent';
  recent_contact: boolean; vaccination_status: 'up_to_date' | 'overdue' | 'unknown'; mortality_count: number;
  duration_hours: number; location: GeoPoint; reported_at?: string; image_url?: string; voice_note_url?: string
}
export interface Triage {
  suspected_disease: string; probability: number | null; severity: string; triggered_rules: string[];
  missing_information: string[]; recommended_escalation: string; model_version: string; model_source: string;
  disease_code?: string; probability_kind?: string; rule_strength?: number; safe_actions?: string[]
}
export interface Risk { score: number; level: string; factors: { key: string; label: string; points: number; detail: string }[]; version: string }
export interface DiseaseCase {
  version: number; needs_vet_review?: boolean; assigned_vet_name?: string; lab_tests?: LabTest[]; confirmed_disease?: string; professional_review?: { diagnosis: string; recommendations: string; reviewer_name: string; date: string };
  id: string; animal_id: string; animal_name: string; pashu_id: string; species: string; village: string; district: string;
  reporter_id: string; report: ReportInput; location: GeoPoint; reported_at: string; created_at: string; updated_at: string;
  status: string; confirmation_status: string; triage: Triage | null; risk: Risk | null;
  timeline: { status: string; at?: string; timestamp?: string; note?: string; actor_id?: string }[]; assigned_vet_id: string | null
}
export interface AnimalHistory { animal: Animal; cases: DiseaseCase[]; lab_tests: Record<string, unknown>[] }
export interface FarmerOption { id: string; name: string; email: string }
export interface AuthResult { access_token: string; token_type: string; user: User }
export interface Outbreak {
  id: string; disease_code: string; suspected_disease: string; center: GeoPoint; radius_km: number;
  case_ids: string[]; case_count: number; animal_count: number; score: number; level: string; status: string;
  factors: Risk['factors']; start_time: string; end_time: string; district: string; villages: string[];
  risk_distribution: Record<string, number>; latest_reports: DiseaseCase[]; active: boolean
}
export interface OutbreakFilters { days: number; disease: string; species: string; village: string; district: string }
export interface OutbreakMapData {
  cases: DiseaseCase[]; clusters: Outbreak[]; total_cases: number; truncated: boolean;
  config: { radius_km: number; window_hours: number }; generated_at: string
}
export interface DemoStatus { enabled: boolean; completed: number; total: number; run_id: string }
export interface DemoReplay extends DemoStatus { new_case_ids: string[]; clusters: Outbreak[] }
export interface LabTest {
  id: string; case_id: string; case_version: number; animal_name: string; animal_id: string; pashu_id: string;
  district: string; village: string; test_type: string; disease_code: string; status: string; requested_at: string;
  requested_by_name: string; notes: string; result_notes?: string; confirmed_disease?: string; attachment_url?: string
}
export interface Notification { id: string; title: string; message: string; case_id?: string; cluster_id?: string; created_at: string; read_by: string[] }
export interface DistrictDashboard {
  kpis: Record<string, number>; cases_over_time: { name: string; count: number }[];
  disease_distribution: { name: string; count: number }[]; species_distribution: { name: string; count: number }[];
  risk_distribution: { name: string; count: number }[]; critical_cases: DiseaseCase[]; recent_clusters: Outbreak[];
  operational: { mean_report_to_assignment_minutes: number | null; assigned_case_count: number }; generated_at: string
}
