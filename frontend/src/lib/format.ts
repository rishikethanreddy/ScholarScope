const DATE = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
const DATETIME = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
const INR = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 });

/** Parse an ISO date (YYYY-MM-DD) as a calendar date, not a UTC instant. */
function parseDay(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return new Date(y, m - 1, d);
}

export const fmtDate = (iso: string | null | undefined) => (iso ? DATE.format(iso.length === 10 ? parseDay(iso) : new Date(iso)) : '—');
export const fmtDateTime = (iso: string | null | undefined) => (iso ? DATETIME.format(new Date(iso)) : '—');
export const fmtINR = (n: number | null | undefined) => (n == null ? '—' : INR.format(n));

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return 'never';
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 0) return 'in the future';
  if (s < 60) return 'just now';
  const m = Math.round(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

export function fmtValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.length ? v.map((x) => (typeof x === 'object' ? (x as { text?: string }).text ?? JSON.stringify(x) : String(x))).join(', ') : '—';
  if (typeof v === 'number') return v >= 10000 ? fmtINR(v) : String(v);
  if (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(v)) return fmtDate(v);
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

export const FIELD_LABELS: Record<string, string> = {
  deadline: 'Deadline',
  open_date: 'Opening date',
  renewal_type: 'Fresh / renewal',
  official_source_url: 'Official source',
  application_url: 'Application link',
  guideline_url: 'Guideline document',
  listing_presence: 'Listed on source',
  page_content: 'Page content',
  status_reported: 'Application status (as stated)',
  income_limit: 'Income ceiling',
  income_rule: 'Income rule',
  academic_rule: 'Academic rule',
  min_percentage: 'Minimum %',
  min_cgpa: 'Minimum CGPA',
  education_levels: 'Education levels',
  disciplines: 'Disciplines',
  genders: 'Gender',
  categories: 'Categories',
  disability_rule: 'Disability rule',
  eligible_states: 'States',
  conditions: 'Special conditions',
  amount_text: 'Award amount',
  required_documents: 'Required documents',
};

export const fieldLabel = (f: string) => FIELD_LABELS[f] ?? f.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

export const METHOD_LABELS: Record<string, string> = {
  dataset_import: 'Curated dataset import',
  nsp_listing_parser: 'NSP listing parser (deterministic)',
  html_rules: 'Page text rules (deterministic)',
  llm: 'AI extraction (quote-verified)',
  manual: 'Entered by admin',
  'page-monitor/1.0': 'Page monitor',
};

export const methodLabel = (m: string) => METHOD_LABELS[m] ?? m;
