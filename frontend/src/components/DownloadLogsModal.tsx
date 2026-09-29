import React, { useState, useEffect } from 'react';
import { fetchStudents, fetchStudentSessions } from '../services/adminApi';
import { API_BASE_URL } from '../services/api';
import type { Student, Session } from '../types/api';

interface DownloadLogsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const DownloadLogsModal: React.FC<DownloadLogsModalProps> = ({ isOpen, onClose }) => {
  const [scope, setScope] = useState<'all' | 'student' | 'session'>('all');
  const [students, setStudents] = useState<Student[]>([]);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [selectedSession, setSelectedSession] = useState<string>('');
  const [start, setStart] = useState<string>('');
  const [end, setEnd] = useState<string>('');
  const [format, setFormat] = useState<'xlsx' | 'csv'>('xlsx');

  // Load students when needed
  useEffect(() => {
    if (scope === 'student' || scope === 'session') {
      fetchStudents().then(setStudents).catch(() => {});
    }
  }, [scope]);

  // Load sessions for selected student
  useEffect(() => {
    if (scope === 'session' && selectedStudent) {
      fetchStudentSessions(selectedStudent).then(setSessions).catch(() => {});
    }
  }, [scope, selectedStudent]);

  const download = async () => {
    const token = localStorage.getItem('admin_token');
    const params = new URLSearchParams({
      format,
      ...(start && { start }),
      ...(end && { end }),
    });
    const base = API_BASE_URL;
    let url = '';
    if (scope === 'all') {
      url = `${base}/admin/export/all?${params.toString()}`;
    } else if (scope === 'student') {
      url = `${base}/admin/export/student/${selectedStudent}?${params.toString()}`;
    } else {
      url = `${base}/admin/export/session/${selectedSession}?${params.toString()}`;
    }
    const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await response.blob();
    const disposition = response.headers.get('Content-Disposition');
    let filename = 'download';
    if (disposition) {
      const match = disposition.match(/filename=([^;]+)/);
      if (match) filename = match[1].replace(/"/g, '');
    }
    const link = document.createElement('a');
    link.href = window.URL.createObjectURL(blob);
    link.download = filename;
    link.click();
    onClose();
  };

  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="glass-card !bg-elev p-7 w-full max-w-md max-h-[90vh] overflow-y-auto animate-fade-up">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold mb-1">Export</p>
        <h2 className="font-display text-2xl text-fg mb-6">Download Logs</h2>
        <label className="field-label">Scope</label>
        <select
          value={scope}
          onChange={e => setScope(e.target.value as any)}
          className="input-premium mb-4"
        >
          <option value="all">All Students</option>
          <option value="student">One Student</option>
          <option value="session">One Session</option>
        </select>
        {scope === 'student' && (
          <>
            <label className="field-label">Student</label>
            <select
              value={selectedStudent}
              onChange={e => setSelectedStudent(e.target.value)}
              className="input-premium mb-4"
            >
              <option value="">Select student</option>
              {students.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.roll_no})
                </option>
              ))}
            </select>
          </>
        )}
        {scope === 'session' && (
          <>
            <label className="field-label">Student</label>
            <select
              value={selectedStudent}
              onChange={e => setSelectedStudent(e.target.value)}
              className="input-premium mb-4"
            >
              <option value="">Select student</option>
              {students.map(s => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.roll_no})
                </option>
              ))}
            </select>
            <label className="field-label">Session</label>
            <select
              value={selectedSession}
              onChange={e => setSelectedSession(e.target.value)}
              className="input-premium mb-4"
              disabled={!selectedStudent}
            >
              <option value="">Select session</option>
              {sessions.map(sess => (
                <option key={sess.id} value={sess.id}>Session {sess.id}</option>
              ))}
            </select>
          </>
        )}
        <label className="field-label">Start Date & Time (optional)</label>
        <input
          type="datetime-local"
          value={start}
          onChange={e => setStart(e.target.value)}
          className="input-premium mb-4"
        />
        <label className="field-label">End Date & Time (optional)</label>
        <input
          type="datetime-local"
          value={end}
          onChange={e => setEnd(e.target.value)}
          className="input-premium mb-4"
        />
        <label className="field-label">Format</label>
        <div className="flex gap-3 mb-6">
          <label className="btn-ghost flex-1 cursor-pointer has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
            <input
              type="radio"
              className="accent-[var(--fill-1)]"
              name="format"
              value="xlsx"
              checked={format === 'xlsx'}
              onChange={() => setFormat('xlsx')}
            />{' '}
            Excel (.xlsx)
          </label>
          <label className="btn-ghost flex-1 cursor-pointer has-[:checked]:border-accent has-[:checked]:bg-accent-soft">
            <input
              type="radio"
              className="accent-[var(--fill-1)]"
              name="format"
              value="csv"
              checked={format === 'csv'}
              onChange={() => setFormat('csv')}
            />{' '}
            CSV
          </label>
        </div>
        <div className="flex justify-end gap-3 pt-2 border-t border-line">
          <button onClick={onClose} className="btn-ghost mt-4">
            Cancel
          </button>
          <button onClick={download} className="btn-primary mt-4">
            Download
          </button>
        </div>
      </div>
    </div>
  );
};

export default DownloadLogsModal;
