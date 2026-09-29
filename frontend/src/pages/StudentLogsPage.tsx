import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchStudents } from '../services/adminApi';
import type { Student } from '../types/api';
import { Search, ChevronRight, Users } from 'lucide-react';
import { AdminShell, PageHeader, LoadingState, ErrorState } from '../components/AdminShell';

const StudentLogsPage: React.FC = () => {
  const navigate = useNavigate();
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const filteredStudents = students.filter((s) => {
    const haystack = `${s.id} ${s.name} ${s.roll_no} ${s.username}`.toLowerCase();
    return haystack.includes(search.toLowerCase());
  });

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchStudents();
        setStudents(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Failed to load students');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const handleViewSessions = (studentId: string) => {
    navigate(`/admin/logs/${studentId}`);
  };

  return (
    <AdminShell>
      <PageHeader
        eyebrow="Records"
        title="Student Logs"
        subtitle={`${students.length} student${students.length === 1 ? '' : 's'} registered`}
        actions={
          <div className="relative w-full md:w-72">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
            <input
              type="text"
              placeholder="Search students..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-premium !pl-11"
            />
          </div>
        }
      />
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-premium">
            <thead>
              <tr>
                <th>Name</th>
                <th>Username</th>
                <th>Roll No</th>
                <th className="hidden lg:table-cell">ID</th>
                <th className="!text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredStudents.map((s) => (
                <tr key={s.id} className="cursor-pointer" onClick={() => handleViewSessions(s.id)}>
                  <td>
                    <div className="flex items-center gap-3">
                      <span className="avatar w-8 h-8 text-xs">{s.name.trim().charAt(0).toUpperCase()}</span>
                      <span className="font-medium text-fg">{s.name}</span>
                    </div>
                  </td>
                  <td className="!text-muted">@{s.username}</td>
                  <td><span className="badge font-mono">{s.roll_no}</span></td>
                  <td className="hidden lg:table-cell font-mono text-xs !text-faint break-all">{s.id}</td>
                  <td className="text-right">
                    <button
                      className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline underline-offset-4 whitespace-nowrap"
                      onClick={(e) => { e.stopPropagation(); handleViewSessions(s.id); }}
                    >
                      View Sessions
                      <ChevronRight size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredStudents.length === 0 && (
          <div className="py-16 flex flex-col items-center text-center text-muted">
            <Users size={32} className="text-faint mb-3" />
            No students found.
          </div>
        )}
      </div>
    </AdminShell>
  );
};

export default StudentLogsPage;
