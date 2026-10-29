import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import { api } from '../lib/api';
import { fmtDate, fmtDateTime } from '../lib/format';
import { Container } from '../components/Layout';
import { Card, CardHeader, EmptyState, ErrorState, LoadingBlock, PageHeader, Select } from '../components/ui';
import { ChangeTimeline } from '../components/explain';

export default function Changes() {
  const [days, setDays] = useState(30);
  const q = useQuery({ queryKey: ['feed', days], queryFn: () => api.feed(days) });
  return (
    <Container className="max-w-5xl">
      <PageHeader
        title="What changed?"
        subtitle="Material changes detected on monitored sources and newly discovered scholarships. Only changes that were auto-accepted under policy or approved by a reviewer are shown."
        actions={
          <Select aria-label="Time range" value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-40">
            <option value={7}>Last 7 days</option><option value={30}>Last 30 days</option><option value={90}>Last 90 days</option>
          </Select>
        }
      />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <Card className="p-5">
            {q.data!.changes.length ? <ChangeTimeline changes={q.data!.changes} showScholarship /> : <EmptyState title="No material changes in this period">The monitor checks registered sources on a schedule. Nothing material changed.</EmptyState>}
          </Card>
          <Card>
            <CardHeader icon={<Sparkles className="h-5 w-5" />} title="Newly discovered" subtitle="Published after review" />
            {q.data!.new_scholarships.length ? (
              <ul className="divide-y divide-ink-100">
                {q.data!.new_scholarships.map((n) => (
                  <li key={n.id} className="px-5 py-3">
                    <Link to={`/scholarships/${n.id}`} className="text-sm font-medium text-ink-900 hover:text-brand-700">{n.name}</Link>
                    <div className="mt-0.5 text-xs text-ink-500">{n.provider} · found {fmtDateTime(n.first_discovered_at)} · deadline {fmtDate(n.deadline)}</div>
                  </li>
                ))}
              </ul>
            ) : <p className="px-5 py-4 text-sm text-ink-500">None in this period.</p>}
          </Card>
        </div>
      )}
    </Container>
  );
}
