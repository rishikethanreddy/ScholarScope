import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import LandingPage from './pages/LandingPage';
import OnboardingPage from './pages/OnboardingPage';
import DashboardPage from './pages/DashboardPage';
import ScholarshipDiscoveryPage from './pages/ScholarshipDiscoveryPage';
import ScholarshipDetailPage from './pages/ScholarshipDetailPage';
import CheckScholarshipPage from './pages/CheckScholarshipPage';
import MainLayout from './layouts/MainLayout';

function App() {
  return (
    <Router>
      <MainLayout>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/dashboard/:studentId" element={<DashboardPage />} />
          <Route path="/discover/:studentId" element={<ScholarshipDiscoveryPage />} />
          <Route path="/check-scholarship/:studentId" element={<CheckScholarshipPage />} />
          <Route path="/scholarship/:scholarshipId" element={<ScholarshipDetailPage />} />
        </Routes>
      </MainLayout>
    </Router>
  );
}

export default App;
