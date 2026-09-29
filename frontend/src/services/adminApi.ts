import axios from 'axios';
import type { Student, Session, Message } from '../types/api';
import { API_BASE_URL } from './api';

const API_URL = API_BASE_URL;

// Helper to get JWT token from localStorage
const getAuthHeaders = () => {
  const token = localStorage.getItem('admin_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const fetchStudents = async (): Promise<Student[]> => {
  const response = await axios.get<Student[]>(`${API_URL}/admin/students`, {
    headers: getAuthHeaders(),
  });
  return response.data;
};

export const fetchStudent = async (studentId: string): Promise<Student & { sessions: Session[] }> => {
  const response = await axios.get<Student & { sessions: Session[] }>(
    `${API_URL}/admin/students/${studentId}`,
    { headers: getAuthHeaders() }
  );
  return response.data;
};

export const fetchStudentSessions = async (studentId: string): Promise<Session[]> => {
  const response = await axios.get<Session[]>(
    `${API_URL}/admin/students/${studentId}/sessions`,
    { headers: getAuthHeaders() }
  );
  return response.data;
};

export const fetchSessionMessages = async (studentId: string, sessionId: string): Promise<Message[]> => {
  const response = await axios.get<Message[]>(
    `${API_URL}/admin/students/${studentId}/sessions/${sessionId}`,
    { headers: getAuthHeaders() }
  );
  return response.data;
};

export const fetchAdminImage = async (messageId: string): Promise<Blob> => {
  const response = await axios.get(`${API_URL}/images/${messageId}`, {
    headers: getAuthHeaders(),
    responseType: 'blob',
  });
  return response.data;
};

// ----- Admin password / recovery code -----

export const verifyAdminRecoveryCode = async (username: string, recovery_code: string) =>
  (await axios.post<{ reset_token: string }>(`${API_URL}/admin/recover/verify`, { username, recovery_code })).data;

export const resetAdminPassword = async (reset_token: string, new_password: string) =>
  (await axios.post<{ access_token: string; recovery_code: string }>(`${API_URL}/admin/recover/reset`, { reset_token, new_password })).data;

export const fetchAdminSecurity = async () =>
  (await axios.get<{ username: string; has_recovery_code: boolean; password_changed: boolean }>(
    `${API_URL}/admin/security`, { headers: getAuthHeaders() })).data;

export const changeAdminPassword = async (current_password: string, new_password: string) =>
  (await axios.post(`${API_URL}/admin/security/password`, { current_password, new_password }, { headers: getAuthHeaders() })).data;

export const generateAdminRecoveryCode = async (current_password: string) =>
  (await axios.post<{ recovery_code: string }>(`${API_URL}/admin/security/recovery-code`, { current_password }, { headers: getAuthHeaders() })).data;

export const fetchAdminDocument = async (messageId: string): Promise<Blob> => {
  const response = await axios.get(`${API_URL}/documents/${messageId}`, {
    headers: getAuthHeaders(),
    responseType: 'blob',
  });
  return response.data;
};

export const fetchAdminAttachment = async (attachmentId: string): Promise<Blob> => {
  const response = await axios.get(`${API_URL}/attachments/${attachmentId}`, {
    headers: getAuthHeaders(),
    responseType: 'blob',
  });
  return response.data;
};
