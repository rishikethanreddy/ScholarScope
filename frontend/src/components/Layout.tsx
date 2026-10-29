import { useState, type ReactNode } from 'react';
import { Link, NavLink, Navigate, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Activity, Bookmark, ClipboardCheck, Database, FileSearch, FlaskConical, GaugeCircle, History, LayoutDashboard, LogOut, Menu, Radar, Search, ShieldCheck, Telescope, User, X } from 'lucide-react';
import { useAuth } from '../lib/auth';
import { api } from '../lib/api';
import { cx } from './ui';

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-md focus-visible:outline-2">
      <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-white shadow-sm"><Telescope className="h-4.5 w-4.5" aria-hidden /></span>
      <span className="font-display text-lg font-semibold tracking-tight text-ink-900">ScholarScope</span>
    </Link>
  );
}

const navCls = ({ isActive }: { isActive: boolean }) =>
  cx('flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors', isActive ? 'bg-brand-50 text-brand-700' : 'text-ink-600 hover:bg-ink-100 hover:text-ink-900');

export function AppShell() {
  const { user, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const stats = useQuery({ queryKey: ['public-stats'], queryFn: api.publicStats, staleTime: 60_000 });
  const links: { to: string; label: string; icon: ReactNode }[] = [
    { to: '/discover', label: 'Discover', icon: <Search className="h-4 w-4" /> },
    { to: '/changes', label: 'What changed', icon: <History className="h-4 w-4" /> },
  ];
  if (user?.role === 'student') {
    links.unshift({ to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard className="h-4 w-4" /> });
    links.push({ to: '/saved', label: 'Saved', icon: <Bookmark className="h-4 w-4" /> });
  }
  if (user?.role === 'admin') links.push({ to: '/admin', label: 'Operations', icon: <GaugeCircle className="h-4 w-4" /> });

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:shadow">Skip to content</a>
      {stats.data?.demo_mode && (
        <div className="bg-violet-700 px-4 py-1.5 text-center text-xs font-medium text-white">
          DEMO DATABASE: sources are local fixtures, clearly labelled. Nothing here is a live check.
        </div>
      )}
      <header className="sticky top-0 z-40 border-b border-ink-200/80 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex items-center gap-6">
            <Logo />
            <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
              {links.map((l) => <NavLink key={l.to} to={l.to} className={navCls}>{l.icon}{l.label}</NavLink>)}
            </nav>
          </div>
          <div className="hidden items-center gap-2 md:flex">
            {user ? (
              <>
                {user.role === 'student' && <NavLink to="/profile" className={navCls}><User className="h-4 w-4" />Profile</NavLink>}
                <span className="max-w-40 truncate text-xs text-ink-500" title={user.email}>{user.email}</span>
                <button onClick={signOut} className="rounded-lg p-2 text-ink-500 hover:bg-ink-100 hover:text-ink-900" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
              </>
            ) : (
              <>
                <Link to="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-ink-700 hover:bg-ink-100">Sign in</Link>
                <Link to="/register" className="rounded-lg bg-brand-600 px-3.5 py-2 text-sm font-medium text-white hover:bg-brand-700">Create account</Link>
              </>
            )}
          </div>
          <button className="rounded-lg p-2 text-ink-600 hover:bg-ink-100 md:hidden" aria-label={open ? 'Close menu' : 'Open menu'} aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open && (
          <nav className="space-y-1 border-t border-ink-100 px-4 py-3 md:hidden" aria-label="Mobile">
            {links.map((l) => <NavLink key={l.to} to={l.to} className={navCls} onClick={() => setOpen(false)}>{l.icon}{l.label}</NavLink>)}
            {user ? (
              <>
                {user.role === 'student' && <NavLink to="/profile" className={navCls} onClick={() => setOpen(false)}><User className="h-4 w-4" />Profile</NavLink>}
                <button onClick={() => { signOut(); setOpen(false); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-600 hover:bg-ink-100"><LogOut className="h-4 w-4" />Sign out</button>
              </>
            ) : (
              <>
                <NavLink to="/login" className={navCls} onClick={() => setOpen(false)}>Sign in</NavLink>
                <NavLink to="/register" className={navCls} onClick={() => setOpen(false)}>Create account</NavLink>
              </>
            )}
          </nav>
        )}
      </header>
      <main id="main" className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-ink-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-6 text-xs text-ink-500 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>ScholarScope AI is an academic project. Eligibility results are based on recorded criteria and are not official decisions.</p>
          <p>
            {stats.data ? <>Last successful source check: {stats.data.last_successful_check ? new Date(stats.data.last_successful_check).toLocaleString('en-IN') : 'none yet'}</> : null}
          </p>
        </div>
      </footer>
    </div>
  );
}

export function Container({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx('mx-auto max-w-7xl px-4 py-8 sm:px-6', className)}>{children}</div>;
}

export function RequireAuth({ role, children, needProfile }: { role?: 'student' | 'admin'; children: ReactNode; needProfile?: boolean }) {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Container><div className="skeleton h-40" /></Container>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname)}`} replace />;
  if (role && user.role !== role) return <Navigate to={user.role === 'admin' ? '/admin' : '/dashboard'} replace />;
  if (needProfile && user.role === 'student' && !user.has_profile) return <Navigate to="/profile?welcome=1" replace />;
  return <>{children}</>;
}

const adminLinks = [
  { to: '/admin', label: 'Overview', icon: Activity, end: true },
  { to: '/admin/sources', label: 'Sources', icon: Radar },
  { to: '/admin/jobs', label: 'Crawl jobs', icon: ClipboardCheck },
  { to: '/admin/review', label: 'Review queue', icon: FileSearch },
  { to: '/admin/changes', label: 'Changes', icon: History },
  { to: '/admin/data', label: 'Data quality', icon: Database },
  { to: '/admin/evaluation', label: 'Evaluation', icon: FlaskConical },
  { to: '/admin/audit', label: 'Audit log', icon: ShieldCheck },
];

export function AdminLayout() {
  return (
    <RequireAuth role="admin">
      <div className="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:flex-row">
        <aside className="lg:w-52 lg:flex-none">
          <nav className="flex gap-1 overflow-x-auto lg:flex-col" aria-label="Operations">
            {adminLinks.map(({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end} className={navCls}><Icon className="h-4 w-4" />{label}</NavLink>
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1"><Outlet /></div>
      </div>
    </RequireAuth>
  );
}
