import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, ArrowRight, Bot, Clock } from 'lucide-react';
import { api } from '../../lib/api';
import { fmtDateTime, timeAgo } from '../../lib/format';
import { Card, CardHeader, ErrorState, LoadingBlock, Notice, PageHeader, Stat } from '../../components/ui';
import { HealthBadge, JobStatusBadge, SourceClassBadge, TrustBadge } from '../../components/status';
import { ChangeTimeline } from '../../components/explain';

export default function AdminOverview() {
  const q = useQuery({ queryKey: ['admin', 'overview'], queryFn: api.admin.overview, refetchInterval: 15_000 });
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error || !q.data) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const o = q.data;
  const total = o.scholarships.published;
  return (
    <div>
      <PageHeader title="Operations overview" subtitle={`All figures computed from the database at ${fmtDateTime(o.generated_at)}. Refreshes every 15 s.`} />
      {!o.scheduler.enabled && <Notice tone="amber" className="mb-4" icon={<Clock className="h-4 w-4" />}>The scheduler is disabled (SCHEDULER_ENABLED=false). Sources are only checked when you run them manually.</Notice>}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Published records" value={total} hint={`${o.scholarships.unpublished} unpublished`} />
        <Stat label="Pending review" value={o.review.pending_candidates + o.review.pending_changes} tone={o.review.pending_candidates + o.review.pending_changes ? 'amber' : 'default'} hint={`${o.review.pending_candidates} candidates · ${o.review.pending_changes} changes`} />
        <Stat label="Job success rate" value={o.jobs.success_rate == null ? '—' : `${Math.round(o.jobs.success_rate * 100)}%`} hint={`${o.jobs.all_time.succeeded ?? 0} succeeded · ${o.jobs.all_time.failed ?? 0} failed (all time)`} />
        <Stat label="Material changes (7 d)" value={o.changes_last_7_days.material} hint={`${o.changes_last_7_days.auto_accepted} auto-accepted · ${o.changes_last_7_days.cosmetic} cosmetic filtered`} />
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Sources" action={<Link to="/admin/sources" className="text-sm font-medium text-brand-700 hover:underline">Manage</Link>} />
          <ul className="divide-y divide-ink-100">
            {o.sources.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 px-5 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-ink-900">{s.name}</div>
                  <div className="mt-0.5 text-xs text-ink-500">last success {timeAgo(s.last_success_at)} · next {s.next_check_at ? fmtDateTime(s.next_check_at) : 'when due'}</div>
                </div>
                <div className="flex gap-1.5"><SourceClassBadge c={s.classification} fixture={s.is_fixture} /><HealthBadge h={s.enabled ? s.health_status : 'disabled'} /></div>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardHeader title="Records by verification status" />
          <ul className="space-y-2.5 p-5">
            {Object.entries(o.scholarships.by_verification_status).sort((a, b) => b[1] - a[1]).map(([k, n]) => (
              <li key={k}>
                <div className="flex items-center justify-between text-sm"><TrustBadge status={k} /><span className="tabular-nums text-ink-700">{n}</span></div>
                <div className="mt-1 h-1.5 rounded-full bg-ink-100" aria-hidden><div className="h-full rounded-full bg-brand-500" style={{ width: `${(n / Math.max(1, total)) * 100}%` }} /></div>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2 border-t border-ink-100 px-5 py-3 text-xs text-ink-600">
            <Bot className="h-4 w-4" />LLM extraction: {o.llm.configured ? `${o.llm.provider} / ${o.llm.model}` : 'not configured (manual entry only)'}
          </div>
        </Card>

        <Card>
          <CardHeader title="Recent failures" action={<Link to="/admin/jobs?status=failed" className="text-sm font-medium text-brand-700 hover:underline">All jobs</Link>} />
          {o.jobs.recent_failures.length === 0 ? <p className="px-5 py-4 text-sm text-ink-500">No failed jobs.</p> : (
            <ul className="divide-y divide-ink-100">
              {o.jobs.recent_failures.map((j) => (
                <li key={j.id}>
                  <Link to={`/admin/jobs/${j.id}`} className="flex items-start gap-3 px-5 py-3 hover:bg-ink-50">
                    <AlertTriangle className="mt-0.5 h-4 w-4 flex-none text-rose-500" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-ink-900">{j.source_name}</div>
                      <div className="truncate text-xs text-ink-500">{j.error_type}: {j.error_message}</div>
                    </div>
                    <span className="text-xs text-ink-400">{timeAgo(j.queued_at)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <CardHeader title="Recent material changes" action={<Link to="/admin/changes" className="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline">Review<ArrowRight className="h-3.5 w-3.5" /></Link>} />
          <div className="max-h-[28rem] overflow-auto p-5"><ChangeTimeline changes={o.recent_changes} showScholarship /></div>
        </Card>

        {o.scholarships.stale.length > 0 && (
          <Card className="xl:col-span-2">
            <CardHeader title="Stale records" subtitle="Last successful check is older than the freshness policy allows." />
            <ul className="grid gap-2 p-5 sm:grid-cols-2">
              {o.scholarships.stale.map((s) => <li key={s.id} className="text-sm"><Link to={`/scholarships/${s.id}`} className="text-ink-800 hover:text-brand-700">{s.name}</Link> <span className="text-xs text-ink-500">· {timeAgo(s.last_checked_at)}</span></li>)}
            </ul>
          </Card>
        )}
        <Card className="xl:col-span-2">
          <CardHeader title="Jobs in the last 24 hours" />
          <div className="flex flex-wrap gap-3 p-5">
            {Object.keys(o.jobs.last_24h).length === 0 ? <span className="text-sm text-ink-500">No jobs in the last 24 hours.</span> :
              Object.entries(o.jobs.last_24h).map(([k, n]) => <span key={k} className="flex items-center gap-2 text-sm"><JobStatusBadge s={k} /><span className="tabular-nums">{n}</span></span>)}
            {o.jobs.running > 0 && <span className="text-sm text-brand-700">{o.jobs.running} queued/running now</span>}
          </div>
        </Card>
      </div>
    </div>
  );
}
