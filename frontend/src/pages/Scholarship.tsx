import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowLeft, Bookmark, BookmarkCheck, CalendarClock, ExternalLink, FileText, Info, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fieldLabel, fmtDate, fmtDateTime, fmtINR, fmtValue, methodLabel, timeAgo } from '../lib/format';
import type { RecommendationResult, ScholarshipDetail } from '../lib/types';
import { Container } from '../components/Layout';
import { Badge, Button, ButtonLink, Card, CardHeader, ErrorState, ExternalA, LoadingBlock, Notice, Tabs } from '../components/ui';
import { AvailabilityBadge, HealthBadge, OutcomeBadge, SourceClassBadge, TRUST_HELP, TrustBadge } from '../components/status';
import { ChangeTimeline, ConflictNotice, CriteriaList, EvidenceCard, RelevanceBreakdown } from '../components/explain';

type Tab = 'eligibility' | 'details' | 'verify' | 'history';

export default function ScholarshipPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('eligibility');
  const detailQ = useQuery({ queryKey: ['scholarship', id], queryFn: () => api.scholarship(id) });
  const personal = user?.role === 'student' && user.has_profile;
  const recQ = useQuery({ queryKey: ['recommendation', id], queryFn: () => api.recommendation(id), enabled: !!personal });

  if (detailQ.isLoading) return <Container><LoadingBlock rows={4} /></Container>;
  if (detailQ.error || !detailQ.data) return <Container><ErrorState error={detailQ.error} title="Could not load this scholarship" /></Container>;
  const d = detailQ.data;
  const s = d.scholarship;
  const material = d.changes.filter((c) => c.materiality === 'material');

  return (
    <Container className="max-w-6xl">
      <Link to="/discover" className="mb-4 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900"><ArrowLeft className="h-4 w-4" />All scholarships</Link>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 max-w-3xl">
          <div className="text-xs font-semibold uppercase tracking-wider text-brand-700">{s.provider}</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink-900 sm:text-3xl">{s.name}</h1>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {recQ.data && <OutcomeBadge outcome={recQ.data.outcome} />}
            <AvailabilityBadge a={s.availability} deadline={s.deadline} />
            <TrustBadge status={d.trust.primary} />
            {s.renewal_type === 'renewal' && <Badge tone="violet">Renewal applications only</Badge>}
            {s.origin === 'crawler' && <Badge tone="violet">Discovered by monitor</Badge>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {personal && <SaveButton scholarshipId={s.id} />}
          {s.application_url && (
            <a href={/^https?:\/\//.test(s.application_url) ? s.application_url : undefined} target="_blank" rel="noopener noreferrer"
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white hover:bg-brand-700">
              Apply on official site<ExternalLink className="h-4 w-4" />
            </a>
          )}
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <KeyFact label="Award" value={s.amount_text ?? 'Not stated'} sub={s.amount_frequency ?? undefined} />
        <KeyFact label="Deadline" value={fmtDate(s.deadline)} sub={s.open_date ? `Opened ${fmtDate(s.open_date)}` : undefined} />
        <KeyFact label="Last checked" value={s.last_checked_at ? timeAgo(s.last_checked_at) : 'Never'} sub={s.last_checked_at ? fmtDateTime(s.last_checked_at) : 'Dataset only'} />
        <KeyFact label="Last verified" value={s.last_verified_at ? timeAgo(s.last_verified_at) : 'Never'} sub="Deadline re-observed on an official source" />
      </div>

      <Tabs<Tab> label="Scholarship sections" value={tab} onChange={setTab} tabs={[
        { id: 'eligibility', label: 'Why this match' },
        { id: 'details', label: 'Details & documents' },
        { id: 'verify', label: 'Verify', count: d.trust.flags.filter((f) => !f.startsWith('official')).length || undefined },
        { id: 'history', label: 'History', count: material.length || undefined },
      ]} />
      <div className="mt-6">
        {tab === 'eligibility' && <EligibilityTab personal={!!personal} signedIn={!!user} rec={recQ.data} loading={recQ.isLoading} error={recQ.error} d={d} />}
        {tab === 'details' && <DetailsTab d={d} />}
        {tab === 'verify' && <VerifyTab d={d} />}
        {tab === 'history' && <HistoryTab d={d} />}
      </div>
    </Container>
  );
}

function KeyFact({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-3.5">
      <div className="text-xs text-ink-500">{label}</div>
      <div className="mt-0.5 truncate font-semibold text-ink-900" title={value}>{value}</div>
      {sub && <div className="truncate text-[11px] text-ink-500" title={sub}>{sub}</div>}
    </Card>
  );
}

function SaveButton({ scholarshipId }: { scholarshipId: string }) {
  const qc = useQueryClient();
  const savedQ = useQuery({ queryKey: ['saved'], queryFn: api.saved });
  const existing = savedQ.data?.find((x) => x.scholarship.id === scholarshipId);
  const m = useMutation({
    mutationFn: () => (existing ? api.unsave(existing.id) : api.save(scholarshipId)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['saved'] }),
  });
  return (
    <Button variant="secondary" loading={m.isPending} onClick={() => m.mutate()} aria-pressed={!!existing}>
      {existing ? <BookmarkCheck className="h-4 w-4 text-brand-600" /> : <Bookmark className="h-4 w-4" />}{existing ? 'Saved' : 'Save'}
    </Button>
  );
}

function EligibilityTab({ personal, signedIn, rec, loading, error, d }: { personal: boolean; signedIn: boolean; rec: RecommendationResult | undefined; loading: boolean; error: unknown; d: ScholarshipDetail }) {
  if (!personal) {
    return (
      <Notice tone="blue" icon={<Info className="h-4 w-4" />}>
        {signedIn ? 'Complete your profile' : 'Sign in and create a profile'} to see, rule by rule, whether you meet this scholarship's recorded criteria.{' '}
        <Link to={signedIn ? '/profile' : '/register'} className="font-medium underline">{signedIn ? 'Go to profile' : 'Create an account'}</Link>
        <div className="mt-3 text-ink-700"><RulesSummary d={d} /></div>
      </Notice>
    );
  }
  if (loading) return <LoadingBlock rows={3} />;
  if (error || !rec) return <ErrorState error={error} />;
  const r = rec;
  const unknownCount = r.criteria.filter((c) => c.status === 'unknown').length;
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <Card>
        <CardHeader title={r.headline} subtitle={unknownCount ? `${unknownCount} criteria unresolved. Each shows what would resolve it.` : 'Every recorded criterion was evaluated.'} />
        <div className="px-5"><CriteriaList result={r} /></div>
        <p className="border-t border-ink-100 px-5 py-3 text-xs text-ink-500">
          This compares your profile with the scholarship's recorded rules. It is not an official decision and not a guarantee of funding. Always confirm on the official source.
        </p>
      </Card>
      <div className="space-y-4">
        {r.relevance && <Card className="p-5"><RelevanceBreakdown r={r.relevance} /></Card>}
        {r.availability.state === 'closed' && <Notice tone="amber" icon={<CalendarClock className="h-4 w-4" />}>Applications closed on {fmtDate(r.scholarship.deadline)}. Watch the History tab: deadlines are sometimes extended.</Notice>}
        {r.requires_verification && <Notice tone="neutral" icon={<ShieldCheck className="h-4 w-4" />}>Status: {r.verification_label}. {TRUST_HELP[r.verification_status]}</Notice>}
      </div>
    </div>
  );
}

function RulesSummary({ d }: { d: ScholarshipDetail }) {
  const s = d.scholarship;
  const rows: [string, string][] = [
    ['Education', s.courses_text ?? '—'],
    ['Disciplines', s.fields_text ?? '—'],
    ['Academic', s.academic_rule === 'percentage' ? `Minimum ${s.min_percentage}%` : s.academic_rule === 'cgpa' ? `Minimum CGPA ${s.min_cgpa}` : s.academic_note ?? (s.academic_rule === 'none' ? 'No fixed minimum' : 'Not recorded')],
    ['Income', s.income_rule === 'limit' ? `≤ ${fmtINR(s.income_limit)} per year` : s.income_rule === 'none' ? 'No ceiling stated' : s.income_note ?? 'Not recorded'],
    ['States', s.eligible_states.length ? s.eligible_states.join(', ') : 'All India'],
    ['Other conditions', s.special_note ?? '—'],
  ];
  return (
    <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-[9rem_1fr]">
      {rows.map(([k, v]) => <div key={k} className="contents"><dt className="text-xs font-medium text-ink-500">{k}</dt><dd className="text-sm text-ink-800">{v}</dd></div>)}
    </dl>
  );
}

function DocChecklist({ id, docs }: { id: string; docs: string[] }) {
  const key = `scholarscope.docs.${id}`;
  const [checked, setChecked] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(key) ?? '[]'); } catch { return []; }
  });
  const toggle = (doc: string) => {
    const next = checked.includes(doc) ? checked.filter((x) => x !== doc) : [...checked, doc];
    setChecked(next);
    try { localStorage.setItem(key, JSON.stringify(next)); } catch { /* per-device convenience only */ }
  };
  if (!docs.length) return <p className="text-sm text-ink-500">The source does not list required documents.</p>;
  return (
    <>
      <ul className="space-y-1.5">
        {docs.map((doc) => (
          <li key={doc}>
            <label className="flex items-start gap-2 text-sm text-ink-800">
              <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand-600" checked={checked.includes(doc)} onChange={() => toggle(doc)} />{doc}
            </label>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-xs text-ink-500">{checked.length}/{docs.length} ready · saved on this device only. Never upload documents here.</p>
    </>
  );
}

function DetailsTab({ d }: { d: ScholarshipDetail }) {
  const s = d.scholarship;
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="space-y-6">
        <Card className="p-5">
          <h2 className="font-semibold text-ink-900">Overview</h2>
          <p className="mt-2 whitespace-pre-line text-sm text-ink-700">{s.description ?? 'No description recorded.'}</p>
          {s.eligibility_summary && <p className="mt-3 text-sm text-ink-700"><span className="font-medium">Eligibility summary:</span> {s.eligibility_summary}</p>}
          {s.selection_process && <p className="mt-2 text-sm text-ink-700"><span className="font-medium">Selection:</span> {s.selection_process}</p>}
          {s.exclusions && <p className="mt-2 text-sm text-ink-700"><span className="font-medium">Restrictions:</span> {s.exclusions}</p>}
        </Card>
        <Card className="p-5">
          <h2 className="mb-3 font-semibold text-ink-900">Recorded eligibility rules</h2>
          <RulesSummary d={d} />
        </Card>
      </div>
      <div className="space-y-6">
        <Card className="p-5">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-ink-900"><FileText className="h-4 w-4 text-ink-400" />Documents checklist</h2>
          <DocChecklist key={s.id} id={s.id} docs={s.required_documents} />
        </Card>
        <Card className="p-5 text-sm">
          <h2 className="mb-2 font-semibold text-ink-900">How to apply</h2>
          <p className="text-ink-700">{s.application_method ?? 'See official source.'}</p>
          <div className="mt-3 space-y-1">
            <div><ExternalA href={s.application_url}>Application portal</ExternalA></div>
            <div><ExternalA href={s.official_source_url}>Official guideline / source</ExternalA></div>
          </div>
        </Card>
      </div>
    </div>
  );
}

const KEY_FIELDS = ['deadline', 'open_date', 'renewal_type', 'status_reported', 'income_limit', 'income_rule', 'academic_rule', 'min_percentage', 'education_levels', 'eligible_states', 'conditions', 'amount_text', 'official_source_url', 'guideline_url'];

function VerifyTab({ d }: { d: ScholarshipDetail }) {
  const s = d.scholarship;
  const current = d.evidence.current;
  const byField = useMemo(() => {
    const m = new Map<string, typeof current>();
    for (const e of current) m.set(e.field, [...(m.get(e.field) ?? []), e]);
    return m;
  }, [current]);
  const fields = KEY_FIELDS.filter((f) => byField.has(f));
  return (
    <div className="space-y-6">
      <ConflictNotice conflicts={d.trust.details.conflicts} />
      <Card>
        <CardHeader icon={<ShieldCheck className="h-5 w-5" />} title="Verification status" subtitle={`Freshness policy for this record: a check older than ${d.trust.max_age_hours} hours is stale.`} />
        <ul className="divide-y divide-ink-100">
          {d.trust.flags.map((f) => (
            <li key={f} className="flex flex-wrap items-start gap-3 px-5 py-3">
              <TrustBadge status={f} />
              <span className="flex-1 text-sm text-ink-600">{TRUST_HELP[f]}</span>
            </li>
          ))}
        </ul>
        <div className="grid gap-4 border-t border-ink-100 px-5 py-4 text-sm sm:grid-cols-2">
          <div><div className="text-xs text-ink-500">Last checked (any successful source check)</div><div className="font-medium">{fmtDateTime(s.last_checked_at)}</div></div>
          <div><div className="text-xs text-ink-500">Last verified (deadline re-observed officially)</div><div className="font-medium">{fmtDateTime(s.last_verified_at)}</div></div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Sources monitoring this record" subtitle="A successful HTTP check does not mean every field was verified." />
        {d.sources.length === 0 ? (
          <p className="px-5 py-4 text-sm text-ink-500">No monitored source is linked to this record yet. Its values come from the curated dataset only.</p>
        ) : (
          <ul className="divide-y divide-ink-100">
            {d.sources.map((src) => (
              <li key={src.id} className="px-5 py-3.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-ink-900">{src.name}</span>
                  <SourceClassBadge c={src.classification} fixture={src.is_fixture} />
                  <HealthBadge h={src.enabled ? src.health_status : 'disabled'} />
                  {src.currently_listed === false && <Badge tone="amber" icon={<AlertTriangle className="h-3 w-3" />}>No longer listed</Badge>}
                </div>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-ink-500">
                  <span>Last success: {src.last_success_at ? fmtDateTime(src.last_success_at) : 'never'}</span>
                  <span>Last attempt: {src.last_attempt_at ? fmtDateTime(src.last_attempt_at) : 'never'}</span>
                  <span>Matched by: {src.match_method.replace('_', ' ')}</span>
                  {src.target_urls[0] && <ExternalA href={src.target_urls[0]}>open source</ExternalA>}
                </div>
                {(src.paused_reason || (src.last_error && src.health_status !== 'healthy')) && <p className="mt-1 text-xs text-rose-700">{src.paused_reason ?? src.last_error}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <CardHeader title="Field-level evidence" subtitle="The current observation of each key field from each source, highest-precedence first." />
        <div className="divide-y divide-ink-100">
          {fields.map((f) => (
            <div key={f} className="grid gap-3 px-5 py-4 md:grid-cols-[12rem_1fr]">
              <div>
                <div className="text-sm font-medium text-ink-900">{fieldLabel(f)}</div>
                <div className="mt-0.5 break-all text-xs text-ink-500">Published: {fmtValue(f === 'guideline_url' ? byField.get(f)![0].value : s[f])}</div>
              </div>
              <div className="space-y-2">
                {byField.get(f)!.map((e) => (
                  <div key={e.id}>
                    <div className="mb-1 text-xs text-ink-600">Observed <span className="font-medium text-ink-900">{fmtValue(e.value)}</span> · {methodLabel(e.method)}</div>
                    <EvidenceCard e={e} />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function HistoryTab({ d }: { d: ScholarshipDetail }) {
  const changes = d.changes.filter((c) => c.materiality !== 'cosmetic');
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <Card className="p-5">
        <h2 className="mb-4 font-semibold text-ink-900">Detected changes</h2>
        <ChangeTimeline changes={changes} />
      </Card>
      <Card>
        <CardHeader title="Record versions" subtitle="Each version is kept; nothing is overwritten." />
        <ol className="divide-y divide-ink-100">
          {d.versions.map((v, i) => {
            const prev = d.versions[i + 1];
            const deadlineChanged = prev && prev.deadline !== v.deadline;
            return (
              <li key={v.version} className="px-5 py-3 text-sm">
                <div className="flex items-center justify-between"><span className="font-medium text-ink-900">v{v.version}</span><span className="text-xs text-ink-500">{fmtDateTime(v.created_at)}</span></div>
                <div className="mt-0.5 text-xs text-ink-600">{v.reason}</div>
                <div className={`mt-1 text-xs ${deadlineChanged ? 'font-medium text-brand-700' : 'text-ink-500'}`}>Deadline: {fmtDate(v.deadline)}{deadlineChanged && ` (was ${fmtDate(prev.deadline)})`}</div>
              </li>
            );
          })}
        </ol>
      </Card>
      <div className="lg:col-span-2"><ButtonLink to="/changes" variant="secondary" size="sm">See changes across all scholarships</ButtonLink></div>
    </div>
  );
}
