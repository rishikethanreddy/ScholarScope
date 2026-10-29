import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bookmark, Trash2 } from 'lucide-react';
import { api } from '../lib/api';
import { fmtDate, timeAgo } from '../lib/format';
import { Container } from '../components/Layout';
import { Button, ButtonLink, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, Select } from '../components/ui';
import { TrustBadge } from '../components/status';

const STATUSES = [
  ['saved', 'Saved'], ['preparing', 'Preparing'], ['applied', 'Applied'], ['awarded', 'Awarded'], ['rejected', 'Not selected'],
] as const;

export default function Saved() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['saved'], queryFn: api.saved });
  const upd = useMutation({ mutationFn: ({ id, status }: { id: string; status: string }) => api.updateSaved(id, { status }), onSuccess: () => qc.invalidateQueries({ queryKey: ['saved'] }) });
  const del = useMutation({ mutationFn: api.unsave, onSuccess: () => qc.invalidateQueries({ queryKey: ['saved'] }) });

  return (
    <Container className="max-w-5xl">
      <PageHeader title="Saved scholarships" subtitle="Track where you are with each application. Deadlines update automatically when a monitored source changes them." />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? (
        <EmptyState icon={<Bookmark className="h-5 w-5" />} title="Nothing saved yet" action={<ButtonLink to="/discover">Discover scholarships</ButtonLink>}>
          Save scholarships from their detail page to track them here.
        </EmptyState>
      ) : (
        <Card>
          <ul className="divide-y divide-ink-100">
            {q.data.map((row) => (
              <li key={row.id} className="flex flex-wrap items-center gap-4 px-5 py-4">
                <div className="min-w-0 flex-1">
                  <Link to={`/scholarships/${row.scholarship.id}`} className="font-medium text-ink-900 hover:text-brand-700">{row.scholarship.name}</Link>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-500">
                    <span>Deadline {fmtDate(row.scholarship.deadline)}</span>
                    <TrustBadge status={row.scholarship.verification_status} />
                    <span>checked {timeAgo(row.scholarship.last_checked_at)}</span>
                  </div>
                </div>
                <Select aria-label="Application status" className="w-40" value={row.status} onChange={(e) => upd.mutate({ id: row.id, status: e.target.value })}>
                  {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                </Select>
                <Button variant="ghost" size="sm" aria-label={`Remove ${row.scholarship.name}`} onClick={() => del.mutate(row.id)}><Trash2 className="h-4 w-4" /></Button>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Container>
  );
}
