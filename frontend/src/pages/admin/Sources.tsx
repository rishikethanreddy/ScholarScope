import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FlaskConical, Pause, Pencil, Play, Plus, RotateCcw } from 'lucide-react';
import { api, errorMessage } from '../../lib/api';
import type { Source } from '../../lib/types';
import { fmtDateTime, timeAgo } from '../../lib/format';
import { Badge, Button, Card, ErrorState, ExternalA, Field, Input, LoadingBlock, Notice, PageHeader, Select, Textarea } from '../../components/ui';
import { HealthBadge, SourceClassBadge } from '../../components/status';

export default function AdminSources() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ['admin', 'sources'], queryFn: api.admin.sources, refetchInterval: 10_000 });
  const [editing, setEditing] = useState<Source | 'new' | null>(null);
  const [message, setMessage] = useState<{ tone: 'green' | 'red'; text: string; jobId?: string } | null>(null);
  const [testResult, setTestResult] = useState<{ id: string; data: Record<string, unknown> } | null>(null);
  const done = () => qc.invalidateQueries({ queryKey: ['admin'] });
  const run = useMutation({ mutationFn: api.admin.checkSource, onSuccess: (j) => { setMessage({ tone: j.status === 'failed' ? 'red' : 'green', text: `Check ${j.status === 'queued' ? 'queued' : j.status}.`, jobId: j.id }); void done(); }, onError: (e) => setMessage({ tone: 'red', text: errorMessage(e) }) });
  const pause = useMutation({ mutationFn: (id: string) => api.admin.pauseSource(id, 'Paused by admin'), onSuccess: done });
  const resume = useMutation({ mutationFn: api.admin.resumeSource, onSuccess: done });
  const test = useMutation({ mutationFn: api.admin.testSource, onSuccess: (data, id) => setTestResult({ id, data }), onError: (e) => setMessage({ tone: 'red', text: errorMessage(e) }) });

  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div>
      <PageHeader title="Source registry" subtitle="Approved sources only. The crawler fetches nothing outside each source's allowed URL patterns, honours robots.txt, and never bypasses access controls."
        actions={<Button onClick={() => setEditing('new')}><Plus className="h-4 w-4" />Add source</Button>} />
      {message && <Notice tone={message.tone} className="mb-4">{message.text} {message.jobId && <Link className="font-medium underline" to={`/admin/jobs/${message.jobId}`}>View job</Link>}</Notice>}
      {editing && <SourceForm source={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); void done(); }} />}
      <div className="space-y-3">
        {q.data!.map((s) => (
          <Card key={s.id} className="p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink-900">{s.name}</span>
                  <SourceClassBadge c={s.classification} fixture={s.is_fixture} />
                  <HealthBadge h={s.enabled ? s.health_status : 'disabled'} />
                  <Badge>{s.connector}</Badge>
                </div>
                <div className="mt-1 text-xs text-ink-500">{s.organization} · key <code>{s.key}</code> · every {Math.round(s.crawl_frequency_minutes / 60)} h · priority {s.priority}</div>
                <div className="mt-1 text-xs"><ExternalA href={s.target_urls[0]}>{s.target_urls[0]}</ExternalA></div>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Button size="sm" variant="secondary" onClick={() => test.mutate(s.id)} loading={test.isPending && test.variables === s.id}><FlaskConical className="h-3.5 w-3.5" />Test</Button>
                <Button size="sm" onClick={() => run.mutate(s.id)} disabled={!s.enabled || s.health_status === 'paused'} loading={run.isPending && run.variables === s.id}><Play className="h-3.5 w-3.5" />Run check</Button>
                {s.health_status === 'paused'
                  ? <Button size="sm" variant="secondary" onClick={() => resume.mutate(s.id)}><RotateCcw className="h-3.5 w-3.5" />Resume</Button>
                  : <Button size="sm" variant="ghost" onClick={() => pause.mutate(s.id)}><Pause className="h-3.5 w-3.5" />Pause</Button>}
                <Button size="sm" variant="ghost" onClick={() => setEditing(s)} aria-label={`Edit ${s.name}`}><Pencil className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-4">
              <div><dt className="text-ink-400">Last attempt</dt><dd>{timeAgo(s.last_attempt_at)}</dd></div>
              <div><dt className="text-ink-400">Last success</dt><dd>{s.last_success_at ? fmtDateTime(s.last_success_at) : 'never'}</dd></div>
              <div><dt className="text-ink-400">Last content change</dt><dd>{s.last_change_at ? fmtDateTime(s.last_change_at) : '—'}</dd></div>
              <div><dt className="text-ink-400">Failures / HTTP</dt><dd>{s.consecutive_failures} · {s.last_http_status ?? '—'}</dd></div>
            </dl>
            {(s.paused_reason || (s.last_error && s.health_status !== 'healthy')) && <p className="mt-2 text-xs text-rose-700">{s.paused_reason ?? s.last_error}</p>}
            {s.access_notes && <p className="mt-2 text-xs text-ink-500"><span className="font-medium">Access notes:</span> {s.access_notes}</p>}
            {testResult?.id === s.id && (
              <div className="mt-3 rounded-lg bg-ink-50 p-3">
                <div className="mb-1 text-xs font-medium text-ink-700">Dry-run result (nothing stored)</div>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap text-[11px] text-ink-700">{JSON.stringify(testResult.data, null, 2)}</pre>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}

function SourceForm({ source, onClose, onSaved }: { source: Source | null; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({
    key: source?.key ?? '', name: source?.name ?? '', organization: source?.organization ?? '', classification: source?.classification ?? 'official',
    base_url: source?.base_url ?? 'https://', target_urls: (source?.target_urls ?? []).join('\n'), allowed_url_patterns: (source?.allowed_url_patterns ?? []).join('\n'),
    connector: source?.connector ?? 'html_page', crawl_frequency_minutes: source?.crawl_frequency_minutes ?? 1440, enabled: source?.enabled ?? true,
    priority: source?.priority ?? 50, trust_policy: source?.trust_policy ?? '', access_notes: source?.access_notes ?? '',
    auto_extract: Boolean(source?.connector_config?.auto_extract),
  });
  const lines = (s: string) => s.split('\n').map((x) => x.trim()).filter(Boolean);
  const m = useMutation({
    mutationFn: () => {
      const common = {
        name: f.name, organization: f.organization || null, classification: f.classification, target_urls: lines(f.target_urls),
        allowed_url_patterns: lines(f.allowed_url_patterns), crawl_frequency_minutes: Number(f.crawl_frequency_minutes), enabled: f.enabled,
        priority: Number(f.priority), trust_policy: f.trust_policy || null, access_notes: f.access_notes || null, connector_config: { auto_extract: f.auto_extract },
      };
      return source ? api.admin.updateSource(source.id, common) : api.admin.createSource({ ...common, key: f.key, base_url: f.base_url, connector: f.connector });
    },
    onSuccess: onSaved,
  });
  const set = (k: keyof typeof f, v: unknown) => setF((x) => ({ ...x, [k]: v }));
  return (
    <Card className="mb-5 p-5">
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); m.mutate(); }} className="grid gap-4 sm:grid-cols-2">
        <h2 className="font-semibold text-ink-900 sm:col-span-2">{source ? `Edit ${source.name}` : 'Register a new source'}</h2>
        {!source && <Field label="Key" htmlFor="key" hint="lowercase_with_underscores"><Input id="key" required value={f.key} onChange={(e) => set('key', e.target.value)} /></Field>}
        <Field label="Name" htmlFor="name"><Input id="name" required value={f.name} onChange={(e) => set('name', e.target.value)} /></Field>
        <Field label="Organization" htmlFor="org"><Input id="org" value={f.organization} onChange={(e) => set('organization', e.target.value)} /></Field>
        <Field label="Classification" htmlFor="cls"><Select id="cls" value={f.classification} onChange={(e) => set('classification', e.target.value)}>
          <option value="official">Official (scheme owner / government)</option><option value="institutional">Institutional</option><option value="aggregator">Aggregator (discovery only)</option><option value="other">Other</option><option value="fixture">Fixture (testing)</option>
        </Select></Field>
        {!source && <Field label="Connector" htmlFor="conn"><Select id="conn" value={f.connector} onChange={(e) => set('connector', e.target.value)}>
          <option value="html_page">HTML page monitor</option><option value="pdf_document">PDF document monitor</option><option value="nsp_listing">NSP scheme listing parser</option>
        </Select></Field>}
        {!source && <Field label="Base URL" htmlFor="base"><Input id="base" required value={f.base_url} onChange={(e) => set('base_url', e.target.value)} /></Field>}
        <Field label="Target URLs (one per line)" htmlFor="targets"><Textarea id="targets" required value={f.target_urls} onChange={(e) => set('target_urls', e.target.value)} /></Field>
        <Field label="Allowed URL patterns" htmlFor="patterns" hint="Glob patterns, e.g. https://example.gov.in/*. Redirects outside these are refused."><Textarea id="patterns" required value={f.allowed_url_patterns} onChange={(e) => set('allowed_url_patterns', e.target.value)} /></Field>
        <Field label="Check frequency (minutes)" htmlFor="freq"><Input id="freq" type="number" min={30} value={f.crawl_frequency_minutes} onChange={(e) => set('crawl_frequency_minutes', e.target.value)} /></Field>
        <Field label="Priority (0-100)" htmlFor="prio"><Input id="prio" type="number" min={0} max={100} value={f.priority} onChange={(e) => set('priority', e.target.value)} /></Field>
        <Field label="Trust policy" htmlFor="trust"><Textarea id="trust" value={f.trust_policy} onChange={(e) => set('trust_policy', e.target.value)} /></Field>
        <Field label="Access-policy notes" htmlFor="access"><Textarea id="access" value={f.access_notes} onChange={(e) => set('access_notes', e.target.value)} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={f.enabled} onChange={(e) => set('enabled', e.target.checked)} />Enabled</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={f.auto_extract} onChange={(e) => set('auto_extract', e.target.checked)} />Run AI extraction when content changes</label>
        {m.error && <Notice tone="red" className="sm:col-span-2">{errorMessage(m.error)}</Notice>}
        <div className="flex gap-2 sm:col-span-2"><Button type="submit" loading={m.isPending}>Save source</Button><Button type="button" variant="ghost" onClick={onClose}>Cancel</Button></div>
      </form>
    </Card>
  );
}
