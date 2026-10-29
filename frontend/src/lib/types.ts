export type Outcome = 'eligible' | 'eligible_pending_verification' | 'potential_match' | 'not_eligible';
export type CriterionStatus = 'satisfied' | 'not_satisfied' | 'unknown' | 'not_applicable';
export type AvailabilityState = 'open' | 'closed' | 'upcoming' | 'unknown';

export interface Availability {
  state: AvailabilityState;
  days_left: number | null;
  deadline_approaching: boolean;
}

export interface Evidence {
  source_url: string | null;
  source_key: string;
  snippet: string | null;
  location: string | null;
  method: string;
  verification_status: string;
  classification: string;
  retrieved_at: string | null;
}

export interface Criterion {
  key: string;
  label: string;
  status: CriterionStatus;
  rule: string;
  student_value: string | number | null;
  explanation: string;
  unknown_reason: 'student_missing' | 'needs_confirmation' | 'scholarship_unresolved' | null;
  resolve: { profile_field?: string; question?: { key: string; text: string } } | null;
  evidence: Evidence | null;
}

export interface RelevanceFactor {
  value: number;
  detail: string;
  weight: number;
  contribution: number;
}

export interface Relevance {
  score: number;
  factors: Record<string, RelevanceFactor>;
  note: string;
}

export interface ScholarshipSummary {
  id: string;
  external_id: string | null;
  name: string;
  provider: string | null;
  provider_type: string | null;
  scholarship_type: string | null;
  amount_text: string | null;
  amount_max_inr: number | null;
  amount_frequency: string | null;
  open_date: string | null;
  deadline: string | null;
  renewal_type: string;
  education_levels: string[];
  eligible_states: string[];
  application_url: string | null;
  official_source_url: string | null;
  verification_status: string;
  last_checked_at: string | null;
  last_verified_at: string | null;
  version: number;
  origin: string;
}

export interface RecommendationResult {
  scholarship_id: string;
  outcome: Outcome;
  outcome_label: string;
  headline: string;
  availability: Availability;
  verification_status: string;
  verification_label: string;
  requires_verification: boolean;
  criteria: Criterion[];
  deadline_evidence: Evidence | null;
  relevance: Relevance | null;
  scholarship: ScholarshipSummary;
  answers?: Record<string, string>;
}

export interface UpdateItem {
  scholarship_id: string;
  name: string;
  kind: 'new_opportunity' | 'changed';
  now?: { outcome: Outcome; availability: AvailabilityState; deadline: string | null };
  changes?: Record<string, { from: unknown; to: unknown }>;
}

export interface Recommendations {
  computed_at: string;
  counts: Partial<Record<Outcome, number>>;
  missing_profile_fields: { field: string; label: string; affects: number }[];
  results: RecommendationResult[];
  updates: { since: string | null; items: UpdateItem[] };
}

export interface Scholarship extends Record<string, unknown> {
  id: string;
  external_id: string | null;
  name: string;
  provider: string | null;
  provider_type: string | null;
  description: string | null;
  eligibility_summary: string | null;
  selection_process: string | null;
  amount_text: string | null;
  amount_max_inr: number | null;
  amount_frequency: string | null;
  open_date: string | null;
  deadline: string | null;
  renewal_type: string;
  status_reported: string | null;
  application_url: string | null;
  official_source_url: string | null;
  application_method: string | null;
  required_documents: string[];
  education_levels: string[];
  eligible_states: string[];
  courses_text: string | null;
  fields_text: string | null;
  year_of_study_text: string | null;
  income_rule: string;
  income_limit: number | null;
  income_note: string | null;
  academic_rule: string;
  academic_note: string | null;
  min_percentage: number | null;
  min_cgpa: number | null;
  special_note: string | null;
  exclusions: string | null;
  origin: string;
  version: number;
  verification_status: string;
  verification_label: string;
  verification_flags: string[];
  first_discovered_at: string;
  last_checked_at: string | null;
  last_verified_at: string | null;
  updated_at: string | null;
  availability: Availability;
}

export interface EvidenceRow extends Evidence {
  id: string;
  field: string;
  value: unknown;
  record_version: number;
  is_current: boolean;
  document_id: string | null;
}

export interface ChangeEvent {
  id: string;
  scholarship_id: string | null;
  scholarship_name: string | null;
  source_id: string | null;
  job_id: string | null;
  document_id: string | null;
  field: string;
  change_kind: string;
  old_value: unknown;
  new_value: unknown;
  materiality: 'material' | 'minor' | 'cosmetic';
  detected_at: string;
  source_url: string | null;
  evidence_snippet: string | null;
  method: string;
  review_status: string;
  reviewed_at: string | null;
  review_note: string | null;
  applied_version: number | null;
}

export interface LinkedSource {
  id: string;
  key: string;
  name: string;
  organization: string | null;
  classification: string;
  health_status: string;
  last_success_at: string | null;
  last_attempt_at: string | null;
  last_error: string | null;
  target_urls: string[];
  is_fixture: boolean;
  enabled: boolean;
  paused_reason: string | null;
  currently_listed: boolean | null;
  last_seen_at: string | null;
  match_method: string;
}

export interface ScholarshipDetail {
  scholarship: Scholarship;
  trust: {
    primary: string;
    label: string;
    flags: string[];
    flag_labels: Record<string, string>;
    details: { conflicts?: { field: string; values: { source: string; value: unknown }[] }[]; hours_since_check?: number; pending_changes?: number; unavailable_sources?: string[] };
    max_age_hours: number;
  };
  evidence: { current: EvidenceRow[]; history: EvidenceRow[] };
  sources: LinkedSource[];
  changes: ChangeEvent[];
  versions: { version: number; reason: string; created_at: string; deadline: string | null; open_date: string | null }[];
}

export interface VocabItem {
  code: string;
  label: string;
  group?: string;
}

export interface Vocabulary {
  education_levels: VocabItem[];
  disciplines: VocabItem[];
  categories: VocabItem[];
  genders: VocabItem[];
  states: string[];
  special_circumstances: VocabItem[];
  trust_statuses: Record<string, string>;
  freshness_policy: Record<string, number>;
}

export interface Profile {
  id?: string;
  display_name: string | null;
  education_level: string | null;
  current_class: number | null;
  year_of_study: number | null;
  course_name: string | null;
  discipline: string | null;
  qualifying_exam_percentage: number | null;
  cgpa: number | null;
  cgpa_scale: number;
  annual_family_income: number | null;
  state: string | null;
  gender: string | null;
  category: string | null;
  has_disability: boolean | null;
  disability_percent: number | null;
  is_indian_citizen: boolean | null;
  special_circumstances: string[];
  special_circumstances_none: boolean;
  updated_at?: string;
}

export interface SessionUser {
  id: string;
  email: string;
  role: 'student' | 'admin';
  has_profile: boolean;
}

export interface Source {
  id: string;
  key: string;
  name: string;
  organization: string | null;
  classification: string;
  base_url: string;
  target_urls: string[];
  allowed_url_patterns: string[];
  connector: string;
  connector_config: Record<string, unknown>;
  parser_version: string;
  crawl_frequency_minutes: number;
  enabled: boolean;
  priority: number;
  trust_policy: string | null;
  access_notes: string | null;
  linked_scholarship_id: string | null;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_change_at: string | null;
  last_http_status: number | null;
  last_error: string | null;
  health_status: string;
  consecutive_failures: number;
  next_check_at: string | null;
  paused_reason: string | null;
  is_fixture: boolean;
}

export interface Job {
  id: string;
  source_id: string;
  source_key: string | null;
  source_name: string | null;
  trigger: string;
  status: string;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  pages_fetched: number;
  pages_unchanged: number;
  records_seen: number;
  records_matched: number;
  candidates_created: number;
  changes_detected: number;
  error_type: string | null;
  error_message: string | null;
  retry_of: string | null;
  duration_ms: number | null;
  log?: { t: string; msg: string }[];
  documents?: { id: string; url: string; http_status: number | null; content_sha256: string | null; bytes: number | null; quality: string | null; not_modified: boolean; fetched_at: string }[];
}

export interface Candidate {
  id: string;
  kind: 'new' | 'update';
  status: string;
  source_id: string | null;
  job_id: string | null;
  document_id: string | null;
  external_key: string | null;
  title: string;
  payload: Record<string, unknown>;
  evidence: Record<string, { snippet?: string; location?: string | null; document?: string }>;
  validation: { errors?: string[]; warnings?: string[]; unsupported?: { field: string; value: unknown; quote: string | null; reason: string }[]; missing_for_publication?: string[] };
  possible_matches: { scholarship_id: string; name: string; score: number; decision: string; conflict: string | null; url_match: boolean }[];
  matched_scholarship_id: string | null;
  extraction_method: string;
  extraction_status: string;
  extraction_error: string | null;
  llm_provider: string | null;
  llm_model: string | null;
  created_at: string;
  updated_at: string;
  reviewed_at: string | null;
  review_note: string | null;
  target?: Scholarship | null;
  document?: { id: string; url: string; fetched_at: string; quality: string | null } | null;
}
