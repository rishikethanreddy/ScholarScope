import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { errorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Button, Card, Field, Input, Notice } from '../components/ui';

function AuthCard({ title, subtitle, children }: { title: string; subtitle: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col px-4 py-16">
      <Card className="p-7">
        <h1 className="text-xl font-semibold text-ink-900">{title}</h1>
        <p className="mt-1 text-sm text-ink-500">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </Card>
    </div>
  );
}

function safeNext(next: string | null): string | null {
  return next && next.startsWith('/') && !next.startsWith('//') ? next : null;
}

export function Login() {
  const { signIn } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const u = await signIn(email, password);
      nav(safeNext(params.get('next')) ?? (u.role === 'admin' ? '/admin' : u.has_profile ? '/dashboard' : '/profile?welcome=1'));
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Sign in" subtitle="Welcome back to ScholarScope.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {err && <Notice tone="red">{err}</Notice>}
        <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password" htmlFor="password"><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <Button type="submit" className="w-full" loading={busy}>Sign in</Button>
        <p className="text-center text-sm text-ink-500">New here? <Link to="/register" className="font-medium text-brand-700 hover:underline">Create an account</Link></p>
      </form>
    </AuthCard>
  );
}

export function Register() {
  const { signUp } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < 10) return setErr('Use at least 10 characters for your password.');
    setBusy(true);
    setErr(null);
    try {
      await signUp(email, password);
      nav('/profile?welcome=1');
    } catch (e2) {
      setErr(errorMessage(e2));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthCard title="Create your account" subtitle="Only an email and password. Your profile holds just the details eligibility rules need.">
      <form onSubmit={submit} className="space-y-4" noValidate>
        {err && <Notice tone="red">{err}</Notice>}
        <Field label="Email" htmlFor="email"><Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <Field label="Password" htmlFor="password" hint="At least 10 characters."><Input id="password" type="password" autoComplete="new-password" required minLength={10} value={password} onChange={(e) => setPassword(e.target.value)} /></Field>
        <Button type="submit" className="w-full" loading={busy}>Create account</Button>
        <p className="text-center text-sm text-ink-500">Already registered? <Link to="/login" className="font-medium text-brand-700 hover:underline">Sign in</Link></p>
      </form>
    </AuthCard>
  );
}
