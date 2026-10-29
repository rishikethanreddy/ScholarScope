import { AlertCircle, AlertTriangle, BadgeCheck, CalendarClock, CheckCircle2, CircleDashed, CircleHelp, Clock, FileQuestion, Lock, MinusCircle, ShieldAlert, ShieldCheck, ShieldQuestion, XCircle } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import type { Availability, CriterionStatus, Outcome } from '../lib/types';
import { api } from '../lib/api';
import { Badge } from './ui';
import { fmtDate } from '../lib/format';

const ic = 'h-3.5 w-3.5';

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  switch (outcome) {
    case 'eligible':
      return <Badge tone="green" icon={<CheckCircle2 className={ic} />}>Eligible (recorded criteria)</Badge>;
    case 'eligible_pending_verification':
      return <Badge tone="blue" icon={<ShieldQuestion className={ic} />}>Meets recorded criteria · verify</Badge>;
    case 'potential_match':
      return <Badge tone="amber" icon={<CircleHelp className={ic} />}>Potential match · info needed</Badge>;
    default:
      return <Badge tone="neutral" icon={<XCircle className={ic} />}>Not eligible</Badge>;
  }
}

export function AvailabilityBadge({ a, deadline }: { a: Availability; deadline?: string | null }) {
  if (a.state === 'closed') return <Badge tone="neutral" icon={<Lock className={ic} />}>Closed{deadline ? ` · ${fmtDate(deadline)}` : ''}</Badge>;
  if (a.state === 'upcoming') return <Badge tone="violet" icon={<CalendarClock className={ic} />}>Opens soon</Badge>;
  if (a.state === 'unknown') return <Badge tone="neutral" icon={<CircleDashed className={ic} />}>Deadline unknown</Badge>;
  if (a.deadline_approaching) return <Badge tone="red" icon={<Clock className={ic} />}>{a.days_left === 0 ? 'Closes today' : `${a.days_left} days left`}</Badge>;
  return <Badge tone="green" icon={<CalendarClock className={ic} />}>Open{deadline ? ` · until ${fmtDate(deadline)}` : ''}</Badge>;
}

const TRUST: Record<string, { tone: 'green' | 'blue' | 'amber' | 'red' | 'neutral'; icon: typeof ShieldCheck; label: string }> = {
  official_source_confirmed: { tone: 'green', icon: BadgeCheck, label: 'Official source confirmed' },
  official_source_checked: { tone: 'blue', icon: ShieldCheck, label: 'Official source checked' },
  aggregator_only: { tone: 'neutral', icon: FileQuestion, label: 'Dataset only' },
  needs_review: { tone: 'amber', icon: AlertCircle, label: 'Needs review' },
  conflicting_sources: { tone: 'red', icon: ShieldAlert, label: 'Conflicting sources' },
  stale_observation: { tone: 'amber', icon: Clock, label: 'Stale observation' },
  source_unavailable: { tone: 'red', icon: AlertTriangle, label: 'Source unavailable' },
  deadline_not_verified: { tone: 'neutral', icon: ShieldQuestion, label: 'Deadline not verified' },
};

export const TRUST_HELP: Record<string, string> = {
  official_source_confirmed: 'The latest successful check of an official source re-observed this deadline.',
  official_source_checked: 'An official source for this scheme was checked, but it did not state the current deadline.',
  aggregator_only: 'Only curated-dataset evidence exists. No official source has been checked by this system.',
  needs_review: 'A material change detected by the monitor is waiting for an administrator to review it.',
  conflicting_sources: 'Two current official observations disagree. Check the evidence before relying on this record.',
  stale_observation: 'The last successful check is older than the freshness policy allows for this record.',
  source_unavailable: 'The official source(s) for this record are currently failing or paused.',
  deadline_not_verified: 'The deadline comes only from the imported dataset and has not been observed by the monitor.',
};

export function TrustBadge({ status }: { status: string }) {
  // In the offline demo every "official" observation comes from a local fixture: say so on the badge itself.
  const stats = useQuery({ queryKey: ['public-stats'], queryFn: api.publicStats, staleTime: 60_000 });
  const t = TRUST[status] ?? { tone: 'neutral' as const, icon: ShieldQuestion, label: status };
  const Icon = t.icon;
  const fixture = stats.data?.demo_mode && status.startsWith('official');
  return <Badge tone={fixture ? 'violet' : t.tone} icon={<Icon className={ic} />} title={TRUST_HELP[status]}>{t.label}{fixture ? ' (fixture)' : ''}</Badge>;
}

export function CriterionIcon({ status, reason }: { status: CriterionStatus; reason?: string | null }) {
  if (status === 'satisfied') return <CheckCircle2 className="h-5 w-5 text-emerald-600" aria-label="Satisfied" />;
  if (status === 'not_satisfied') return <XCircle className="h-5 w-5 text-rose-600" aria-label="Not satisfied" />;
  if (status === 'not_applicable') return <MinusCircle className="h-5 w-5 text-ink-300" aria-label="Not applicable" />;
  if (reason === 'scholarship_unresolved') return <ShieldQuestion className="h-5 w-5 text-brand-500" aria-label="Needs source verification" />;
  return <CircleHelp className="h-5 w-5 text-amber-500" aria-label="Unknown" />;
}

export function SourceClassBadge({ c, fixture }: { c: string; fixture?: boolean }) {
  if (fixture || c === 'fixture') return <Badge tone="violet">Local fixture (not live)</Badge>;
  if (c === 'official') return <Badge tone="green">Official</Badge>;
  if (c === 'curated_dataset') return <Badge tone="neutral">Curated dataset</Badge>;
  if (c === 'manual') return <Badge tone="blue">Admin entry</Badge>;
  if (c === 'aggregator') return <Badge tone="amber">Aggregator</Badge>;
  return <Badge>{c}</Badge>;
}

export function HealthBadge({ h }: { h: string }) {
  const tone = h === 'healthy' ? 'green' : h === 'degraded' ? 'amber' : h === 'failing' || h === 'paused' ? 'red' : 'neutral';
  return <Badge tone={tone}>{h}</Badge>;
}

export function JobStatusBadge({ s }: { s: string }) {
  const tone = s === 'succeeded' ? 'green' : s === 'failed' ? 'red' : s === 'running' || s === 'queued' ? 'blue' : 'neutral';
  return <Badge tone={tone}>{s}</Badge>;
}
