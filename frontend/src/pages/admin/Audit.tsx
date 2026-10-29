import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { fmtDateTime } from '../../lib/format';
import { Card, EmptyState, ErrorState, LoadingBlock, PageHeader } from '../../components/ui';

export default function AdminAudit() {
  const q = useQuery({ queryKey: ['admin', 'audit'], queryFn: api.admin.audit });
  return (
    <div>
      <PageHeader title="Audit log" subtitle="Administrative actions: source changes, checks, approvals, rejections and imports." />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState title="No audit entries yet" /> : (
        <Card className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead className="border-b border-ink-100 text-left text-xs uppercase tracking-wide text-ink-500"><tr><th className="px-4 py-3 font-medium">When</th><th className="px-4 py-3 font-medium">Actor</th><th className="px-4 py-3 font-medium">Action</th><th className="px-4 py-3 font-medium">Details</th></tr></thead>
            <tbody className="divide-y divide-ink-100">
              {q.data.map((a) => (
                <tr key={a.id}>
                  <td className="whitespace-nowrap px-4 py-2.5 text-ink-500">{fmtDateTime(a.created_at)}</td>
                  <td className="px-4 py-2.5">{a.actor_email ?? 'system'}</td>
                  <td className="px-4 py-2.5 font-medium text-ink-900">{a.action}</td>
                  <td className="px-4 py-2.5 font-mono text-xs text-ink-600">{JSON.stringify(a.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
