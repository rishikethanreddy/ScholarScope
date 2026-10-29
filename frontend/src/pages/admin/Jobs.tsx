import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RotateCcw } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import { fmtDateTime, timeAgo } from '../../lib/format';
import { Button, Card, CardHeader, EmptyState, ErrorState, LoadingBlock, Notice, PageHeader, Select } from '../../components/ui';
import { JobStatusBadge } from '../../components/status';

export default function AdminJobs() {
  const { id } = useParams();
  return id ? <JobDetail id={id} /> : <JobList />;
}

function JobList() {
  const [params, setParams] = useSearchParams();
  const status = params.get('status') ?? '';
  const q = useQuery({ queryKey: ['admin', 'jobs', status], queryFn: () => api.admin.jobs(status ? { status } : undefined), refetchInterval: 5000 });
  return (
    <div>
      <PageHeader title="Crawl jobs" subtitle="Every scheduled and manual check, with its outcome. Refreshes every 5 s."
        actions={<Select aria-label="Status filter" value={status} onChange={(e) => setParams(e.target.value ? { status: e.target.value } : {})} className="w-40">
          <option value="">All statuses</option><option value="running">Running</option><option value="queued">Queued</option><option value="succeeded">Succeeded</option><option value="failed">Failed</option><option value="skipped">Skipped</option>
        </Select>} />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState title="No jobs yet">Run a source check from the Sources page, or wait for the scheduler.</EmptyState> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[44rem] text-sm">
            <thead className="border-b border-ink-100 text-left text-xs uppercase tracking-wide text-ink-500">
              <tr><th className="px-4 py-3 font-medium">Source</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 font-medium">Trigger</th><th className="px-4 py-3 font-medium">Seen / matched</th><th className="px-4 py-3 font-medium">Changes</th><th className="px-4 py-3 font-medium">Candidates</th><th className="px-4 py-3 font-medium">Queued</th></tr>
            </thead>
            <tbody className="divide-y divide-ink-100">
              {q.data.map((j) => (
                <tr key={j.id} className="hover:bg-ink-50">
                  <td className="px-4 py-3"><Link to={`/admin/jobs/${j.id}`} className="font-medium text-ink-900 hover:text-brand-700">{j.source_name}</Link>{j.error_type && <div className="text-xs text-rose-700">{j.error_type}</div>}</td>
                  <td className="px-4 py-3"><JobStatusBadge s={j.status} /></td>
                  <td className="px-4 py-3 text-ink-600">{j.trigger}</td>
                  <td className="px-4 py-3 tabular-nums">{j.records_seen} / {j.records_matched}</td>
                  <td className="px-4 py-3 tabular-nums">{j.changes_detected}</td>
                  <td className="px-4 py-3 tabular-nums">{j.candidates_created}</td>
                  <td className="px-4 py-3 text-ink-500" title={fmtDateTime(j.queued_at)}>{timeAgo(j.queued_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}

function JobDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['admin', 'job', id], queryFn: () => api.admin.job(id), refetchInterval: (query) => (['queued', 'running'].includes(query.state.data?.status ?? '') ? 2000 : false) });
  const retry = useMutation({ mutationFn: () => api.admin.retryJob(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }) });
  if (q.isLoading) return <LoadingBlock />;
  if (q.error || !q.data) return <ErrorState error={q.error} />;
  const j = q.data;
  return (
    <div>
      <Link to="/admin/jobs" className="mb-3 inline-flex items-center gap-1 text-sm text-ink-500 hover:text-ink-900"><ArrowLeft className="h-4 w-4" />All jobs</Link>
      <PageHeader title={j.source_name ?? 'Job'} subtitle={<span className="flex flex-wrap items-center gap-2"><JobStatusBadge s={j.status} /> {j.trigger} · queued {fmtDateTime(j.queued_at)} {j.duration_ms != null && `· ${(j.duration_ms / 1000).toFixed(1)} s`}</span>}
        actions={j.status === 'failed' ? <Button onClick={() => retry.mutate()} loading={retry.isPending}><RotateCcw className="h-4 w-4" />Retry</Button> : undefined} />
      {retry.error && <Notice tone="red" className="mb-4">{errorMessage(retry.error)}</Notice>}
      {retry.data && <Notice tone="green" className="mb-4">Retry queued. <Link to={`/admin/jobs/${retry.data.id}`} className="underline">Open new job</Link></Notice>}
      {j.error_message && <Notice tone="red" className="mb-4"><b>{j.error_type}</b>: {j.error_message}</Notice>}
      <div className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-6">
        {[['Pages', j.pages_fetched], ['Unchanged', j.pages_unchanged], ['Seen', j.records_seen], ['Matched', j.records_matched], ['Changes', j.changes_detected], ['Candidates', j.candidates_created]].map(([l, v]) => (
          <Card key={l as string} className="p-3"><div className="text-xs text-ink-500">{l}</div><div className="text-xl font-semibold tabular-nums">{v}</div></Card>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <Card>
          <CardHeader title="Job log" />
          <ol className="max-h-[36rem] overflow-auto px-5 py-3 font-mono text-xs leading-relaxed text-ink-700">
            {(j.log ?? []).map((l, i) => <li key={i} className="border-b border-ink-50 py-1"><span className="mr-2 text-ink-400">{new Date(l.t).toLocaleTimeString('en-IN')}</span>{l.msg}</li>)}
          </ol>
        </Card>
        <Card>
          <CardHeader title="Retrieved documents" subtitle="Raw bytes are archived by SHA-256." />
          <ul className="divide-y divide-ink-100">
            {(j.documents ?? []).map((d) => (
              <li key={d.id} className="px-5 py-3 text-xs">
                <div className="break-all text-ink-800">{d.url}</div>
                <div className="mt-1 text-ink-500">HTTP {d.http_status ?? '—'} · {d.bytes ?? 0} bytes · {d.not_modified ? '304 not modified' : d.quality ?? 'parsed'}</div>
                {d.content_sha256 && <div className="mt-0.5 font-mono text-[10px] text-ink-400">{d.content_sha256.slice(0, 24)}…</div>}
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
