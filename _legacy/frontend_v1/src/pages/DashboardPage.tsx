import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { getStudent, getRecommendations } from '../services/api';
import { Award, Briefcase, GraduationCap, Clock, ChevronRight } from 'lucide-react';

const DashboardPage = () => {
  const { studentId } = useParams();
  const [student, setStudent] = useState<any>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        if (!studentId) return;
        const [studentData, recsData] = await Promise.all([
          getStudent(studentId),
          getRecommendations(studentId)
        ]);
        setStudent(studentData);
        setRecommendations(recsData);
      } catch (error) {
        console.error("Error fetching data", error);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [studentId]);

  if (loading) {
    return <div className="min-h-screen flex items-center justify-center">Loading dashboard...</div>;
  }

  const eligibleRecs = recommendations.filter(r => r.is_eligible);
  const strongMatches = eligibleRecs.filter(r => r.score >= 80);
  const openRecs = eligibleRecs.filter(r => r.scholarship.application_status === 'ACTIVE' || r.scholarship.application_status === 'ACTIVE_RENEWAL');

  return (
    <div className="min-h-screen bg-gray-50 pb-12">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Welcome back, {student?.name}</h1>
              <p className="text-sm text-gray-500">{student?.course} • {student?.state}</p>
            </div>
            <div className="flex space-x-3">
              <Link to={`/check-scholarship/${studentId}`} className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50">
                Check PDF Eligibility
              </Link>
              <Link to={`/discover/${studentId}`} className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-brand-600 hover:bg-brand-700">
                Browse All Scholarships
              </Link>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5 flex items-center">
              <div className="flex-shrink-0 bg-blue-100 rounded-md p-3">
                <Briefcase className="h-6 w-6 text-blue-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dt className="text-sm font-medium text-gray-500 truncate">Total Scholarships</dt>
                <dd className="text-3xl font-semibold text-gray-900">{recommendations.length}</dd>
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5 flex items-center">
              <div className="flex-shrink-0 bg-green-100 rounded-md p-3">
                <Award className="h-6 w-6 text-green-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dt className="text-sm font-medium text-gray-500 truncate">Eligible For</dt>
                <dd className="text-3xl font-semibold text-gray-900">{eligibleRecs.length}</dd>
              </div>
            </div>
          </motion.div>
          
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5 flex items-center">
              <div className="flex-shrink-0 bg-purple-100 rounded-md p-3">
                <GraduationCap className="h-6 w-6 text-purple-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dt className="text-sm font-medium text-gray-500 truncate">Strong Matches</dt>
                <dd className="text-3xl font-semibold text-gray-900">{strongMatches.length}</dd>
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="bg-white overflow-hidden shadow rounded-lg">
            <div className="p-5 flex items-center">
              <div className="flex-shrink-0 bg-amber-100 rounded-md p-3">
                <Clock className="h-6 w-6 text-amber-600" />
              </div>
              <div className="ml-5 w-0 flex-1">
                <dt className="text-sm font-medium text-gray-500 truncate">Currently Open</dt>
                <dd className="text-3xl font-semibold text-gray-900">{openRecs.length}</dd>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Top Recommendations */}
        <h2 className="text-lg font-medium text-gray-900 mb-4">Top Recommendations For You</h2>
        <div className="bg-white shadow overflow-hidden sm:rounded-md">
          <ul role="list" className="divide-y divide-gray-200">
            {eligibleRecs.slice(0, 5).map((rec, index) => (
              <motion.li 
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 * index }}
                key={rec.scholarship_id}
              >
                <Link to={`/scholarship/${rec.scholarship_id}`} className="block hover:bg-gray-50 transition-colors">
                  <div className="px-4 py-4 sm:px-6">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center max-w-2xl">
                         <div className="flex-shrink-0">
                           <div className="h-12 w-12 rounded-full bg-brand-100 flex items-center justify-center border border-brand-200">
                             <span className="text-brand-700 font-bold">{Math.round(rec.score)}%</span>
                           </div>
                         </div>
                         <div className="ml-4">
                           <p className="text-sm font-medium text-brand-600 truncate">{rec.scholarship.name}</p>
                           <p className="text-xs text-gray-500">{rec.scholarship.provider}</p>
                         </div>
                      </div>
                      <div className="ml-2 flex-shrink-0 flex">
                        <p className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                          {rec.scholarship.scholarship_amount}
                        </p>
                      </div>
                    </div>
                    <div className="mt-2 sm:flex sm:justify-between">
                      <div className="sm:flex">
                        <p className="flex items-center text-sm text-gray-500">
                          Deadline: {rec.scholarship.application_deadline || 'Open'}
                        </p>
                      </div>
                      <div className="mt-2 flex items-center text-sm text-gray-500 sm:mt-0">
                        View Details
                        <ChevronRight className="ml-1 h-4 w-4" />
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.li>
            ))}
            {eligibleRecs.length === 0 && (
              <li className="px-4 py-8 text-center text-gray-500">
                No eligible scholarships found for your profile at the moment.
              </li>
            )}
          </ul>
        </div>
        
        <div className="mt-4 text-center">
          <Link to={`/discover/${studentId}`} className="text-brand-600 hover:text-brand-800 font-medium text-sm">
            View all {recommendations.length} scholarships →
          </Link>
        </div>
      </div>
    </div>
  );
};

export default DashboardPage;
