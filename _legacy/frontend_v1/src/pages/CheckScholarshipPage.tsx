import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Upload, FileText, CheckCircle, XCircle, ArrowLeft, Loader2, AlertCircle } from 'lucide-react';
import { checkPdfEligibility } from '../services/api';

const CheckScholarshipPage = () => {
  const { studentId } = useParams();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setResult(null);
    }
  };

  const handleUpload = async () => {
    if (!file || !studentId) return;

    setLoading(true);
    setError(null);

    try {
      const data = await checkPdfEligibility(studentId, file);
      setResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to analyze PDF. Please check your API key and file format.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="mb-6">
          <Link to={`/dashboard/${studentId}`} className="inline-flex items-center text-sm font-medium text-brand-600 hover:text-brand-800">
            <ArrowLeft className="mr-1 h-4 w-4" /> Back to Dashboard
          </Link>
        </div>

        <div className="bg-white shadow rounded-lg p-6 mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Check Scholarship Eligibility</h1>
          <p className="text-gray-600 mb-6">
            Found a scholarship PDF? Upload it here and our AI will extract the requirements and instantly tell you if you are eligible based on your saved profile!
          </p>

          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center bg-gray-50">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="hidden"
              id="file-upload"
            />
            <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center">
              <Upload className="mx-auto h-12 w-12 text-gray-400" />
              <span className="mt-2 block text-sm font-medium text-gray-900">
                {file ? file.name : "Select a PDF file to upload"}
              </span>
              <span className="mt-1 block text-sm text-gray-500">PDF up to 10MB</span>
            </label>
            {file && (
              <button
                onClick={handleUpload}
                disabled={loading}
                className="mt-6 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-brand-600 hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500 disabled:bg-gray-400"
              >
                {loading ? <Loader2 className="animate-spin -ml-1 mr-2 h-5 w-5" /> : <FileText className="-ml-1 mr-2 h-5 w-5" />}
                {loading ? "Analyzing PDF with AI..." : "Extract & Check Eligibility"}
              </button>
            )}
          </div>

          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded flex items-center">
              <AlertCircle className="h-5 w-5 mr-2" />
              {error}
            </div>
          )}
        </div>

        {/* Results Section */}
        {result && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
              AI Analysis Results
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Eligibility Section */}
              <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-gray-900">Your Eligibility</h3>
                  {result.eligibility.is_eligible ? (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                      <CheckCircle className="mr-1.5 h-4 w-4" /> Eligible
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
                      <XCircle className="mr-1.5 h-4 w-4" /> Not Eligible
                    </span>
                  )}
                </div>
                
                {result.eligibility.is_eligible && (
                  <div className="mb-4 text-center">
                    <p className="text-sm text-gray-500">Match Score</p>
                    <p className="text-3xl font-bold text-brand-600">{result.score}%</p>
                  </div>
                )}

                <div className="space-y-4">
                  {result.eligibility.reasons.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-green-800 mb-2">Matches:</h4>
                      <ul className="text-sm text-gray-600 space-y-1">
                        {result.eligibility.reasons.map((r: string, i: number) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.eligibility.failures.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-red-800 mb-2">Mismatches:</h4>
                      <ul className="text-sm text-gray-600 space-y-1">
                        {result.eligibility.failures.map((f: string, i: number) => (
                          <li key={i}>{f}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {result.eligibility.missing_info.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium text-amber-800 mb-2">Missing Profile Info:</h4>
                      <ul className="text-sm text-gray-600 space-y-1">
                        {result.eligibility.missing_info.map((m: string, i: number) => (
                          <li key={i}>• {m}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>

              {/* Extracted Data Section */}
              <div>
                <h3 className="text-lg font-medium text-gray-900 mb-4">Extracted Details</h3>
                <dl className="grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <dt className="text-sm font-medium text-gray-500">Scholarship Name</dt>
                    <dd className="mt-1 text-sm text-gray-900">{result.scholarship_data.name}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Provider</dt>
                    <dd className="mt-1 text-sm text-gray-900">{result.scholarship_data.provider}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Amount</dt>
                    <dd className="mt-1 text-sm text-gray-900 font-semibold">{result.scholarship_data.scholarship_amount || 'Varies'}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Min CGPA</dt>
                    <dd className="mt-1 text-sm text-gray-900">{result.scholarship_data.minimum_cgpa || 'None'}</dd>
                  </div>
                  <div>
                    <dt className="text-sm font-medium text-gray-500">Max Income</dt>
                    <dd className="mt-1 text-sm text-gray-900">₹{result.scholarship_data.maximum_family_income || 'None'}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-sm font-medium text-gray-500">Eligible Courses</dt>
                    <dd className="mt-1 text-sm text-gray-900">{result.scholarship_data.eligible_courses}</dd>
                  </div>
                </dl>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CheckScholarshipPage;
