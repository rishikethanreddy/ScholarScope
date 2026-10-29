import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, Check, X } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import { fieldLabel, fmtDateTime, fmtValue, methodLabel } from '../../lib/format';
import { Badge, Button, Card, EmptyState, ErrorState, ExternalA, LoadingBlock, Notice, PageHeader, Tabs } from '../../components/ui';

type Status = 'pending' | 'auto_accepted' | 'accepted' | 'rejected' | 'informational';

export default function AdminChanges() {
  const qc = useQueryClient();
  const [status, setStatus] = useState<Status>('pending');
  const [err, setErr] = useState<string | null>(null);
  const q = useQuery({ queryKey: ['admin', 'changes', status], queryFn: () => api.admin.changes(status) });
  const decide = useMutation({
    mutationFn: ({ id, accept }: { id: string; accept: boolean }) => (accept ? api.admin.acceptChange(id) : api.admin.rejectChange(id)),
    onSuccess: () => { setErr(null); void qc.invalidateQueries({ queryKey: ['admin'] }); },
    onError: (e) => setErr(errorMessage(e)),
  });
  return (
    <div>
      <PageHeader title="Detected changes" subtitle="Deterministic official-listing changes to deadlines and windows are auto-accepted under policy (config/policies.json). Everything else waits here." />
      <Tabs label="Change status" value={status} onChange={setStatus} tabs={[
        { id: 'pending', label: 'Pending' }, { id: 'auto_accepted', label: 'Auto-accepted' }, { id: 'accepted', label: 'Accepted' }, { id: 'rejected', label: 'Rejected' }, { id: 'informational', label: 'Cosmetic (filtered)' },
      ]} />
      {err && <Notice tone="red" className="mt-4">{err}</Notice>}
      <div className="mt-4">
        {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : !q.data?.length ? <EmptyState title="Nothing here" /> : (
          <ul className="space-y-3">
            {q.data.map((c) => (
              <li key={c.id}>
                <Card className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      {c.scholarship_id ? <Link to={`/scholarships/${c.scholarship_id}`} className="font-medium text-ink-900 hover:text-brand-700">{c.scholarship_name}</Link> : <span className="font-medium text-ink-900">Unlinked source page</span>}
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-500">
                        <Badge tone={c.materiality === 'material' ? 'red' : c.materiality === 'cosmetic' ? 'neutral' : 'amber'}>{c.materiality}</Badge>
                        <span>{fmtDateTime(c.detected_at)}</span><span>{methodLabel(c.method)}</span>
                        {c.source_url && <ExternalA href={c.source_url}>source</ExternalA>}
                      </div>
                      <div className="mt-2 text-sm">
                        <span className="font-medium">{fieldLabel(c.field)}</span>{' '}
                        {c.field === 'page_content' ? 'main text changed' : <>{fmtValue(c.old_value)} <ArrowRight className="mx-1 inline h-3.5 w-3.5" /> <b>{fmtValue(c.new_value)}</b></>}
                      </div>
                      {c.evidence_snippet && <pre className="mt-2 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-ink-50 p-2 text-xs text-ink-700">{c.evidence_snippet}</pre>}
                    </div>
                    {c.review_status === 'pending' && (
                      <div className="flex gap-1.5">
                        <Button size="sm" onClick={() => decide.mutate({ id: c.id, accept: true })} loading={decide.isPending && decide.variables?.id === c.id && decide.variables.accept}><Check className="h-3.5 w-3.5" />Accept</Button>
                        <Button size="sm" variant="secondary" onClick={() => decide.mutate({ id: c.id, accept: false })}><X className="h-3.5 w-3.5" />Reject</Button>
                      </div>
                    )}
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
