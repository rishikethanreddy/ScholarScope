import { motion } from 'framer-motion';
import { ArrowRight, GraduationCap, Search, CheckCircle } from 'lucide-react';
import { Link } from 'react-router-dom';

const LandingPage = () => {
  return (
    <div className="min-h-screen bg-white">

      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="max-w-7xl mx-auto">
          <div className="relative z-10 pb-8 bg-white sm:pb-16 md:pb-20 lg:max-w-2xl lg:w-full lg:pb-28 xl:pb-32 pt-20">
            <main className="mt-10 mx-auto max-w-7xl px-4 sm:mt-12 sm:px-6 md:mt-16 lg:mt-20 lg:px-8 xl:mt-28">
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="sm:text-center lg:text-left"
              >
                <h1 className="text-4xl tracking-tight font-extrabold text-gray-900 sm:text-5xl md:text-6xl">
                  <span className="block xl:inline">Find scholarships that</span>{' '}
                  <span className="block text-brand-600 xl:inline">match your profile</span>
                </h1>
                <p className="mt-3 text-base text-gray-500 sm:mt-5 sm:text-lg sm:max-w-xl sm:mx-auto md:mt-5 md:text-xl lg:mx-0">
                  Stop searching through hundreds of irrelevant scholarships. Our AI-powered engine analyzes your profile and matches you with opportunities you're actually eligible for.
                </p>
                <div className="mt-5 sm:mt-8 sm:flex sm:justify-center lg:justify-start">
                  <div className="rounded-md shadow">
                    <Link
                      to="/onboarding"
                      className="w-full flex items-center justify-center px-8 py-3 border border-transparent text-base font-medium rounded-md text-white bg-brand-600 hover:bg-brand-700 md:py-4 md:text-lg md:px-10 transition-colors"
                    >
                      Get Started
                      <ArrowRight className="ml-2 w-5 h-5" />
                    </Link>
                  </div>
                </div>
              </motion.div>
            </main>
          </div>
        </div>
        <div className="lg:absolute lg:inset-y-0 lg:right-0 lg:w-1/2 bg-brand-50 flex items-center justify-center">
            <motion.div 
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.7, delay: 0.2 }}
                className="p-12 hidden lg:block"
            >
                {/* Abstract illustration representation */}
                <div className="relative w-full max-w-lg">
                    <div className="absolute top-0 -left-4 w-72 h-72 bg-purple-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob"></div>
                    <div className="absolute top-0 -right-4 w-72 h-72 bg-brand-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-2000"></div>
                    <div className="absolute -bottom-8 left-20 w-72 h-72 bg-pink-300 rounded-full mix-blend-multiply filter blur-xl opacity-70 animate-blob animation-delay-4000"></div>
                    <div className="relative glass-card p-8 rounded-2xl">
                        <div className="flex items-center gap-4 mb-6">
                            <div className="w-12 h-12 bg-green-100 text-green-600 rounded-full flex items-center justify-center">
                                <CheckCircle className="w-6 h-6" />
                            </div>
                            <div>
                                <h3 className="font-bold text-gray-900">94% Match Found</h3>
                                <p className="text-sm text-gray-500">AICTE Pragati Scholarship</p>
                            </div>
                        </div>
                        <div className="space-y-3">
                            <div className="h-2 bg-gray-100 rounded w-full"></div>
                            <div className="h-2 bg-gray-100 rounded w-5/6"></div>
                            <div className="h-2 bg-gray-100 rounded w-4/6"></div>
                        </div>
                    </div>
                </div>
            </motion.div>
        </div>
      </div>
    </div>
  );
};

export default LandingPage;
