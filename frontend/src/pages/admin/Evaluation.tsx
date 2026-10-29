import { useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import { fmtDateTime } from '../../lib/format';
import { Card, CardHeader, EmptyState, ErrorState, LoadingBlock, Notice, PageHeader } from '../../components/ui';

interface Metric { name: string; value: number | string | null; n?: number; note?: string }
interface Experiment { id: string; title: string; description: string; data: string; metrics: Metric[]; limitations?: string[]; baseline?: Metric[] }

export default function AdminEvaluation() {
  const q = useQuery({ queryKey: ['admin', 'evaluation'], queryFn: api.admin.evaluation });
  if (q.isLoading) return <LoadingBlock />;
  if (q.error) return <ErrorState error={q.error} />;
  const d = q.data as { available: boolean; message?: string; generated_at?: string; experiments?: Experiment[]; label_provenance?: string };
  return (
    <div>
      <PageHeader title="Evaluation" subtitle="Results produced by `python -m evaluation.run` on archived snapshots and labelled cases. Numbers are shown exactly as measured." />
      {!d.available ? <EmptyState title="No evaluation results yet">{d.message}</EmptyState> : (
        <>
          <Notice tone="amber" className="mb-5">Generated {fmtDateTime(d.generated_at)}. {d.label_provenance}</Notice>
          <div className="space-y-5">
            {d.experiments!.map((e) => (
              <Card key={e.id}>
                <CardHeader title={e.title} subtitle={e.description} />
                <div className="px-5 py-3 text-xs text-ink-500">Data: {e.data}</div>
                <div className="overflow-x-auto px-5 pb-4">
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs uppercase tracking-wide text-ink-500"><tr><th className="py-2 font-medium">Metric</th><th className="py-2 font-medium">Proposed</th>{e.baseline && <th className="py-2 font-medium">Baseline</th>}<th className="py-2 font-medium">n</th><th className="py-2 font-medium">Note</th></tr></thead>
                    <tbody className="divide-y divide-ink-100">
                      {e.metrics.map((m, i) => (
                        <tr key={m.name}>
                          <td className="py-2 text-ink-800">{m.name}</td>
                          <td className="py-2 font-semibold tabular-nums">{fmt(m.value)}</td>
                          {e.baseline && <td className="py-2 tabular-nums text-ink-600">{fmt(e.baseline[i]?.value)}</td>}
                          <td className="py-2 tabular-nums text-ink-500">{m.n ?? ''}</td>
                          <td className="py-2 text-xs text-ink-500">{m.note}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {e.limitations && <ul className="list-disc border-t border-ink-100 px-9 py-3 text-xs text-ink-600">{e.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return 'not measured';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(3);
  return String(v);
}
