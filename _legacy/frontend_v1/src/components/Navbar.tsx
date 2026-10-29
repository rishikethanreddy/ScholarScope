import { Link, useLocation } from 'react-router-dom';
import { GraduationCap } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  
  // Try to extract student ID from the URL if we are in a student context
  const pathParts = location.pathname.split('/');
  const studentId = (pathParts[1] === 'dashboard' || pathParts[1] === 'discover') ? pathParts[2] : null;

  return (
    <nav className="border-b border-gray-100 bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16 items-center">
          <div className="flex items-center space-x-2">
            <Link to="/" className="flex items-center space-x-2 hover:opacity-80 transition-opacity">
              <GraduationCap className="h-8 w-8 text-brand-600" />
              <span className="font-bold text-xl text-gray-900 hidden sm:block">ScholarMatch</span>
            </Link>
          </div>
          <div className="flex items-center space-x-4">
            {studentId ? (
              <>
                <Link to={`/dashboard/${studentId}`} className="text-gray-600 hover:text-brand-600 px-3 py-2 rounded-md text-sm font-medium transition-colors">Dashboard</Link>
                <Link to={`/discover/${studentId}`} className="text-gray-600 hover:text-brand-600 px-3 py-2 rounded-md text-sm font-medium transition-colors">Find Scholarships</Link>
              </>
            ) : (
              <>
                <Link to="/onboarding" className="text-gray-600 hover:text-brand-600 px-3 py-2 rounded-md text-sm font-medium transition-colors">For Students</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
