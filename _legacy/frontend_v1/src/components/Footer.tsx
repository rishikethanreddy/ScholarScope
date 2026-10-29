import { GraduationCap, Heart } from 'lucide-react';
import { Link } from 'react-router-dom';

const Footer = () => {
  return (
    <footer className="bg-white border-t border-gray-200 pt-12 pb-8 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-8">
          <div className="col-span-1 md:col-span-2">
            <Link to="/" className="flex items-center space-x-2 mb-4">
              <GraduationCap className="h-6 w-6 text-brand-600" />
              <span className="font-bold text-lg text-gray-900">ScholarMatch</span>
            </Link>
            <p className="text-gray-500 text-sm max-w-xs">
              AI-powered scholarship recommendations to help students achieve their dreams without financial burden.
            </p>
            <div className="flex space-x-4 mt-6">
              {/* Social icons removed for stability */}
            </div>
          </div>
          
          <div>
            <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase mb-4">Resources</h3>
            <ul className="space-y-3">
              <li>
                <Link to="/onboarding" className="text-sm text-gray-500 hover:text-brand-600">Find Scholarships</Link>
              </li>
              <li>
                <a href="#" className="text-sm text-gray-500 hover:text-brand-600">How it Works</a>
              </li>
              <li>
                <a href="#" className="text-sm text-gray-500 hover:text-brand-600">Success Stories</a>
              </li>
            </ul>
          </div>

          <div>
            <h3 className="text-sm font-semibold text-gray-900 tracking-wider uppercase mb-4">Legal</h3>
            <ul className="space-y-3">
              <li>
                <a href="#" className="text-sm text-gray-500 hover:text-brand-600">Privacy Policy</a>
              </li>
              <li>
                <a href="#" className="text-sm text-gray-500 hover:text-brand-600">Terms of Service</a>
              </li>
            </ul>
          </div>
        </div>
        
        <div className="border-t border-gray-200 pt-8 flex flex-col md:flex-row justify-between items-center">
          <p className="text-sm text-gray-400 mb-4 md:mb-0">
            &copy; {new Date().getFullYear()} ScholarMatch. All rights reserved.
          </p>
          <p className="text-sm text-gray-400 flex items-center">
            Built with <Heart className="h-4 w-4 mx-1 text-red-500" /> for students
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
