import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRecommendations } from '../services/api';
import { Filter, Search, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

const ScholarshipDiscoveryPage = () => {
  const { studentId } = useParams();
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [filtered, setFiltered] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');

  useEffect(() => {
    const fetchRecs = async () => {
      if (studentId) {
        const data = await getRecommendations(studentId);
        setRecommendations(data);
        setFiltered(data);
        setLoading(false);
      }
    };
    fetchRecs();
  }, [studentId]);

  useEffect(() => {
    if (filter === 'ALL') {
      setFiltered(recommendations);
    } else if (filter === 'ELIGIBLE') {
      setFiltered(recommendations.filter(r => r.is_eligible));
    } else if (filter === 'INELIGIBLE') {
      setFiltered(recommendations.filter(r => !r.is_eligible));
    }
  }, [filter, recommendations]);

  if (loading) return <div className="p-8 text-center">Loading scholarships...</div>;

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-5xl mx-auto">
        <Link to={`/dashboard/${studentId}`} className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors mb-6">
          &larr; Back to Dashboard
        </Link>
        <div className="flex flex-col sm:flex-row justify-between items-center mb-8 gap-4">
          <h1 className="text-3xl font-bold text-gray-900">Scholarship Discovery</h1>
          <div className="flex space-x-2">
            <button onClick={() => setFilter('ALL')} className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${filter === 'ALL' ? 'bg-brand-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'}`}>All</button>
            <button onClick={() => setFilter('ELIGIBLE')} className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${filter === 'ELIGIBLE' ? 'bg-green-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'}`}>Eligible</button>
            <button onClick={() => setFilter('INELIGIBLE')} className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${filter === 'INELIGIBLE' ? 'bg-red-600 text-white' : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-200'}`}>Not Eligible</button>
          </div>
        </div>

        <div className="space-y-6">
          {filtered.map((rec, i) => (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              key={rec.scholarship_id} 
              className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden hover:shadow-md transition-shadow"
            >
              <div className="p-6">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-semibold uppercase tracking-wider text-gray-500">{rec.scholarship.provider}</span>
                      {rec.is_eligible ? (
                         <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                           Eligible
                         </span>
                      ) : (
                         <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                           Not Eligible
                         </span>
                      )}
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 mb-2">
                      <Link to={`/scholarship/${rec.scholarship_id}`} className="hover:text-brand-600">
                        {rec.scholarship.name}
                      </Link>
                    </h2>
                    <p className="text-gray-600 text-sm mb-4 line-clamp-2">{rec.scholarship.short_description}</p>
                    
                    <div className="flex flex-wrap gap-4 text-sm">
                      <div className="flex items-center text-gray-500">
                        <span className="font-medium text-gray-900 mr-1">Amount:</span> {rec.scholarship.scholarship_amount}
                      </div>
                      <div className="flex items-center text-gray-500">
                        <span className="font-medium text-gray-900 mr-1">Deadline:</span> {rec.scholarship.application_deadline || 'Open'}
                      </div>
                    </div>
                  </div>
                  
                  {rec.is_eligible && (
                    <div className="ml-6 flex flex-col items-center justify-center h-20 w-20 rounded-full border-4 border-brand-100 bg-brand-50">
                      <span className="text-xl font-bold text-brand-700">{Math.round(rec.score)}%</span>
                      <span className="text-xs text-brand-600">Match</span>
                    </div>
                  )}
                </div>

                <div className="mt-6 pt-4 border-t border-gray-100 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    {rec.reasons.length > 0 && (
                      <div className="mb-2">
                        <h4 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2 flex items-center"><CheckCircle className="w-3 h-3 mr-1"/> Why it matches</h4>
                        <ul className="space-y-1">
                          {rec.reasons.slice(0, 3).map((reason: string, j: number) => (
                            <li key={j} className="text-xs text-gray-600">{reason}</li>
                          ))}
                          {rec.reasons.length > 3 && <li className="text-xs text-gray-500 italic">+{rec.reasons.length - 3} more...</li>}
                        </ul>
                      </div>
                    )}
                  </div>
                  <div>
                    {rec.failures.length > 0 && (
                      <div>
                        <h4 className="text-xs font-bold text-red-700 uppercase tracking-wider mb-2 flex items-center"><XCircle className="w-3 h-3 mr-1"/> Mismatches</h4>
                        <ul className="space-y-1">
                          {rec.failures.map((failure: string, j: number) => (
                            <li key={j} className="text-xs text-red-600">{failure}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    
                    {rec.missing_info.length > 0 && (
                      <div className="mt-3">
                         <h4 className="text-xs font-bold text-amber-700 uppercase tracking-wider mb-2 flex items-center"><AlertCircle className="w-3 h-3 mr-1"/> Missing Info</h4>
                         <p className="text-xs text-gray-600">Your profile is missing: {rec.missing_info.join(', ')}</p>
                      </div>
                    )}
                  </div>
                </div>
                
                <div className="mt-4 flex justify-end">
                  <Link to={`/scholarship/${rec.scholarship_id}`} className="text-sm font-medium text-brand-600 hover:text-brand-800">
                    View Full Details & Apply &rarr;
                  </Link>
                </div>
              </div>
            </motion.div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
              <p className="text-gray-500">No scholarships found matching this filter.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ScholarshipDiscoveryPage;
