import { motion } from 'framer-motion';
import { useQuery } from '@tanstack/react-query';
import { ArrowRight, BadgeCheck, CircleHelp, History, Radar, ScanSearch, ShieldCheck } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { timeAgo } from '../lib/format';
import { ButtonLink, Card, Skeleton } from '../components/ui';

const fade = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } };

export default function Landing() {
  const { user } = useAuth();
  const stats = useQuery({ queryKey: ['public-stats'], queryFn: api.publicStats });
  const primary = user ? (user.role === 'admin' ? '/admin' : '/dashboard') : '/register';
  const s = stats.data;
  const confirmed = s?.by_verification_status?.official_source_confirmed ?? 0;

  return (
    <div>
      <section className="relative overflow-hidden border-b border-ink-200 bg-white">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60rem_30rem_at_80%_-10%,var(--color-brand-50),transparent)]" aria-hidden />
        <div className="relative mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:py-24">
          <motion.div {...fade} transition={{ duration: 0.4 }}>
            <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">
              <Radar className="h-3.5 w-3.5" aria-hidden /> Monitors official scholarship sources on a schedule
            </p>
            <h1 className="font-display text-4xl font-semibold leading-[1.1] tracking-tight text-ink-900 sm:text-5xl">
              Scholarships you qualify for, with proof of where every fact came from.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink-600">
              ScholarScope checks your profile against each scheme's recorded rules, tells you exactly which criteria you meet, which are
              missing, and shows the official source, the quoted evidence and when it was last checked.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <ButtonLink to={primary} size="lg">{user ? 'Go to my dashboard' : 'Check my eligibility'}<ArrowRight className="h-4 w-4" /></ButtonLink>
              <ButtonLink to="/discover" size="lg" variant="secondary">Browse the catalogue</ButtonLink>
            </div>
            <p className="mt-4 text-xs text-ink-500">No identity numbers or documents required. Results are guidance based on recorded criteria, not an official decision.</p>
          </motion.div>

          <motion.div {...fade} transition={{ duration: 0.4, delay: 0.1 }}>
            <Card className="p-6">
              <h2 className="text-sm font-semibold text-ink-900">Live catalogue status</h2>
              <p className="mt-0.5 text-xs text-ink-500">Computed from the database right now.</p>
              {stats.isLoading ? (
                <div className="mt-5 space-y-3"><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
              ) : s ? (
                <dl className="mt-5 grid grid-cols-2 gap-4">
                  <div className="rounded-xl bg-ink-50 p-4"><dt className="text-xs text-ink-500">Published scholarships</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{s.published_scholarships}</dd></div>
                  <div className="rounded-xl bg-emerald-50 p-4"><dt className="text-xs text-emerald-800">Deadline confirmed on an official source</dt><dd className="mt-1 text-2xl font-semibold tabular-nums text-emerald-800">{confirmed}</dd></div>
                  <div className="rounded-xl bg-ink-50 p-4"><dt className="text-xs text-ink-500">Sources monitored</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{s.enabled_sources}</dd></div>
                  <div className="rounded-xl bg-ink-50 p-4"><dt className="text-xs text-ink-500">Material changes (7 days)</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{s.material_changes_last_7_days}</dd></div>
                  <div className="col-span-2 rounded-xl border border-ink-200 p-3 text-xs text-ink-600">
                    Last successful source check: <span className="font-medium text-ink-900">{s.last_successful_check ? timeAgo(s.last_successful_check) : 'none yet'}</span>.
                    Monitoring is only as current as the last successful check.
                  </div>
                </dl>
              ) : (
                <p className="mt-5 text-sm text-rose-700">The API is not reachable right now.</p>
              )}
            </Card>
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-16 sm:px-6">
        <h2 className="text-2xl font-semibold tracking-tight text-ink-900">What makes it different</h2>
        <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: CircleHelp, title: 'Unknown is never "eligible"', body: 'Each rule is satisfied, not satisfied, or unknown. Missing information is shown as a question, not silently passed.' },
            { icon: BadgeCheck, title: 'Field-level evidence', body: 'Deadlines and rules link to the quoted text, the source, the extraction method and the retrieval time.' },
            { icon: History, title: 'Change history', body: 'When a source revises a deadline, the old value is kept and the change is shown with its evidence.' },
            { icon: ShieldCheck, title: 'Honest freshness', body: '"Last checked" and "last verified" are separate. Failed or blocked sources are shown as unavailable.' },
          ].map(({ icon: Icon, title, body }) => (
            <Card key={title} className="p-5">
              <Icon className="h-5 w-5 text-brand-600" aria-hidden />
              <h3 className="mt-3 font-semibold text-ink-900">{title}</h3>
              <p className="mt-1.5 text-sm text-ink-600">{body}</p>
            </Card>
          ))}
        </div>
        <div className="mt-10 flex flex-wrap items-center gap-3 rounded-2xl border border-ink-200 bg-white p-5">
          <ScanSearch className="h-5 w-5 text-ink-500" aria-hidden />
          <p className="flex-1 text-sm text-ink-600">Coverage is limited to the registered sources and the imported dataset. It does not cover every scholarship on the internet.</p>
          <ButtonLink to="/changes" variant="secondary" size="sm">See what changed recently</ButtonLink>
        </div>
      </section>
    </div>
  );
}
