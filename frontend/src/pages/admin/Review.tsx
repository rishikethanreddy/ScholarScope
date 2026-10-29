import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Bot, Check, Link2, X } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { Candidate } from '../../lib/types';
import { fieldLabel, fmtDateTime, fmtValue, methodLabel } from '../../lib/format';
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, ExternalA, Input, LoadingBlock, Notice, PageHeader, Tabs, Textarea } from '../../components/ui';

export default function AdminReview() {
  const { id } = useParams();
  return id ? <CandidateDetail id={id} /> : <CandidateList />;
}

function CandidateList() {
  const [status, setStatus] = useState<'pending' | 'approved' | 'rejected'>('pending');
  const q = useQuery({ queryKey: ['admin', 'candidates', status], queryFn: () => api.admin.candidates(status) });
  return (
    <div>
      <PageHeader title="Review queue" subtitle="Records proposed by the crawler or AI extraction. Nothing here is published until an admin approves it." />
      <Tabs label="Candidate status" value={status} onChange={setStatus} tabs={[{ id: 'pending', label: 'Pending' }, { id: 'approved', label: 'Approved' }, { id: 'rejected', label: 'Rejected' }]} />
      <div className="mt-4">
        {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState title={`No ${status} candidates`} /> : (
          <ul className="space-y-3">
            {q.data.map((c) => (
              <li key={c.id}>
                <Link to={`/admin/review/${c.id}`}>
                  <Card className="p-4 transition-shadow hover:shadow-md">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-medium text-ink-900">{c.title}</span>
                      <div className="flex gap-1.5">
                        <Badge tone={c.kind === 'new' ? 'violet' : 'blue'}>{c.kind === 'new' ? 'New record' : 'Update'}</Badge>
                        {c.possible_matches?.[0]?.decision === 'possible' && <Badge tone="amber">Possible duplicate</Badge>}
                        {(c.validation?.errors?.length ?? 0) > 0 && <Badge tone="red">{c.validation.errors!.length} errors</Badge>}
                        <Badge>{c.extraction_status === 'succeeded' ? 'AI extracted' : c.extraction_status === 'failed' ? 'Extraction failed' : methodLabel(c.extraction_method)}</Badge>
                      </div>
                    </div>
                    <div className="mt-1 text-xs text-ink-500">Created {fmtDateTime(c.created_at)} · {Object.keys(c.payload).length} fields</div>
                  </Card>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

const EDITABLE: { key: string; kind: 'text' | 'date' | 'number' | 'list' | 'json' }[] = [
  { key: 'name', kind: 'text' }, { key: 'provider', kind: 'text' }, { key: 'official_source_url', kind: 'text' }, { key: 'application_url', kind: 'text' },
  { key: 'open_date', kind: 'date' }, { key: 'deadline', kind: 'date' }, { key: 'renewal_type', kind: 'text' },
  { key: 'education_rule', kind: 'text' }, { key: 'education_levels', kind: 'list' }, { key: 'courses_text', kind: 'text' }, { key: 'fields_text', kind: 'text' },
  { key: 'discipline_rule', kind: 'text' }, { key: 'disciplines', kind: 'list' },
  { key: 'academic_rule', kind: 'text' }, { key: 'min_percentage', kind: 'number' }, { key: 'min_cgpa', kind: 'number' }, { key: 'academic_note', kind: 'text' },
  { key: 'income_rule', kind: 'text' }, { key: 'income_limit', kind: 'number' }, { key: 'income_note', kind: 'text' },
  { key: 'genders', kind: 'list' }, { key: 'categories', kind: 'list' }, { key: 'eligible_states', kind: 'list' },
  { key: 'disability_rule', kind: 'text' }, { key: 'min_disability_percent', kind: 'number' },
  { key: 'amount_text', kind: 'text' }, { key: 'amount_frequency', kind: 'text' }, { key: 'required_documents', kind: 'list' },
  { key: 'special_note', kind: 'text' }, { key: 'conditions', kind: 'json' }, { key: 'exclusions', kind: 'text' }, { key: 'description', kind: 'text' },
];

function toInput(kind: string, v: unknown): string {
  if (v === null || v === undefined) return '';
  if (kind === 'list') return Array.isArray(v) ? v.join(', ') : String(v);
  if (kind === 'json') return JSON.stringify(v, null, 1);
  return String(v);
}

function fromInput(kind: string, s: string): unknown {
  if (s.trim() === '') return kind === 'list' || kind === 'json' ? [] : null;
  if (kind === 'number') return Number(s);
  if (kind === 'list') return s.split(',').map((x) => x.trim()).filter(Boolean);
  if (kind === 'json') return JSON.parse(s);
  return s;
}

function CandidateDetail({ id }: { id: string }) {
  const q = useQuery({ queryKey: ['admin', 'candidate', id], queryFn: () => api.admin.candidate(id) });
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  return <CandidateEditor key={q.data.id + q.data.updated_at} c={q.data} />;
}

function CandidateEditor({ c }: { c: Candidate }) {
  const id = c.id;
  const qc = useQueryClient();
  const nav = useNavigate();
  const [draft, setDraft] = useState<Record<string, string>>(() => Object.fromEntries(EDITABLE.map(({ key, kind }) => [key, toInput(kind, c.payload[key])])));
  const [note, setNote] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin'] });
  const buildPayload = () => {
    const out: Record<string, unknown> = { ...c!.payload };
    for (const { key, kind } of EDITABLE) out[key] = fromInput(kind, draft[key] ?? '');
    return out;
  };
  const approve = useMutation({ mutationFn: () => api.admin.approve(id, buildPayload(), note || undefined), onSuccess: (r) => { void refresh(); nav(`/scholarships/${r.scholarship_id}`); }, onError: (e) => setErr(errorMessage(e)) });
  const reject = useMutation({ mutationFn: () => api.admin.reject(id, note || undefined), onSuccess: () => { void refresh(); nav('/admin/review'); }, onError: (e) => setErr(errorMessage(e)) });
  const link = useMutation({ mutationFn: (sid: string) => api.admin.link(id, sid), onSuccess: (r) => { void refresh(); nav(`/scholarships/${r.scholarship_id}`); }, onError: (e) => setErr(errorMessage(e)) });
  const extract = useMutation({ mutationFn: () => api.admin.extract(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin', 'candidate', id] }), onError: (e) => setErr(errorMessage(e)) });

  const v = c.validation ?? {};
  const pending = c.status === 'pending';

  return (
    <div>
      <Link to="/admin/review" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900"><ArrowLeft className="h-4 w-4" />Review queue</Link>
      <PageHeader title={c.title} subtitle={<span className="flex flex-wrap items-center gap-2"><Badge tone={c.kind === 'new' ? 'violet' : 'blue'}>{c.kind === 'new' ? 'New record' : 'Update to existing record'}</Badge><Badge>{c.status}</Badge> created {fmtDateTime(c.created_at)}</span>} />
      {err && <Notice tone="red" className="mb-4">{err}</Notice>}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="space-y-6">
          {c.possible_matches?.length > 0 && c.kind === 'new' && (
            <Card>
              <CardHeader title="Similar existing records" subtitle="Similarity only proposes a match. Confirm before linking; never merge distinct schemes." />
              <ul className="divide-y divide-ink-100">
                {c.possible_matches.map((m) => (
                  <li key={m.scholarship_id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                    <div className="min-w-0">
                      <Link to={`/scholarships/${m.scholarship_id}`} className="text-sm font-medium text-ink-900 hover:text-brand-700">{m.name}</Link>
                      <div className="text-xs text-ink-500">score {m.score.toFixed(2)} · {m.decision}{m.url_match && ' · same guideline URL'}{m.conflict && <span className="text-rose-700"> · conflict: {m.conflict}</span>}</div>
                    </div>
                    {pending && <Button size="sm" variant="secondary" onClick={() => link.mutate(m.scholarship_id)} loading={link.isPending}><Link2 className="h-3.5 w-3.5" />Same scheme: link</Button>}
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <Card>
            <CardHeader title="Candidate fields" subtitle="Edit before approving. Edited fields are recorded as admin-entered evidence." />
            <div className="divide-y divide-ink-100">
              {EDITABLE.map(({ key, kind }) => {
                const ev = c.evidence?.[key];
                const unsupported = v.unsupported?.find((u) => u.field === key || fieldLabel(u.field) === fieldLabel(key));
                return (
                  <div key={key} className="grid gap-2 px-5 py-3 md:grid-cols-[11rem_1fr]">
                    <label htmlFor={`f-${key}`} className="text-xs font-medium text-ink-600">{fieldLabel(key)}</label>
                    <div>
                      {kind === 'json' || (kind === 'text' && (key === 'description' || key.endsWith('_note'))) ? (
                        <Textarea id={`f-${key}`} disabled={!pending} value={draft[key] ?? ''} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} className="min-h-16 font-mono text-xs" />
                      ) : (
                        <Input id={`f-${key}`} disabled={!pending} type={kind === 'date' ? 'date' : kind === 'number' ? 'number' : 'text'} value={draft[key] ?? ''} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
                      )}
                      {ev?.snippet && <q className="mt-1 block text-xs text-ink-500">{ev.snippet}{ev.location && ` (${ev.location})`}</q>}
                      {unsupported && <p className="mt-1 text-xs text-amber-700">Rejected AI value {fmtValue(unsupported.value)}: {unsupported.reason}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card className="p-5">
            <h2 className="font-semibold text-ink-900">Validation</h2>
            {(v.errors?.length ?? 0) === 0 && (v.warnings?.length ?? 0) === 0 && <p className="mt-2 text-sm text-emerald-700">No validation issues.</p>}
            {v.errors?.map((e) => <Notice key={e} tone="red" className="mt-2">{e}</Notice>)}
            {v.warnings?.map((w) => <Notice key={w} tone="amber" className="mt-2">{w}</Notice>)}
            {v.missing_for_publication && <p className="mt-2 text-xs text-ink-600">Eligibility fields not yet filled: {v.missing_for_publication.join(', ')}. They will show as "unknown" to students until provided.</p>}
          </Card>
          <Card className="p-5 text-sm">
            <h2 className="mb-2 font-semibold text-ink-900">Provenance</h2>
            <dl className="space-y-1.5 text-xs">
              <div><dt className="inline text-ink-500">Method: </dt><dd className="inline">{methodLabel(c.extraction_method)}</dd></div>
              <div><dt className="inline text-ink-500">AI extraction: </dt><dd className="inline">{c.extraction_status}{c.llm_model && ` (${c.llm_provider}/${c.llm_model})`}</dd></div>
              {c.extraction_error && <div className="text-rose-700">{c.extraction_error}</div>}
              {c.document && <div><dt className="inline text-ink-500">Document: </dt><dd className="inline"><ExternalA href={c.document.url}>{c.document.url}</ExternalA> · {fmtDateTime(c.document.fetched_at)}</dd></div>}
              {typeof c.payload.official_source_url === 'string' && <div><dt className="inline text-ink-500">Guideline: </dt><dd className="inline"><ExternalA href={c.payload.official_source_url}>{c.payload.official_source_url}</ExternalA></dd></div>}
            </dl>
            {pending && <Button className="mt-3 w-full" variant="secondary" onClick={() => extract.mutate()} loading={extract.isPending}><Bot className="h-4 w-4" />Run AI extraction on document</Button>}
            {extract.isPending && <p className="mt-2 text-xs text-ink-500">Fetching the guideline and extracting. This can take up to a minute.</p>}
          </Card>
          {pending ? (
            <Card className="p-5">
              <h2 className="mb-2 font-semibold text-ink-900">Decision</h2>
              <Textarea aria-label="Review note" placeholder="Review note (optional)" value={note} onChange={(e) => setNote(e.target.value)} className="min-h-16" />
              <div className="mt-3 flex gap-2">
                <Button className="flex-1" onClick={() => approve.mutate()} loading={approve.isPending}><Check className="h-4 w-4" />Approve &amp; publish</Button>
                <Button variant="secondary" onClick={() => reject.mutate()} loading={reject.isPending}><X className="h-4 w-4" />Reject</Button>
              </div>
            </Card>
          ) : <Notice tone="neutral">This candidate was {c.status} {c.reviewed_at && `on ${fmtDateTime(c.reviewed_at)}`}.{c.review_note && ` Note: ${c.review_note}`}</Notice>}
        </div>
      </div>
    </div>
  );
}

