import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getScholarship } from '../services/api';
import { ExternalLink, Calendar, MapPin, GraduationCap, DollarSign, ArrowLeft } from 'lucide-react';
import { motion } from 'framer-motion';

const ScholarshipDetailPage = () => {
  const { scholarshipId } = useParams();
  const [scholarship, setScholarship] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchScholarship = async () => {
      if (scholarshipId) {
        try {
          const data = await getScholarship(scholarshipId);
          setScholarship(data);
        } catch (error) {
          console.error("Error fetching scholarship details", error);
        } finally {
          setLoading(false);
        }
      }
    };
    fetchScholarship();
  }, [scholarshipId]);

  if (loading) return <div className="p-8 text-center">Loading details...</div>;
  if (!scholarship) return <div className="p-8 text-center">Scholarship not found</div>;

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto">
        <button onClick={() => window.history.back()} className="mb-6 flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors">
          <ArrowLeft className="mr-1 w-4 h-4" /> Back to list
        </button>
        
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl shadow-xl border border-gray-100 overflow-hidden"
        >
          {/* Header */}
          <div className="bg-brand-600 px-6 py-8 sm:p-10 text-white">
            <div className="uppercase tracking-widest text-brand-200 text-xs font-bold mb-2">{scholarship.provider}</div>
            <h1 className="text-3xl font-extrabold mb-4">{scholarship.name}</h1>
            <div className="flex flex-wrap gap-4 text-sm font-medium">
              <div className="flex items-center bg-brand-700/50 rounded-full px-3 py-1">
                <DollarSign className="w-4 h-4 mr-1" />
                {scholarship.scholarship_amount}
              </div>
              <div className="flex items-center bg-brand-700/50 rounded-full px-3 py-1">
                <Calendar className="w-4 h-4 mr-1" />
                Deadline: {scholarship.application_deadline || 'Open'}
              </div>
            </div>
          </div>
          
          {/* Content */}
          <div className="p-6 sm:p-10 space-y-8">
            
            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 border-b pb-2">Overview</h2>
              <p className="text-gray-600 whitespace-pre-wrap">{scholarship.short_description}</p>
            </section>

            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 border-b pb-2">Eligibility Requirements</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-100">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center"><GraduationCap className="w-4 h-4 mr-2 text-gray-500"/> Academic</h3>
                  <ul className="text-sm text-gray-600 space-y-2">
                    <li><span className="font-medium">Education Level:</span> {scholarship.education_level}</li>
                    <li><span className="font-medium">Eligible Courses:</span> {scholarship.eligible_courses}</li>
                    <li><span className="font-medium">Minimum CGPA:</span> {scholarship.minimum_cgpa || 'N/A'}</li>
                  </ul>
                </div>
                
                <div className="bg-gray-50 p-4 rounded-lg border border-gray-100">
                  <h3 className="font-semibold text-gray-900 mb-2 flex items-center"><MapPin className="w-4 h-4 mr-2 text-gray-500"/> Demographic</h3>
                  <ul className="text-sm text-gray-600 space-y-2">
                    <li><span className="font-medium">Income Limit:</span> {scholarship.maximum_family_income ? `₹${scholarship.maximum_family_income}` : 'N/A'}</li>
                    <li><span className="font-medium">Category:</span> {scholarship.category_requirement}</li>
                    <li><span className="font-medium">Eligible States:</span> {scholarship.eligible_states}</li>
                  </ul>
                </div>
              </div>
            </section>

            <section>
              <h2 className="text-xl font-bold text-gray-900 mb-4 border-b pb-2">Required Documents</h2>
              <p className="text-gray-600 text-sm whitespace-pre-wrap">{scholarship.required_documents}</p>
            </section>

            <div className="pt-6 border-t border-gray-200">
              <a 
                href={scholarship.application_url || scholarship.official_source_url} 
                target="_blank" 
                rel="noopener noreferrer"
                className="w-full flex items-center justify-center px-8 py-4 border border-transparent text-lg font-medium rounded-md text-white bg-brand-600 hover:bg-brand-700 md:py-4 md:text-lg md:px-10 transition-colors shadow-lg hover:shadow-xl"
              >
                Apply on Official Website
                <ExternalLink className="ml-2 w-5 h-5" />
              </a>
              <p className="text-center text-xs text-gray-400 mt-4">
                You will be redirected to the official scholarship portal. We do not process applications directly.
              </p>
            </div>
            
          </div>
        </motion.div>
      </div>
    </div>
  );
};

export default ScholarshipDetailPage;
