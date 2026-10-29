import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Upload } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import { fmtDateTime, timeAgo } from '../../lib/format';
import { Badge, Button, Card, CardHeader, ErrorState, Field, Input, LoadingBlock, Notice, PageHeader, Select } from '../../components/ui';

export default function AdminData() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['admin', 'quality'], queryFn: api.admin.quality });
  const ds = useQuery({ queryKey: ['admin', 'datasets'], queryFn: api.admin.datasets });
  const [file, setFile] = useState<File | null>(null);
  const [version, setVersion] = useState('');
  const [name, setName] = useState('Replacement dataset');
  const [mode, setMode] = useState('review');
  const imp = useMutation({ mutationFn: () => api.admin.importDataset(file!, version, name, mode), onSuccess: () => qc.invalidateQueries({ queryKey: ['admin'] }) });

  return (
    <div>
      <PageHeader title="Data quality & datasets" subtitle="Duplicates, unresolved fields and stale records are computed from the current catalogue." />
      {q.isLoading ? <LoadingBlock /> : q.error ? <ErrorState error={q.error} /> : (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader title="Fields not recorded in structured form" subtitle="Each shows as 'needs source verification' to students." />
            <ul className="grid grid-cols-2 gap-3 p-5">
              {Object.entries(q.data!.unresolved_fields).map(([k, n]) => (
                <li key={k} className="rounded-lg bg-ink-50 p-3"><div className="text-xs text-ink-500">{k.replace(/_rule$/, '').replace(/_/g, ' ')}</div><div className="text-xl font-semibold tabular-nums">{n}</div></li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Possible duplicates" subtitle="Similar names without conflicting discriminators (e.g. degree vs diploma)." />
            {q.data!.duplicate_candidates.length === 0 ? <p className="px-5 py-4 text-sm text-ink-500">No likely duplicates found.</p> : (
              <ul className="divide-y divide-ink-100">
                {q.data!.duplicate_candidates.map((p) => (
                  <li key={p.a_id + p.b_id} className="px-5 py-3 text-sm">
                    <Link className="text-ink-800 hover:text-brand-700" to={`/scholarships/${p.a_id}`}>{p.a_name}</Link><span className="text-ink-400"> vs </span>
                    <Link className="text-ink-800 hover:text-brand-700" to={`/scholarships/${p.b_id}`}>{p.b_name}</Link>
                    <div className="text-xs text-ink-500">similarity {p.score.toFixed(2)}{p.url_match && ' · same source URL'}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <CardHeader title="Never checked by the monitor" subtitle="Values come only from the dataset import." />
            <ul className="max-h-72 divide-y divide-ink-100 overflow-auto">
              {q.data!.never_checked.map((s) => <li key={s.id} className="px-5 py-2.5 text-sm"><Link to={`/scholarships/${s.id}`} className="hover:text-brand-700">{s.name}</Link></li>)}
              {q.data!.never_checked.length === 0 && <li className="px-5 py-4 text-sm text-ink-500">Every record has been checked at least once.</li>}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Stale and conflicting" />
            <ul className="divide-y divide-ink-100">
              {q.data!.stale.map((s) => <li key={s.id} className="flex justify-between px-5 py-2.5 text-sm"><Link to={`/scholarships/${s.id}`} className="hover:text-brand-700">{s.name}</Link><Badge tone="amber">stale · {timeAgo(s.last_checked_at)}</Badge></li>)}
              {q.data!.conflicts.map((s) => <li key={s.id} className="flex justify-between px-5 py-2.5 text-sm"><Link to={`/scholarships/${s.id}`} className="hover:text-brand-700">{s.name}</Link><Badge tone="red">conflict</Badge></li>)}
              {q.data!.stale.length + q.data!.conflicts.length === 0 && <li className="px-5 py-4 text-sm text-ink-500">None.</li>}
            </ul>
          </Card>
        </div>
      )}

      <h2 className="mb-3 mt-10 text-lg font-semibold text-ink-900">Dataset imports</h2>
      <Card className="mb-5 p-5">
        <form onSubmit={(e: FormEvent) => { e.preventDefault(); if (file && version) imp.mutate(); }} className="grid gap-4 md:grid-cols-4">
          <Field label="CSV file" htmlFor="csv"><input id="csv" type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="block w-full text-sm" /></Field>
          <Field label="Version label" htmlFor="ver"><Input id="ver" required value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2027-28-v1" /></Field>
          <Field label="Dataset name" htmlFor="dsname"><Input id="dsname" value={name} onChange={(e) => setName(e.target.value)} /></Field>
          <Field label="Existing records" htmlFor="mode" hint="Review: differences become pending changes."><Select id="mode" value={mode} onChange={(e) => setMode(e.target.value)}><option value="review">Queue changes for review</option><option value="apply">Apply changes (I reviewed the file)</option></Select></Field>
          <div className="md:col-span-4"><Button type="submit" disabled={!file || !version} loading={imp.isPending}><Upload className="h-4 w-4" />Import</Button></div>
        </form>
        {imp.error && <Notice tone="red" className="mt-3">{errorMessage(imp.error)}</Notice>}
        {imp.data && <Notice tone="green" className="mt-3">Imported: {JSON.stringify(imp.data)}</Notice>}
      </Card>
      {ds.data?.map((d) => (
        <Card key={d.id} className="mb-3 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div><span className="font-medium text-ink-900">{d.version}</span> <span className="text-sm text-ink-500">· {d.dataset_name} · {d.file_name}</span></div>
            <span className="text-xs text-ink-500">{fmtDateTime(d.imported_at)}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <Badge>{d.rows} rows</Badge><Badge tone="green">{d.created} created</Badge><Badge tone="blue">{d.updated} updated</Badge><Badge>{d.unchanged} unchanged</Badge><Badge tone={d.rejected ? 'red' : 'neutral'}>{d.rejected} rejected</Badge>
            <Badge tone="amber">{d.report.rows_with_issues} rows with interpretation notes</Badge>
          </div>
          <details className="mt-3">
            <summary className="cursor-pointer text-xs font-medium text-brand-700">Row-level report</summary>
            <ul className="mt-2 max-h-80 space-y-1 overflow-auto text-xs">
              {d.report.rows.filter((r) => r.issues.length).map((r) => (
                <li key={r.line} className="rounded bg-ink-50 p-2"><span className="font-medium">{r.external_id ?? `line ${r.line}`}</span> ({r.status}): {r.issues.join('; ')}</li>
              ))}
            </ul>
            <p className="mt-2 font-mono text-[10px] text-ink-400">sha256 {d.file_sha256}</p>
          </details>
        </Card>
      ))}
    </div>
  );
}
