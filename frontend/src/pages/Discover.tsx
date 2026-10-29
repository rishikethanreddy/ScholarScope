import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search, SlidersHorizontal, X } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { fmtDate, timeAgo } from '../lib/format';
import type { Scholarship } from '../lib/types';
import { Container } from '../components/Layout';
import { Button, Card, EmptyState, ErrorState, Input, LoadingBlock, PageHeader, Select } from '../components/ui';
import { AvailabilityBadge, OutcomeBadge, TrustBadge } from '../components/status';

const FILTERS = ['q', 'education_level', 'availability', 'verification_status', 'provider_type', 'state', 'outcome', 'sort'] as const;

export default function Discover() {
  const [params, setParams] = useSearchParams();
  const { user } = useAuth();
  const vocab = useQuery({ queryKey: ['vocab'], queryFn: api.vocabulary, staleTime: Infinity });
  const query = Object.fromEntries(FILTERS.filter((k) => k !== 'outcome').map((k) => [k, params.get(k) || undefined]));
  const listQ = useQuery({ queryKey: ['scholarships', query], queryFn: () => api.scholarships(query) });
  const personal = user?.role === 'student' && user.has_profile;
  const recQ = useQuery({ queryKey: ['recommendations'], queryFn: api.recommendations, enabled: !!personal });
  const outcomeFor = useMemo(() => new Map(recQ.data?.results.map((r) => [r.scholarship_id, r]) ?? []), [recQ.data]);

  const set = (k: string, v: string) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const outcome = params.get('outcome');
  let items: Scholarship[] = listQ.data?.items ?? [];
  if (outcome && personal) items = items.filter((s) => outcomeFor.get(s.id)?.outcome === outcome);
  const active = FILTERS.filter((k) => k !== 'sort' && params.get(k)).length;

  return (
    <Container>
      <PageHeader title="Discover scholarships" subtitle="Every record shows where its deadline comes from and when it was last checked against a source." />
      <Card className="mb-5 p-4">
        <div className="flex flex-col gap-3 lg:flex-row">
          <label className="relative flex-1">
            <span className="sr-only">Search</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-400" aria-hidden />
            <Input placeholder="Search by name, provider or description" className="pl-9" defaultValue={params.get('q') ?? ''}
              onChange={(e) => set('q', e.target.value)} maxLength={100} />
          </label>
          <Select aria-label="Sort" className="lg:w-44" value={params.get('sort') ?? 'deadline'} onChange={(e) => set('sort', e.target.value)}>
            <option value="deadline">Sort: deadline</option><option value="amount">Sort: award amount</option>
            <option value="name">Sort: name</option><option value="recent">Sort: recently updated</option>
          </Select>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Select aria-label="Education level" value={params.get('education_level') ?? ''} onChange={(e) => set('education_level', e.target.value)}>
            <option value="">Any level</option>
            {vocab.data?.education_levels.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}
          </Select>
          <Select aria-label="Availability" value={params.get('availability') ?? ''} onChange={(e) => set('availability', e.target.value)}>
            <option value="">Any status</option><option value="open">Open</option><option value="upcoming">Opens soon</option>
            <option value="closed">Closed</option><option value="unknown">Deadline unknown</option>
          </Select>
          <Select aria-label="Verification" value={params.get('verification_status') ?? ''} onChange={(e) => set('verification_status', e.target.value)}>
            <option value="">Any verification</option>
            {vocab.data && Object.entries(vocab.data.trust_statuses).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </Select>
          <Select aria-label="Provider type" value={params.get('provider_type') ?? ''} onChange={(e) => set('provider_type', e.target.value)}>
            <option value="">Any provider</option><option value="government">Government</option>
            <option value="private_foundation">Private foundation</option><option value="corporate">Corporate</option><option value="institution">Institution</option>
          </Select>
          <Select aria-label="State" value={params.get('state') ?? ''} onChange={(e) => set('state', e.target.value)}>
            <option value="">Any state</option>
            {vocab.data?.states.map((s) => <option key={s} value={s}>{s}</option>)}
          </Select>
          <Select aria-label="My eligibility" value={outcome ?? ''} disabled={!personal} title={personal ? undefined : 'Sign in with a profile to filter by eligibility'} onChange={(e) => set('outcome', e.target.value)}>
            <option value="">{personal ? 'Any eligibility' : 'Eligibility (sign in)'}</option>
            <option value="eligible">Eligible</option><option value="eligible_pending_verification">Meets recorded rules</option>
            <option value="potential_match">Potential match</option><option value="not_eligible">Not eligible</option>
          </Select>
        </div>
        {active > 0 && (
          <div className="mt-3 flex items-center gap-2 text-xs text-ink-500">
            <SlidersHorizontal className="h-3.5 w-3.5" aria-hidden />{active} filter{active > 1 ? 's' : ''} active
            <Button size="sm" variant="ghost" onClick={() => setParams(new URLSearchParams(), { replace: true })}><X className="h-3.5 w-3.5" />Clear</Button>
          </div>
        )}
      </Card>

      {listQ.isLoading ? <LoadingBlock rows={5} /> : listQ.error ? <ErrorState error={listQ.error} onRetry={() => listQ.refetch()} /> : items.length === 0 ? (
        <EmptyState title="No scholarships match these filters">Try removing a filter. Coverage is limited to registered sources and the imported dataset.</EmptyState>
      ) : (
        <>
          <p className="mb-3 text-sm text-ink-500" aria-live="polite">{items.length} scholarship{items.length === 1 ? '' : 's'}</p>
          <ul className="space-y-3">
            {items.map((s) => {
              const r = outcomeFor.get(s.id);
              return (
                <li key={s.id}>
                  <Card className="p-4 transition-shadow hover:shadow-md sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <Link to={`/scholarships/${s.id}`} className="text-[15px] font-semibold text-ink-900 hover:text-brand-700">{s.name}</Link>
                        <div className="mt-0.5 text-sm text-ink-500">{s.provider}</div>
                      </div>
                      <div className="text-right text-sm">
                        <div className="font-medium text-ink-900">{s.amount_text ?? 'Amount not stated'}</div>
                        <div className="text-xs text-ink-500">{s.amount_frequency}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {r && <OutcomeBadge outcome={r.outcome} />}
                      <AvailabilityBadge a={s.availability} deadline={s.deadline} />
                      <TrustBadge status={s.verification_status} />
                      {s.origin === 'crawler' && <span className="rounded-full bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 ring-1 ring-violet-200">Discovered by monitor</span>}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-500">
                      <span>Deadline {fmtDate(s.deadline)}</span>
                      <span>Last checked {s.last_checked_at ? timeAgo(s.last_checked_at) : 'never (dataset only)'}</span>
                      <span>Last verified {s.last_verified_at ? timeAgo(s.last_verified_at) : 'never'}</span>
                    </div>
                  </Card>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </Container>
  );
}
