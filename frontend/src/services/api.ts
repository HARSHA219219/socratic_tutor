import axios from 'axios';
import type { Student, StudentAuthResponse, Session, Message, ChatResponse, Checkpoint, StreamEvent } from '../types/api';
import { createSseParser } from './sse';

const rawUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
export const API_BASE_URL = `${rawUrl.replace(/\/+$/, '').replace(/\/api$/, '')}/api`;

// Upload limits live in attachmentRules.ts (re-exported for existing imports)
export { MAX_IMAGE_BYTES, ACCEPTED_IMAGE_TYPES, MAX_DOCUMENT_BYTES, DOCUMENT_EXTENSIONS } from './attachmentRules';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ----- Student session storage -----

export const getStudentToken = () => localStorage.getItem('student_token');

export const saveStudentSession = (auth: StudentAuthResponse) => {
  localStorage.setItem('student_token', auth.access_token);
  localStorage.setItem('studentId', auth.student.id);
  localStorage.setItem('studentName', auth.student.name);
  localStorage.setItem('studentUsername', auth.student.username);
};

export const clearStudentSession = () => {
  ['student_token', 'studentId', 'studentName', 'studentUsername'].forEach((k) => localStorage.removeItem(k));
};

apiClient.interceptors.request.use((config) => {
  const token = getStudentToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

apiClient.interceptors.response.use(
  (r) => r,
  (error) => {
    // Expired/invalid student token on a protected call: back to sign-in
    const url: string = error?.config?.url || '';
    if (error?.response?.status === 401 && !url.startsWith('/students/') && getStudentToken()) {
      clearStudentSession();
      window.location.assign('/login');
    }
    return Promise.reject(error);
  }
);

// ----- Accounts -----

export const signupStudent = async (body: { name: string; roll_no: string; username: string; password: string }) =>
  (await apiClient.post<StudentAuthResponse>('/students/signup', body)).data;

export const loginStudent = async (username: string, password: string) =>
  (await apiClient.post<StudentAuthResponse>('/students/login', { username, password })).data;

export const getMe = async () => (await apiClient.get<Student>('/students/me')).data;

export const verifyRecoveryCode = async (username: string, recovery_code: string) =>
  (await apiClient.post<{ reset_token: string }>('/students/recover/verify', { username, recovery_code })).data;

export const resetPassword = async (reset_token: string, new_password: string) =>
  (await apiClient.post<StudentAuthResponse>('/students/recover/reset', { reset_token, new_password })).data;

// ----- Chat -----

export const getStudentSessions = async (studentId: string): Promise<Session[]> => {
  const response = await apiClient.get<Session[]>(`/sessions/student/${studentId}`);
  return response.data;
};

export const createSession = async (studentId: string): Promise<Session> => {
  const response = await apiClient.post<Session>('/sessions/', { student_id: studentId });
  return response.data;
};

export const getSessionMessages = async (sessionId: string): Promise<Message[]> => {
  const response = await apiClient.get<Message[]>(`/chat/session/${sessionId}`);
  return response.data;
};

export const sendChatMessage = async (
  sessionId: string,
  message: string,
  image?: File | null,
  document?: File | null,
): Promise<ChatResponse> => {
  if (document) {
    const form = new FormData();
    form.append('session_id', sessionId);
    form.append('message', message);
    form.append('document', document);
    const response = await apiClient.post<ChatResponse>('/chat/document', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }
  if (image) {
    const form = new FormData();
    form.append('session_id', sessionId);
    form.append('message', message);
    form.append('image', image);
    const response = await apiClient.post<ChatResponse>('/chat/image', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  }
  const response = await apiClient.post<ChatResponse>('/chat/', { session_id: sessionId, message });
  return response.data;
};

/** Hint ladder ("hint") or direct answer ("answer") for the latest question in the session. */
export const requestTutorHelp = async (sessionId: string, mode: 'hint' | 'answer'): Promise<ChatResponse> =>
  (await apiClient.post<ChatResponse>('/chat/', { session_id: sessionId, mode })).data;

// ----- Streaming chat (Server-Sent Events via fetch) -----

export type StreamRequest =
  | { type: 'json'; body: { session_id: string; message?: string; mode?: 'normal' | 'hint' | 'answer' } }
  | { type: 'image' | 'document' | 'attachments'; form: FormData };

const httpError = (status: number, detail: string) =>
  // Same shape as an Axios error so errorDetail() keeps working
  Object.assign(new Error(detail), { response: { status, data: { detail } } });

/**
 * Streams one tutor turn. Calls onEvent for start / user_message / chunk / complete as they
 * arrive. Rejects on HTTP errors, a server "error" event, or a connection that ends early.
 */
export async function streamChat(req: StreamRequest, onEvent: (e: StreamEvent) => void, signal?: AbortSignal): Promise<void> {
  const token = getStudentToken();
  const headers: Record<string, string> = { Accept: 'text/event-stream' };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit;
  if (req.type === 'json') {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(req.body);
  } else {
    body = req.form; // the browser sets the multipart boundary itself
  }
  const path = req.type === 'json' ? '/chat/stream' : `/chat/stream/${req.type}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', headers, body, signal });

  if (!response.ok) {
    let detail = 'The tutor could not respond. Please try again.';
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string') detail = data.detail;
    } catch {
      // non-JSON error body
    }
    if (response.status === 401 && token) {
      clearStudentSession();
      window.location.assign('/login');
    }
    throw httpError(response.status, detail);
  }
  if (!response.body) throw httpError(500, 'Streaming is not supported by this browser.');

  let finished = false;
  let failure: string | null = null;
  const parser = createSseParser(data => {
    if (data === '[DONE]') return;
    let event: StreamEvent;
    try {
      event = JSON.parse(data);
    } catch {
      return; // ignore a malformed event rather than breaking the whole reply
    }
    if (event.type === 'error') failure = event.message;
    if (event.type === 'complete') finished = true;
    onEvent(event);
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    parser.push(decoder.decode(value, { stream: true }));
  }
  parser.push(decoder.decode());
  parser.end();

  if (failure) throw httpError(502, failure);
  if (!finished) throw httpError(502, 'The connection was interrupted before the tutor finished. Please try again.');
}

// ----- Checkpoints -----

export const createCheckpoint = async (sessionId: string, messageId: string): Promise<Checkpoint> =>
  (await apiClient.post<Checkpoint>('/checkpoints/', { session_id: sessionId, message_id: messageId })).data;

export const getSessionCheckpoints = async (sessionId: string): Promise<Checkpoint[]> =>
  (await apiClient.get<Checkpoint[]>(`/checkpoints/session/${sessionId}`)).data;

export const getCheckpoint = async (checkpointId: string): Promise<Checkpoint> =>
  (await apiClient.get<Checkpoint>(`/checkpoints/${checkpointId}`)).data;

export const continueFromCheckpoint = async (checkpointId: string): Promise<Session> =>
  (await apiClient.post<Session>(`/checkpoints/${checkpointId}/continue`)).data;

export const fetchAttachment = async (attachmentId: string): Promise<Blob> =>
  (await apiClient.get(`/attachments/${attachmentId}`, { responseType: 'blob' })).data;

export const fetchStudentDocument = async (messageId: string): Promise<Blob> =>
  (await apiClient.get(`/documents/${messageId}`, { responseType: 'blob' })).data;

export const fetchStudentImage = async (messageId: string): Promise<Blob> =>
  (await apiClient.get(`/images/${messageId}`, { responseType: 'blob' })).data;

export const errorDetail = (err: any, fallback: string): string => {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  // FastAPI validation errors: [{ msg: "Value error, ..." }]
  if (Array.isArray(detail) && detail[0]?.msg) return String(detail[0].msg).replace(/^Value error, /, '');
  return fallback;
};
