import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { createStudent, getStudents } from '../services/api';
import { useForm } from 'react-hook-form';

const OnboardingPage = () => {
  const navigate = useNavigate();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm();
  const [savedProfiles, setSavedProfiles] = useState<any[]>([]);

  useEffect(() => {
    getStudents().then(setSavedProfiles).catch(console.error);
  }, []);
  
  const onSubmit = async (data: any) => {
    try {
      // Format numeric fields
      const formattedData = {
        ...data,
        age: parseInt(data.age),
        family_income: parseFloat(data.family_income),
        cgpa: data.cgpa ? parseFloat(data.cgpa) : null,
        percentage: data.percentage ? parseFloat(data.percentage) : null,
        disability_status: data.disability_status === 'true'
      };
      
      const student = await createStudent(formattedData);
      navigate(`/dashboard/${student.id}`);
    } catch (error) {
      console.error("Error creating profile", error);
      alert("Failed to create profile. Please check the backend connection.");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-2xl mx-auto">
        <Link to="/" className="inline-flex items-center text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors mb-6">
          &larr; Back to Home
        </Link>
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white p-8 rounded-2xl shadow-xl border border-gray-100"
        >
          <h2 className="text-3xl font-extrabold text-gray-900 mb-6 text-center">Create Your Profile</h2>
          <p className="text-gray-500 text-center mb-8">We need some information to find the best scholarships for you.</p>
          
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            
            <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <label className="block text-sm font-medium text-gray-700">Full Name</label>
                <div className="mt-1">
                  <input type="text" {...register("name", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                </div>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700">Age</label>
                <div className="mt-1">
                  <input type="number" {...register("age", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">Gender</label>
                <div className="mt-1">
                  <select {...register("gender", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border">
                    <option value="">Select...</option>
                    <option value="Male">Male</option>
                    <option value="Female">Female</option>
                    <option value="Other">Other</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">State</label>
                <div className="mt-1">
                  <input type="text" {...register("state", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700">District</label>
                <div className="mt-1">
                  <input type="text" {...register("district", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                </div>
              </div>
            </div>

            <div className="border-t border-gray-200 pt-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Academic & Financial</h3>
              <div className="grid grid-cols-1 gap-y-6 gap-x-4 sm:grid-cols-2">
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">Education Level</label>
                  <div className="mt-1">
                    <select {...register("education_level", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border">
                      <option value="">Select...</option>
                      <option value="School">School (Class 1-12)</option>
                      <option value="Diploma">Diploma</option>
                      <option value="Degree">Undergraduate Degree</option>
                      <option value="Postgraduate">Postgraduate Degree</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Course Name</label>
                  <div className="mt-1">
                    <input type="text" placeholder="e.g., B.Tech Computer Science" {...register("course", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Year of Study</label>
                  <div className="mt-1">
                    <input type="text" placeholder="e.g., 1st Year" {...register("year_of_study", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Current CGPA (out of 10)</label>
                  <div className="mt-1">
                    <input type="number" step="0.1" {...register("cgpa")} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Annual Family Income (₹)</label>
                  <div className="mt-1">
                    <input type="number" {...register("family_income", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border" />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Category</label>
                  <div className="mt-1">
                    <select {...register("category", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border">
                      <option value="">Select...</option>
                      <option value="General">General</option>
                      <option value="OBC">OBC</option>
                      <option value="SC">SC</option>
                      <option value="ST">ST</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Disability Status</label>
                  <div className="mt-1">
                    <select {...register("disability_status", { required: true })} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border">
                      <option value="false">No</option>
                      <option value="true">Yes</option>
                    </select>
                  </div>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700">Special Background</label>
                  <div className="mt-1">
                    <select {...register("special_background")} className="shadow-sm focus:ring-brand-500 focus:border-brand-500 block w-full sm:text-sm border-gray-300 rounded-md p-2 border">
                      <option value="">None</option>
                      <option value="Orphan">Orphan / Lost parents</option>
                      <option value="Ward of Armed Forces">Ward of Armed/Paramilitary Forces</option>
                      <option value="Worker Ward">Ward of Beedi/Cine/Mine Worker</option>
                    </select>
                  </div>
                </div>

              </div>
            </div>

            <div className="pt-5">
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full flex justify-center py-3 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500 disabled:opacity-50"
                >
                  {isSubmitting ? 'Saving Profile...' : 'Find Scholarships'}
                </button>
              </div>
            </div>
          </form>
        </motion.div>
        
        {savedProfiles.length > 0 && (
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="mt-8 bg-white p-8 rounded-2xl shadow-xl border border-gray-100"
          >
            <h3 className="text-xl font-bold text-gray-900 mb-4">Saved Profiles</h3>
            <p className="text-sm text-gray-500 mb-4">Select an existing profile to continue where you left off.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {savedProfiles.map(profile => (
                <Link 
                  key={profile.id} 
                  to={`/dashboard/${profile.id}`}
                  className="block p-4 border border-gray-200 rounded-lg hover:border-brand-500 hover:shadow-md transition-all"
                >
                  <p className="font-medium text-gray-900">{profile.name}</p>
                  <p className="text-xs text-gray-500 mt-1">{profile.course} • {profile.state}</p>
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default OnboardingPage;
