import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight, FileSearch, Quote } from 'lucide-react';
import type { ChangeEvent, Criterion, Evidence, RecommendationResult } from '../lib/types';
import { api, errorMessage } from '../lib/api';
import { fieldLabel, fmtDate, fmtDateTime, fmtValue, methodLabel } from '../lib/format';
import { Badge, Button, Card, Disclosure, ExternalA, Notice, cx } from './ui';
import { AvailabilityBadge, CriterionIcon, OutcomeBadge, SourceClassBadge, TrustBadge } from './status';

export function EvidenceInline({ e, compact }: { e: Evidence | null; compact?: boolean }) {
  if (!e) return <span className="text-xs text-ink-400">No evidence recorded</span>;
  return (
    <Disclosure summary={<span className="inline-flex items-center gap-1"><FileSearch className="h-3.5 w-3.5" />Evidence · {methodLabel(e.method)}</span>}>
      <EvidenceCard e={e} compact={compact} />
    </Disclosure>
  );
}

export function EvidenceCard({ e, compact }: { e: Evidence; compact?: boolean }) {
  return (
    <div className="rounded-lg border border-ink-200 bg-ink-50/60 p-3 text-xs">
      {e.snippet && (
        <blockquote className="flex gap-2 text-ink-700">
          <Quote className="h-3.5 w-3.5 flex-none text-ink-400" aria-hidden />
          <span className="whitespace-pre-wrap break-words">{e.snippet}</span>
        </blockquote>
      )}
      <div className={cx('flex flex-wrap items-center gap-x-3 gap-y-1 text-ink-500', e.snippet && 'mt-2')}>
        <SourceClassBadge c={e.classification} fixture={e.source_key?.startsWith('fixture')} />
        <span>{e.verification_status === 'dataset_claim' ? 'Dataset claim (not checked by monitor)' : e.verification_status.replace(/_/g, ' ')}</span>
        {e.retrieved_at && <span>retrieved {fmtDateTime(e.retrieved_at)}</span>}
        {e.location && !compact && <span>{e.location}</span>}
        {e.source_url && <ExternalA href={e.source_url} className="truncate max-w-[18rem]">source</ExternalA>}
      </div>
    </div>
  );
}

const ORDER = { not_satisfied: 0, unknown: 1, satisfied: 2, not_applicable: 3 } as const;

export function CriteriaList({ result, editable = true }: { result: RecommendationResult; editable?: boolean }) {
  const criteria = [...result.criteria].sort((a, b) => ORDER[a.status] - ORDER[b.status]);
  return (
    <ul className="divide-y divide-ink-100">
      {criteria.map((c) => <CriterionRow key={c.key} c={c} scholarshipId={result.scholarship_id} answers={result.answers} editable={editable} />)}
    </ul>
  );
}

function CriterionRow({ c, scholarshipId, answers, editable }: { c: Criterion; scholarshipId: string; answers?: Record<string, string>; editable: boolean }) {
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (a: 'yes' | 'no' | 'unsure') => api.answer(scholarshipId, c.resolve!.question!.key, a),
    onSuccess: () => {
      setErr(null);
      void qc.invalidateQueries({ queryKey: ['recommendation', scholarshipId] });
      void qc.invalidateQueries({ queryKey: ['recommendations'] });
    },
    onError: (e) => setErr(errorMessage(e)),
  });
  const question = c.resolve?.question;
  const current = question ? answers?.[question.key] : undefined;
  return (
    <li className="flex gap-3 py-3.5">
      <div className="pt-0.5"><CriterionIcon status={c.status} reason={c.unknown_reason} /></div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3">
          <span className="text-sm font-medium text-ink-900">{c.label}</span>
          {c.student_value !== null && c.student_value !== undefined && <span className="text-xs text-ink-500">You: {String(c.student_value)}</span>}
        </div>
        <p className="mt-0.5 text-sm text-ink-600">{c.explanation}</p>
        {c.rule && c.status !== 'not_applicable' && <p className="mt-1 text-xs text-ink-500"><span className="font-medium">Rule:</span> {c.rule}</p>}
        {c.unknown_reason === 'student_missing' && c.resolve?.profile_field && (
          <Link to={`/profile#${c.resolve.profile_field}`} className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-brand-700 hover:underline">
            Add to profile <ArrowRight className="h-3 w-3" />
          </Link>
        )}
        {c.unknown_reason === 'scholarship_unresolved' && <p className="mt-1 text-xs text-brand-700">Requires source verification. This is a gap in the scholarship record, not in your profile.</p>}
        {question && editable && (
          <div className="mt-2 rounded-lg bg-amber-50/70 p-2.5">
            <p className="text-xs font-medium text-amber-900">{question.text}</p>
            <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="Your answer">
              {(['yes', 'no', 'unsure'] as const).map((a) => (
                <Button key={a} size="sm" variant={current === a ? 'primary' : 'secondary'} aria-pressed={current === a} loading={m.isPending && m.variables === a} onClick={() => m.mutate(a)}>
                  {a === 'unsure' ? 'Not sure' : a[0].toUpperCase() + a.slice(1)}
                </Button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-amber-800">Self-declared answers help you filter; the provider makes the final decision.</p>
            {err && <p className="mt-1 text-xs text-rose-700">{err}</p>}
          </div>
        )}
        {c.evidence && <div className="mt-1.5"><EvidenceInline e={c.evidence} compact /></div>}
      </div>
    </li>
  );
}

export function RelevanceBreakdown({ r }: { r: RecommendationResult['relevance'] }) {
  if (!r) return null;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="text-sm font-medium text-ink-800">Relevance score</span>
        <span className="text-lg font-semibold tabular-nums text-ink-900">{r.score.toFixed(0)}<span className="text-sm font-normal text-ink-400">/100</span></span>
      </div>
      <ul className="mt-3 space-y-2.5">
        {Object.entries(r.factors).map(([k, f]) => (
          <li key={k}>
            <div className="flex justify-between text-xs"><span className="font-medium text-ink-700">{k.replace(/_/g, ' ')}</span><span className="tabular-nums text-ink-500">+{f.contribution.toFixed(1)}</span></div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink-100" aria-hidden>
              <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.round(f.value * 100)}%` }} />
            </div>
            <div className="mt-0.5 text-[11px] text-ink-500">{f.detail}</div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] text-ink-500">{r.note}</p>
    </div>
  );
}

export function ChangeTimeline({ changes, showScholarship }: { changes: ChangeEvent[]; showScholarship?: boolean }) {
  if (!changes.length) return <p className="text-sm text-ink-500">No changes recorded.</p>;
  return (
    <ol className="relative space-y-4 border-l border-ink-200 pl-5">
      {changes.map((c) => (
        <li key={c.id} className="relative">
          <span className={cx('absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-white',
            c.review_status === 'pending' ? 'bg-amber-400' : c.review_status === 'rejected' ? 'bg-ink-300' : 'bg-brand-500')} aria-hidden />
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-500">
            <time dateTime={c.detected_at}>{fmtDateTime(c.detected_at)}</time>
            <Badge tone={c.review_status === 'pending' ? 'amber' : c.review_status === 'rejected' ? 'neutral' : 'blue'}>{c.review_status.replace('_', ' ')}</Badge>
            <span>{methodLabel(c.method)}</span>
          </div>
          {showScholarship && c.scholarship_id && (
            <Link to={`/scholarships/${c.scholarship_id}`} className="mt-1 block text-sm font-medium text-ink-900 hover:text-brand-700">{c.scholarship_name}</Link>
          )}
          <div className="mt-1 text-sm text-ink-800">
            <span className="font-medium">{fieldLabel(c.field)}</span>{' '}
            {c.field === 'page_content' ? <span className="text-ink-600">page text changed</span> : (
              <>
                <span className="text-ink-500 line-through decoration-ink-300">{fmtValue(c.old_value)}</span>
                <ArrowRight className="mx-1 inline h-3.5 w-3.5 text-ink-400" aria-label="changed to" />
                <span className="font-medium text-ink-900">{fmtValue(c.new_value)}</span>
              </>
            )}
          </div>
          {c.evidence_snippet && (
            <div className="mt-1.5">
              <Disclosure summary="Show evidence">
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded-lg bg-ink-50 p-2.5 text-xs text-ink-700">{c.evidence_snippet}</pre>
                {c.source_url && <ExternalA href={c.source_url} className="mt-1 inline-block text-xs">Open source</ExternalA>}
              </Disclosure>
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}

export function ResultCard({ r }: { r: RecommendationResult }) {
  const s = r.scholarship;
  const unknown = r.criteria.filter((c) => c.status === 'unknown').length;
  const failed = r.criteria.filter((c) => c.status === 'not_satisfied');
  return (
    <Card className="group p-4 transition-shadow hover:shadow-md sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link to={`/scholarships/${s.id}`} className="text-[15px] font-semibold text-ink-900 group-hover:text-brand-700 focus:outline-none focus-visible:underline">
            {s.name}
          </Link>
          <div className="mt-0.5 text-sm text-ink-500">{s.provider}</div>
        </div>
        {r.relevance && (
          <div className="text-right" title={r.relevance.note}>
            <div className="text-lg font-semibold tabular-nums text-ink-900">{r.relevance.score.toFixed(0)}</div>
            <div className="text-[10px] uppercase tracking-wide text-ink-400">relevance</div>
          </div>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        <OutcomeChip r={r} />
      </div>
      <div className="mt-3 grid gap-x-4 gap-y-1 text-xs text-ink-600 sm:grid-cols-3">
        <span><span className="text-ink-400">Award</span> {s.amount_text ?? '—'}</span>
        <span><span className="text-ink-400">Deadline</span> {fmtDate(s.deadline)}</span>
        <span><span className="text-ink-400">Checked</span> {s.last_checked_at ? fmtDate(s.last_checked_at) : 'not yet by monitor'}</span>
      </div>
      {r.outcome === 'not_eligible' && failed[0] && <p className="mt-2 text-xs text-rose-700">{failed[0].explanation}</p>}
      {unknown > 0 && r.outcome !== 'not_eligible' && <p className="mt-2 text-xs text-amber-800">{unknown} criteria unresolved. Open to see what is missing.</p>}
    </Card>
  );
}


function OutcomeChip({ r }: { r: RecommendationResult }) {
  return (
    <>
      <OutcomeBadge outcome={r.outcome} />
      <AvailabilityBadge a={r.availability} deadline={r.scholarship.deadline} />
      <TrustBadge status={r.verification_status} />
    </>
  );
}

export function ConflictNotice({ conflicts }: { conflicts?: { field: string; values: { source: string; value: unknown }[] }[] }) {
  if (!conflicts?.length) return null;
  return (
    <Notice tone="red">
      <div className="font-semibold">Sources disagree</div>
      <ul className="mt-1 space-y-0.5">
        {conflicts.map((c) => <li key={c.field}>{fieldLabel(c.field)}: {c.values.map((v) => `${v.source} says ${fmtValue(v.value)}`).join('; ')}</li>)}
      </ul>
    </Notice>
  );
}
