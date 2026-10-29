import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './lib/auth';
import { AdminLayout, AppShell, RequireAuth } from './components/Layout';
import Landing from './pages/Landing';
import { Login, Register } from './pages/Auth';
import ProfilePage from './pages/Profile';
import Dashboard from './pages/Dashboard';
import Discover from './pages/Discover';
import ScholarshipPage from './pages/Scholarship';
import Saved from './pages/Saved';
import Changes from './pages/Changes';
import CheckDocument from './pages/CheckDocument';
import NotFound from './pages/NotFound';

// Admin screens are code-split: students never download them.
const AdminOverview = lazy(() => import('./pages/admin/Overview'));
const AdminSources = lazy(() => import('./pages/admin/Sources'));
const AdminJobs = lazy(() => import('./pages/admin/Jobs'));
const AdminReview = lazy(() => import('./pages/admin/Review'));
const AdminChanges = lazy(() => import('./pages/admin/ChangesReview'));
const AdminData = lazy(() => import('./pages/admin/DataQuality'));
const AdminEvaluation = lazy(() => import('./pages/admin/Evaluation'));
const AdminAudit = lazy(() => import('./pages/admin/Audit'));

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-8"><div className="skeleton h-40" /></div>}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/discover" element={<Discover />} />
            <Route path="/changes" element={<Changes />} />
            <Route path="/scholarships/:id" element={<ScholarshipPage />} />
            <Route path="/profile" element={<RequireAuth role="student"><ProfilePage /></RequireAuth>} />
            <Route path="/dashboard" element={<RequireAuth role="student" needProfile><Dashboard /></RequireAuth>} />
            <Route path="/saved" element={<RequireAuth role="student" needProfile><Saved /></RequireAuth>} />
            <Route path="/check-document" element={<RequireAuth role="student" needProfile><CheckDocument /></RequireAuth>} />
            <Route path="/admin" element={<AdminLayout />}>
              <Route index element={<AdminOverview />} />
              <Route path="sources" element={<AdminSources />} />
              <Route path="jobs" element={<AdminJobs />} />
              <Route path="jobs/:id" element={<AdminJobs />} />
              <Route path="review" element={<AdminReview />} />
              <Route path="review/:id" element={<AdminReview />} />
              <Route path="changes" element={<AdminChanges />} />
              <Route path="data" element={<AdminData />} />
              <Route path="evaluation" element={<AdminEvaluation />} />
              <Route path="audit" element={<AdminAudit />} />
            </Route>
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
