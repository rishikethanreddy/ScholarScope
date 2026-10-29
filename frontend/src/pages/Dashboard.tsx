import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { ArrowRight, BellRing, CalendarDays, CheckCheck, FileUp, ListChecks, Sparkles, UserPen } from 'lucide-react';
import { api } from '../lib/api';
import { fmtDate, fmtValue } from '../lib/format';
import type { RecommendationResult } from '../lib/types';
import { Container } from '../components/Layout';
import { Badge, Button, ButtonLink, Card, CardHeader, EmptyState, ErrorState, LoadingBlock, PageHeader, Stat } from '../components/ui';
import { ResultCard } from '../components/explain';

const OUTCOME_TEXT: Record<string, string> = {
  eligible: 'eligible', eligible_pending_verification: 'meets recorded criteria', potential_match: 'potential match', not_eligible: 'not eligible',
};

export default function Dashboard() {
  const qc = useQueryClient();
  const recQ = useQuery({ queryKey: ['recommendations'], queryFn: api.recommendations });
  const ack = useMutation({ mutationFn: api.acknowledgeUpdates, onSuccess: () => qc.invalidateQueries({ queryKey: ['recommendations'] }) });

  const data = recQ.data;
  const { active, closedMatches, deadlines } = useMemo(() => {
    const res = data?.results ?? [];
    const candidates = res.filter((r) => r.outcome !== 'not_eligible');
    const active = candidates.filter((r) => r.availability.state === 'open' || r.availability.state === 'upcoming' || r.availability.state === 'unknown');
    const closedMatches = candidates.filter((r) => r.availability.state === 'closed');
    const deadlines = candidates
      .filter((r) => r.availability.state === 'open' && r.scholarship.deadline)
      .sort((a, b) => (a.scholarship.deadline! < b.scholarship.deadline! ? -1 : 1))
      .slice(0, 8);
    return { active, closedMatches, deadlines };
  }, [data]);

  if (recQ.isLoading) return <Container><LoadingBlock rows={4} /></Container>;
  if (recQ.error || !data) return <Container><ErrorState error={recQ.error} onRetry={() => recQ.refetch()} /></Container>;
  const c = data.counts;

  return (
    <Container>
      <PageHeader
        title="Your scholarship dashboard"
        subtitle={<>Computed {new Date(data.computed_at).toLocaleString('en-IN')} from {data.results.length} published records. Recommendations are guidance, not official decisions.</>}
        actions={<><ButtonLink to="/profile" variant="secondary"><UserPen className="h-4 w-4" />Edit profile</ButtonLink><ButtonLink to="/check-document" variant="secondary"><FileUp className="h-4 w-4" />Check a PDF</ButtonLink></>}
      />

      {data.updates.items.length > 0 && (
        <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }}>
          <Card className="mb-6 border-brand-200 bg-brand-50/50">
            <CardHeader
              icon={<BellRing className="h-5 w-5 text-brand-600" />}
              title="New opportunities and changes for you"
              subtitle={data.updates.since ? `Since ${new Date(data.updates.since).toLocaleString('en-IN')}` : undefined}
              action={<Button size="sm" variant="secondary" loading={ack.isPending} onClick={() => ack.mutate()}><CheckCheck className="h-4 w-4" />Mark as seen</Button>}
            />
            <ul className="divide-y divide-brand-100">
              {data.updates.items.map((u) => (
                <li key={u.scholarship_id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                  <div className="min-w-0">
                    <Link to={`/scholarships/${u.scholarship_id}`} className="text-sm font-medium text-ink-900 hover:text-brand-700">{u.name}</Link>
                    <div className="mt-0.5 text-xs text-ink-600">
                      {u.kind === 'new_opportunity' ? <>Newly published · now {OUTCOME_TEXT[u.now!.outcome]}</> :
                        Object.entries(u.changes ?? {}).map(([k, ch]) => (
                          <span key={k} className="mr-3">{k}: {k === 'outcome' ? OUTCOME_TEXT[String(ch.from)] : fmtValue(ch.from)} → <b>{k === 'outcome' ? OUTCOME_TEXT[String(ch.to)] : fmtValue(ch.to)}</b></span>
                        ))}
                    </div>
                  </div>
                  <Badge tone={u.kind === 'new_opportunity' ? 'green' : 'blue'} icon={<Sparkles className="h-3 w-3" />}>{u.kind === 'new_opportunity' ? 'New' : 'Changed'}</Badge>
                </li>
              ))}
            </ul>
          </Card>
        </motion.div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Eligible (recorded)" value={c.eligible ?? 0} tone="green" hint="All recorded rules satisfied" />
        <Stat label="Meets recorded rules" value={c.eligible_pending_verification ?? 0} hint="Some rules still need source verification" />
        <Stat label="Potential matches" value={c.potential_match ?? 0} tone="amber" hint="Answer questions to resolve" />
        <Stat label="Open now among matches" value={active.filter((r) => r.availability.state === 'open').length} hint={`${closedMatches.length} matching but closed`} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="min-w-0 space-y-4">
          <div className="flex items-end justify-between">
            <h2 className="text-lg font-semibold text-ink-900">Best matches you can still apply for</h2>
            <Link to="/discover" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">All scholarships<ArrowRight className="h-4 w-4" /></Link>
          </div>
          {active.length === 0 ? (
            <EmptyState title="No open matches right now" action={<ButtonLink to="/profile" variant="secondary">Review profile</ButtonLink>}>
              None of the open scholarships match your recorded profile. Adding missing details can turn unknown criteria into matches.
            </EmptyState>
          ) : (
            active.slice(0, 8).map((r, i) => (
              <motion.div key={r.scholarship_id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i * 0.04, 0.3) }}>
                <ResultCard r={r} />
              </motion.div>
            ))
          )}
          {closedMatches.length > 0 && (
            <details className="rounded-2xl border border-ink-200 bg-white p-4">
              <summary className="cursor-pointer text-sm font-medium text-ink-700">{closedMatches.length} matching scholarships are currently closed</summary>
              <ul className="mt-3 space-y-2">
                {closedMatches.map((r) => (
                  <li key={r.scholarship_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <Link to={`/scholarships/${r.scholarship_id}`} className="text-ink-800 hover:text-brand-700">{r.scholarship.name}</Link>
                    <span className="text-xs text-ink-500">closed {fmtDate(r.scholarship.deadline)}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader icon={<ListChecks className="h-5 w-5" />} title="Information that would resolve matches" />
            {data.missing_profile_fields.length === 0 ? (
              <p className="px-5 py-4 text-sm text-ink-500">Your profile answers every rule that uses profile data. Remaining unknowns are scheme-specific questions or gaps in the scholarship records.</p>
            ) : (
              <ul className="divide-y divide-ink-100">
                {data.missing_profile_fields.map((m) => (
                  <li key={m.field}>
                    <Link to={`/profile#${m.field}`} className="flex items-center justify-between px-5 py-3 text-sm hover:bg-ink-50">
                      <span className="text-ink-800">{m.label}</span>
                      <span className="text-xs text-ink-500">affects {m.affects}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <CardHeader icon={<CalendarDays className="h-5 w-5" />} title="Upcoming deadlines" subtitle="Among your matches" />
            {deadlines.length === 0 ? <p className="px-5 py-4 text-sm text-ink-500">No upcoming deadlines among your matches.</p> : (
              <ol className="space-y-0.5 p-3">
                {deadlines.map((r) => <DeadlineRow key={r.scholarship_id} r={r} />)}
              </ol>
            )}
          </Card>
        </aside>
      </div>
    </Container>
  );
}

function DeadlineRow({ r }: { r: RecommendationResult }) {
  const d = r.availability.days_left ?? 0;
  return (
    <li>
      <Link to={`/scholarships/${r.scholarship_id}`} className="flex items-center gap-3 rounded-lg p-2 hover:bg-ink-50">
        <div className={`w-12 flex-none rounded-lg py-1 text-center ${d <= 14 ? 'bg-rose-50 text-rose-700' : 'bg-ink-100 text-ink-700'}`}>
          <div className="text-sm font-semibold tabular-nums">{d}</div>
          <div className="text-[10px] uppercase">days</div>
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm text-ink-800">{r.scholarship.name}</div>
          <div className="mt-0.5 text-xs text-ink-500"><span className="whitespace-nowrap">{fmtDate(r.scholarship.deadline)}</span> · {OUTCOME_TEXT[r.outcome]}</div>
        </div>
      </Link>
    </li>
  );
}
