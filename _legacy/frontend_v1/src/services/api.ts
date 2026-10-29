import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
});

export const createStudent = async (studentData: any) => {
  const response = await api.post('/api/students/', studentData);
  return response.data;
};

export const getStudent = async (studentId: str) => {
  const response = await api.get(`/api/students/${studentId}`);
  return response.data;
};

export const getStudents = async (skip = 0, limit = 100) => {
  const response = await api.get(`/api/students/?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getRecommendations = async (studentId: string) => {
  const response = await api.get(`/api/recommendations/${studentId}`);
  return response.data;
};

export const checkPdfEligibility = async (studentId: string, file: File) => {
  const formData = new FormData();
  formData.append('student_id', studentId);
  formData.append('file', file);
  
  const response = await api.post('/api/ai/check-eligibility', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getScholarships = async (skip = 0, limit = 100) => {
  const response = await api.get(`/api/scholarships/?skip=${skip}&limit=${limit}`);
  return response.data;
};

export const getScholarship = async (id: str) => {
  const response = await api.get(`/api/scholarships/${id}`);
  return response.data;
};

export const extractScholarship = async (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  const response = await api.post('/api/ai/extract-scholarship', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  });
  return response.data;
};

export default api;
