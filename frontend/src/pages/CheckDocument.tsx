import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { FileUp, Sparkles } from 'lucide-react';
import { api, errorMessage } from '../lib/api';
import type { Criterion, Outcome } from '../lib/types';
import { fieldLabel, fmtValue } from '../lib/format';
import { Container } from '../components/Layout';
import { Button, Card, CardHeader, Notice, PageHeader } from '../components/ui';
import { CriterionIcon, OutcomeBadge } from '../components/status';

interface CheckResult {
  label: string;
  extracted: Record<string, unknown>;
  evidence: Record<string, { snippet: string; location: string | null }>;
  validation: { errors: string[]; warnings: string[]; unsupported: { field: string; value: unknown; reason: string }[] };
  criteria: Criterion[];
  outcome: Outcome;
  outcome_label: string;
  provider: string;
  model: string;
}

export default function CheckDocument() {
  const [file, setFile] = useState<File | null>(null);
  const stats = useQuery({ queryKey: ['public-stats'], queryFn: api.publicStats });
  const m = useMutation<CheckResult, unknown, File>({ mutationFn: (f) => api.checkDocument(f) });
  const configured = stats.data?.llm.configured;

  return (
    <Container className="max-w-4xl">
      <PageHeader title="Check a scholarship PDF" subtitle="Upload a scholarship notice or guideline you found elsewhere. AI extracts its rules (every value must quote the PDF), then your profile is checked against them. Nothing is stored." />
      {configured === false && <Notice tone="amber" className="mb-4">AI extraction is not configured on this server, so this check cannot run. No placeholder result will be shown.</Notice>}
      <Card className="p-5">
        <form onSubmit={(e) => { e.preventDefault(); if (file) m.mutate(file); }} className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label className="flex-1">
            <span className="sr-only">PDF file</span>
            <input type="file" accept="application/pdf,.pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-ink-600 file:mr-3 file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-2 file:text-sm file:font-medium file:text-brand-700 hover:file:bg-brand-100" />
          </label>
          <Button type="submit" disabled={!file || configured === false} loading={m.isPending}><FileUp className="h-4 w-4" />Analyse</Button>
        </form>
        <p className="mt-2 text-xs text-ink-500">PDF only, up to 10 MB. Do not upload personal documents such as certificates or ID cards.</p>
      </Card>
      {m.error != null && <Notice tone="red" className="mt-4">{errorMessage(m.error)}</Notice>}
      {m.data && (
        <div className="mt-6 space-y-6">
          <Notice tone="amber" icon={<Sparkles className="h-4 w-4" />}>{m.data.label} Model: {m.data.provider}/{m.data.model}.</Notice>
          <Card>
            <CardHeader title={<span className="flex flex-wrap items-center gap-2">Result <OutcomeBadge outcome={m.data.outcome} /></span>} subtitle={m.data.outcome_label} />
            <ul className="divide-y divide-ink-100 px-5">
              {m.data.criteria.map((c) => (
                <li key={c.key} className="flex gap-3 py-3">
                  <CriterionIcon status={c.status} reason={c.unknown_reason} />
                  <div><div className="text-sm font-medium text-ink-900">{c.label}</div><div className="text-sm text-ink-600">{c.explanation}</div></div>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Extracted values and their quotes" />
            <dl className="divide-y divide-ink-100">
              {Object.entries(m.data.extracted).filter(([k]) => !['normalized_name', 'official_source_url'].includes(k)).map(([k, v]) => (
                <div key={k} className="grid gap-1 px-5 py-3 sm:grid-cols-[11rem_1fr]">
                  <dt className="text-xs font-medium text-ink-500">{fieldLabel(k)}</dt>
                  <dd className="text-sm text-ink-800">{fmtValue(v)}{m.data!.evidence[k] && <q className="mt-1 block text-xs text-ink-500">{m.data!.evidence[k].snippet}</q>}</dd>
                </div>
              ))}
            </dl>
            {m.data.validation.unsupported.length > 0 && (
              <div className="border-t border-ink-100 px-5 py-3 text-xs text-ink-600">
                <div className="font-medium text-ink-800">Discarded (no verifiable quote or failed checks):</div>
                <ul className="mt-1 list-disc pl-5">{m.data.validation.unsupported.map((u, i) => <li key={i}>{fieldLabel(u.field)}: {u.reason}</li>)}</ul>
              </div>
            )}
          </Card>
        </div>
      )}
    </Container>
  );
}
