import { useId, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react';
import { AlertTriangle, Inbox, Loader2, RefreshCw } from 'lucide-react';
import { Link } from 'react-router-dom';
import { errorMessage } from '../lib/api';

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');
export { cx };

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'subtle';
const VARIANTS: Record<Variant, string> = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-sm shadow-brand-600/20',
  secondary: 'bg-white text-ink-800 border border-ink-200 hover:bg-ink-50 hover:border-ink-300',
  ghost: 'text-ink-600 hover:bg-ink-100 hover:text-ink-900',
  danger: 'bg-rose-600 text-white hover:bg-rose-700',
  subtle: 'bg-brand-50 text-brand-700 hover:bg-brand-100',
};

export function Button({ variant = 'primary', size = 'md', loading, className, children, disabled, ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: 'sm' | 'md' | 'lg'; loading?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
        size === 'sm' ? 'h-8 px-3 text-sm' : size === 'lg' ? 'h-12 px-6 text-base' : 'h-10 px-4 text-sm',
        VARIANTS[variant], className)}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function ButtonLink({ to, variant = 'primary', size = 'md', className, children }:
  { to: string; variant?: Variant; size?: 'sm' | 'md' | 'lg'; className?: string; children: ReactNode }) {
  return (
    <Link to={to} className={cx(
      'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors',
      size === 'sm' ? 'h-8 px-3 text-sm' : size === 'lg' ? 'h-12 px-6 text-base' : 'h-10 px-4 text-sm',
      VARIANTS[variant], className)}>
      {children}
    </Link>
  );
}

type Tone = 'neutral' | 'green' | 'amber' | 'red' | 'blue' | 'violet' | 'slate';
const TONES: Record<Tone, string> = {
  neutral: 'bg-ink-100 text-ink-700 ring-ink-200',
  green: 'bg-emerald-50 text-emerald-800 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-rose-50 text-rose-800 ring-rose-200',
  blue: 'bg-brand-50 text-brand-800 ring-brand-200',
  violet: 'bg-violet-50 text-violet-800 ring-violet-200',
  slate: 'bg-slate-800 text-white ring-slate-800',
};

export function Badge({ tone = 'neutral', icon, children, className, title }: { tone?: Tone; icon?: ReactNode; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={cx('inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap', TONES[tone], className)}>
      {icon}
      {children}
    </span>
  );
}

export function Card({ children, className, as: As = 'div' }: { children: ReactNode; className?: string; as?: 'div' | 'section' | 'article' }) {
  return <As className={cx('rounded-2xl border border-ink-200/80 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.04)]', className)}>{children}</As>;
}

export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-ink-100 px-5 py-4">
      <div className="flex items-start gap-3 min-w-0">
        {icon && <div className="mt-0.5 text-ink-400">{icon}</div>}
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold text-ink-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-brand-600">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight text-ink-900 sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-500 sm:text-[15px]">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'default' | 'green' | 'amber' | 'red' }) {
  const color = tone === 'green' ? 'text-emerald-700' : tone === 'amber' ? 'text-amber-700' : tone === 'red' ? 'text-rose-700' : 'text-ink-900';
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-500">{label}</div>
      <div className={cx('mt-1.5 text-2xl font-semibold tabular-nums', color)}>{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-500">{hint}</div>}
    </Card>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton', className)} aria-hidden />;
}

export function LoadingBlock({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => <Skeleton key={i} className="h-20 w-full" />)}
    </div>
  );
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-200 bg-white px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-ink-100 p-3 text-ink-500">{icon ?? <Inbox className="h-5 w-5" />}</div>
      <h3 className="font-semibold text-ink-900">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm text-ink-500">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Something went wrong' }: { error: unknown; onRetry?: () => void; title?: string }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900">
      <AlertTriangle className="mt-0.5 h-5 w-5 flex-none text-rose-500" aria-hidden />
      <div className="flex-1">
        <div className="font-semibold">{title}</div>
        <div className="mt-0.5 text-rose-800">{errorMessage(error)}</div>
      </div>
      {onRetry && <Button variant="secondary" size="sm" onClick={onRetry}><RefreshCw className="h-3.5 w-3.5" />Retry</Button>}
    </div>
  );
}

export function Notice({ tone = 'blue', icon, children, className }: { tone?: 'blue' | 'amber' | 'green' | 'red' | 'neutral'; icon?: ReactNode; children: ReactNode; className?: string }) {
  const map = {
    blue: 'border-brand-200 bg-brand-50 text-brand-900',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    red: 'border-rose-200 bg-rose-50 text-rose-900',
    neutral: 'border-ink-200 bg-ink-50 text-ink-700',
  };
  return <div className={cx('flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm', map[tone], className)}>{icon && <span className="mt-0.5 flex-none">{icon}</span>}<div className="min-w-0 flex-1">{children}</div></div>;
}

export function Field({ label, hint, error, children, htmlFor, optional }: { label: string; hint?: ReactNode; error?: string; children: ReactNode; htmlFor?: string; optional?: boolean }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1.5 flex items-center gap-2 text-sm font-medium text-ink-800">
        {label}
        {optional && <span className="text-xs font-normal text-ink-400">optional</span>}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-ink-500">{hint}</p>}
      {error && <p className="mt-1 text-xs text-rose-600" role="alert">{error}</p>}
    </div>
  );
}

const inputCls = 'block w-full rounded-lg border border-ink-200 bg-white px-3 py-2 text-sm text-ink-900 shadow-sm placeholder:text-ink-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-ink-50';

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputCls, props.className)} />;
}

export function Select({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputCls, 'pr-8', props.className)}>{children}</select>;
}

export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(inputCls, 'min-h-24', props.className)} />;
}

export function Tabs<T extends string>({ tabs, value, onChange, label }: { tabs: { id: T; label: ReactNode; count?: number }[]; value: T; onChange: (v: T) => void; label: string }) {
  const id = useId();
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 overflow-x-auto border-b border-ink-200">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          id={`${id}-${t.id}`}
          aria-selected={value === t.id}
          tabIndex={value === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          onKeyDown={(e) => {
            const i = tabs.findIndex((x) => x.id === value);
            if (e.key === 'ArrowRight') onChange(tabs[(i + 1) % tabs.length].id);
            if (e.key === 'ArrowLeft') onChange(tabs[(i - 1 + tabs.length) % tabs.length].id);
          }}
          className={cx(
            '-mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors',
            value === t.id ? 'border-brand-600 text-brand-700' : 'border-transparent text-ink-500 hover:text-ink-800')}
        >
          {t.label}
          {t.count !== undefined && <span className={cx('rounded-full px-1.5 text-xs tabular-nums', value === t.id ? 'bg-brand-100 text-brand-700' : 'bg-ink-100 text-ink-600')}>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Disclosure({ summary, children, defaultOpen = false }: { summary: ReactNode; children: ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div>
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className="text-xs font-medium text-brand-700 hover:underline">
        {summary}
      </button>
      {open && <div id={id} className="mt-2">{children}</div>}
    </div>
  );
}

export function ExternalA({ href, children, className }: { href: string | null | undefined; children: ReactNode; className?: string }) {
  if (!href) return <span className={className}>{children}</span>;
  const safe = /^https?:\/\//i.test(href) ? href : undefined; // never render javascript: or other schemes
  if (!safe) return <span className={className}>{children}</span>;
  return <a href={safe} target="_blank" rel="noopener noreferrer" className={cx('text-brand-700 hover:underline break-words', className)}>{children}</a>;
}
