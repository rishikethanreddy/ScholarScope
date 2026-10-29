import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Lock, Save, Trash2 } from 'lucide-react';
import { api, errorMessage } from '../lib/api';
import { useAuth } from '../lib/auth';
import type { Profile, Vocabulary } from '../lib/types';
import { Container } from '../components/Layout';
import { Button, Card, ErrorState, Field, Input, LoadingBlock, Notice, PageHeader, Select } from '../components/ui';

const EMPTY: Profile = {
  display_name: null, education_level: null, current_class: null, year_of_study: null, course_name: null, discipline: null,
  qualifying_exam_percentage: null, cgpa: null, cgpa_scale: 10, annual_family_income: null, state: null, gender: null,
  category: null, has_disability: null, disability_percent: null, is_indian_citizen: null, special_circumstances: [],
  special_circumstances_none: false,
};

const num = (v: string): number | null => (v.trim() === '' ? null : Number(v));
const triToStr = (b: boolean | null) => (b === null ? '' : b ? 'yes' : 'no');
const strToTri = (s: string): boolean | null => (s === '' ? null : s === 'yes');

function Section({ id, title, desc, children }: { id: string; title: string; desc: string; children: ReactNode }) {
  return (
    <Card as="section" className="p-5 sm:p-6">
      <h2 id={id} className="text-base font-semibold text-ink-900">{title}</h2>
      <p className="mt-0.5 text-sm text-ink-500">{desc}</p>
      <div className="mt-5 grid gap-5 sm:grid-cols-2">{children}</div>
    </Card>
  );
}

export default function ProfilePage() {
  const vocab = useQuery({ queryKey: ['vocab'], queryFn: api.vocabulary, staleTime: Infinity });
  const profileQ = useQuery({ queryKey: ['profile'], queryFn: api.profile });
  if (vocab.isLoading || profileQ.isLoading) return <Container><LoadingBlock /></Container>;
  if (vocab.error || profileQ.error) return <Container><ErrorState error={vocab.error ?? profileQ.error} /></Container>;
  return <ProfileForm key={profileQ.data?.updated_at ?? 'new'} v={vocab.data!} initial={profileQ.data ?? null} />;
}

function ProfileForm({ v, initial }: { v: Vocabulary; initial: Profile | null }) {
  const [params] = useSearchParams();
  const loc = useLocation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { refresh, signOut } = useAuth();
  const [p, setP] = useState<Profile>(() => ({ ...EMPTY, ...(initial ?? {}) }));
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (loc.hash) document.getElementById(loc.hash.slice(1))?.focus();
  }, [loc.hash]);

  const save = useMutation({
    mutationFn: () => api.saveProfile(p),
    onSuccess: async () => {
      setSaved(true);
      await refresh();
      await qc.invalidateQueries();
      if (params.get('welcome')) nav('/dashboard');
    },
  });
  const del = useMutation({ mutationFn: api.deleteAccount, onSuccess: () => { signOut(); nav('/'); } });
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => { setSaved(false); setP((x) => ({ ...x, [k]: v })); };

  const school = p.education_level === 'PRE_MATRIC' || p.education_level === 'POST_MATRIC_SCHOOL';

  function submit(e: FormEvent) {
    e.preventDefault();
    save.mutate();
  }

  return (
    <Container className="max-w-4xl">
      <PageHeader
        eyebrow={params.get('welcome') ? 'Step 1 of 1' : undefined}
        title={params.get('welcome') ? 'Tell us what the rules need' : 'Your eligibility profile'}
        subtitle="Every field is optional. Anything you leave blank is treated as unknown (never as a pass), and you will see which scholarships need it."
      />
      <Notice tone="neutral" icon={<Lock className="h-4 w-4" />} className="mb-6">
        We never ask for Aadhaar, certificates, bank details or documents. Only attributes that a recorded eligibility rule uses are stored, and you can delete everything at any time.
      </Notice>
      <form onSubmit={submit} className="space-y-5">
        <Section id="education" title="Education" desc="Used for education level, class/year and course rules.">
          <Field label="Current education level" htmlFor="education_level">
            <Select id="education_level" value={p.education_level ?? ''} onChange={(e) => set('education_level', e.target.value || null)}>
              <option value="">Not specified</option>
              {v.education_levels.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}
            </Select>
          </Field>
          {school ? (
            <Field label="Current class" htmlFor="current_class" optional>
              <Input id="current_class" type="number" min={1} max={12} value={p.current_class ?? ''} onChange={(e) => set('current_class', num(e.target.value))} />
            </Field>
          ) : (
            <Field label="Year of study in current programme" htmlFor="year_of_study" optional>
              <Input id="year_of_study" type="number" min={1} max={7} value={p.year_of_study ?? ''} onChange={(e) => set('year_of_study', num(e.target.value))} />
            </Field>
          )}
          <Field label="Discipline" htmlFor="discipline" optional>
            <Select id="discipline" value={p.discipline ?? ''} onChange={(e) => set('discipline', e.target.value || null)}>
              <option value="">Not specified</option>
              {v.disciplines.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}
            </Select>
          </Field>
          <Field label="Course name" htmlFor="course_name" optional hint="For your reference, e.g. B.Tech Computer Science.">
            <Input id="course_name" maxLength={120} value={p.course_name ?? ''} onChange={(e) => set('course_name', e.target.value || null)} />
          </Field>
          <Field label="Percentage in last qualifying exam" htmlFor="qualifying_exam_percentage" optional hint="CGPA is not converted to a percentage automatically.">
            <Input id="qualifying_exam_percentage" type="number" step="0.01" min={0} max={100} value={p.qualifying_exam_percentage ?? ''} onChange={(e) => set('qualifying_exam_percentage', num(e.target.value))} />
          </Field>
          <div className="grid grid-cols-[1fr_7rem] gap-3">
            <Field label="Current CGPA" htmlFor="cgpa" optional>
              <Input id="cgpa" type="number" step="0.01" min={0} max={10} value={p.cgpa ?? ''} onChange={(e) => set('cgpa', num(e.target.value))} />
            </Field>
            <Field label="Scale" htmlFor="cgpa_scale">
              <Select id="cgpa_scale" value={p.cgpa_scale} onChange={(e) => set('cgpa_scale', Number(e.target.value))}>
                <option value={10}>/ 10</option><option value={4}>/ 4</option><option value={5}>/ 5</option>
              </Select>
            </Field>
          </div>
        </Section>

        <Section id="finance" title="Financial and location" desc="Used for income ceilings and state/region restrictions.">
          <Field label="Annual family income (₹)" htmlFor="annual_family_income" optional hint="Income from all sources, as on your income certificate.">
            <Input id="annual_family_income" type="number" min={0} step={1000} value={p.annual_family_income ?? ''} onChange={(e) => set('annual_family_income', num(e.target.value))} />
          </Field>
          <Field label="State / UT of domicile" htmlFor="state" optional>
            <Select id="state" value={p.state ?? ''} onChange={(e) => set('state', e.target.value || null)}>
              <option value="">Not specified</option>
              {v.states.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </Field>
          <Field label="Indian citizen" htmlFor="is_indian_citizen" optional>
            <Select id="is_indian_citizen" value={triToStr(p.is_indian_citizen)} onChange={(e) => set('is_indian_citizen', strToTri(e.target.value))}>
              <option value="">Prefer not to say</option><option value="yes">Yes</option><option value="no">No</option>
            </Select>
          </Field>
        </Section>

        <Section id="demographics" title="Eligibility attributes" desc="Some schemes are reserved for specific groups. Share only what you are comfortable with.">
          <Field label="Gender" htmlFor="gender" optional>
            <Select id="gender" value={p.gender ?? ''} onChange={(e) => set('gender', e.target.value || null)}>
              <option value="">Prefer not to say</option>
              {v.genders.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}
            </Select>
          </Field>
          <Field label="Social category" htmlFor="category" optional>
            <Select id="category" value={p.category ?? ''} onChange={(e) => set('category', e.target.value || null)}>
              <option value="">Prefer not to say</option>
              {v.categories.map((x) => <option key={x.code} value={x.code}>{x.label}</option>)}
            </Select>
          </Field>
          <Field label="Person with disability" htmlFor="has_disability" optional>
            <Select id="has_disability" value={triToStr(p.has_disability)} onChange={(e) => set('has_disability', strToTri(e.target.value))}>
              <option value="">Prefer not to say</option><option value="yes">Yes</option><option value="no">No</option>
            </Select>
          </Field>
          {p.has_disability && (
            <Field label="Certified disability percentage" htmlFor="disability_percent" optional>
              <Input id="disability_percent" type="number" min={0} max={100} value={p.disability_percent ?? ''} onChange={(e) => set('disability_percent', num(e.target.value))} />
            </Field>
          )}
          <fieldset className="sm:col-span-2" id="special_circumstances" tabIndex={-1}>
            <legend className="mb-2 text-sm font-medium text-ink-800">Special circumstances <span className="text-xs font-normal text-ink-400">optional</span></legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {v.special_circumstances.map((x) => (
                <label key={x.code} className="flex items-start gap-2 rounded-lg border border-ink-200 p-2.5 text-sm hover:bg-ink-50">
                  <input type="checkbox" className="mt-0.5 h-4 w-4 accent-brand-600" checked={p.special_circumstances.includes(x.code)}
                    onChange={(e) => {
                      const next = e.target.checked ? [...p.special_circumstances, x.code] : p.special_circumstances.filter((c) => c !== x.code);
                      setSaved(false);
                      setP((cur) => ({ ...cur, special_circumstances: next, special_circumstances_none: next.length ? false : cur.special_circumstances_none }));
                    }} />
                  <span className="text-ink-700">{x.label}</span>
                </label>
              ))}
            </div>
            <label className="mt-3 flex items-center gap-2 text-sm text-ink-700">
              <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={p.special_circumstances_none}
                onChange={(e) => { setSaved(false); setP((cur) => ({ ...cur, special_circumstances_none: e.target.checked, special_circumstances: e.target.checked ? [] : cur.special_circumstances })); }} />
              None of these apply to me
            </label>
            <p className="mt-1 text-xs text-ink-500">If you leave this section untouched, schemes reserved for these groups show as "information needed".</p>
          </fieldset>
        </Section>

        {save.error && <Notice tone="red">{errorMessage(save.error)}</Notice>}
        {saved && !save.isPending && <Notice tone="green">Profile saved. Your recommendations have been recomputed.</Notice>}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Button type="submit" size="lg" loading={save.isPending}><Save className="h-4 w-4" />{params.get('welcome') ? 'Save and see my matches' : 'Save profile'}</Button>
          {initial && (
            <Button type="button" variant="ghost" className="text-rose-700" loading={del.isPending}
              onClick={() => { if (window.confirm('Delete your account and all profile data permanently?')) del.mutate(); }}>
              <Trash2 className="h-4 w-4" />Delete account and data
            </Button>
          )}
        </div>
      </form>
    </Container>
  );
}
