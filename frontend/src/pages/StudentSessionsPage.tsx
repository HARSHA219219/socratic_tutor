import React, { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { fetchStudent, fetchStudentSessions, fetchSessionMessages } from '../services/adminApi';
import type { Session } from '../types/api';
import { ArrowLeft, Search, ChevronRight, MessageSquare, CalendarClock } from 'lucide-react';
import { AdminShell, PageHeader, LoadingState, ErrorState } from '../components/AdminShell';

  const StudentSessionsPage: React.FC = () => {
  const { studentId } = useParams<{ studentId: string }>();
  const navigate = useNavigate();
  const [student, setStudent] = useState<{ name: string; roll_no: string } | null>(null);
  const title = student ? `Sessions for ${student.name} (${student.roll_no})` : `Sessions for Student ${studentId}`;

  // Load student details
  useEffect(() => {
    if (!studentId) return;
    const loadStudent = async () => {
      try {
        const data = await fetchStudent(studentId);
        setStudent({ name: data.name, roll_no: data.roll_no });
      } catch (e) {
        // ignore for now
      }
    };
    loadStudent();
  }, [studentId]);

  // Title with name and roll


  const [sessions, setSessions] = useState<Session[]>([]);
  const [msgCounts, setMsgCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
const [search, setSearch] = useState('');

  // Load sessions on mount
  useEffect(() => {
    if (!studentId) return;
    const load = async () => {
      try {
        const data = await fetchStudentSessions(studentId);
        setSessions(data);
        // For each session, fetch its messages to compute count (client‑side)
        const counts: Record<string, number> = {};
        await Promise.all(
          data.map(async (sess) => {
            const msgs = await fetchSessionMessages(studentId, sess.id);
            counts[sess.id] = msgs.length;
          })
        );
        setMsgCounts(counts);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Failed to load sessions');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [studentId]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;

  const formatDate = (d: string) => new Date(d).toLocaleString();

  // // const filteredSessions = sessions.filter((s) => {
  //   const status = s.ended_at ? 'completed' : 'ongoing';
  //   const haystack = `${s.id} ${status} ${formatDate(s.started_at)} ${s.ended_at ? formatDate(s.ended_at) : ''}`.toLowerCase();
  //   return haystack.includes(search.toLowerCase());
  // });

  return (
    <AdminShell>
      <Link to="/admin/logs" className="link-subtle mb-6">
        <ArrowLeft size={16} />
        Back to Students
      </Link>
      <PageHeader
        eyebrow="Sessions"
        title={
          student ? (
            <span className="flex items-center gap-4">
              <span className="avatar w-11 h-11 text-lg font-sans">{student.name.trim().charAt(0).toUpperCase()}</span>
              <span>
                {student.name}{' '}
                <span className="text-faint text-2xl font-sans font-normal">({student.roll_no})</span>
              </span>
            </span>
          ) : title
        }
        subtitle={`${sessions.length} session${sessions.length === 1 ? '' : 's'}`}
        actions={
          <div className="relative w-full md:w-72">
            <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
            <input
              type="text"
              placeholder="Search sessions..."
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
                <th>Chat</th>
                <th>Started At</th>
                <th className="hidden md:table-cell">Ended At</th>
                <th>Status</th>
                <th className="!text-center">Messages</th>
                <th className="!text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id} className="cursor-pointer" onClick={() => navigate(`/admin/logs/${studentId}/${s.id}`)}>
                  <td className="font-medium max-w-[16rem] truncate">{s.title || 'Untitled chat'}</td>
                  <td>
                    <span className="inline-flex items-center gap-2 whitespace-nowrap">
                      <CalendarClock size={15} className="text-faint" />
                      {formatDate(s.started_at)}
                    </span>
                  </td>
                  <td className="hidden md:table-cell whitespace-nowrap !text-muted">{s.ended_at ? formatDate(s.ended_at) : 'Ongoing'}</td>
                  <td>
                    {s.ended_at ? (
                      <span className="badge badge-done">Completed</span>
                    ) : (
                      <span className="badge badge-live">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                        Ongoing
                      </span>
                    )}
                  </td>
                  <td className="text-center">
                    <span className="inline-flex items-center gap-1.5 text-muted">
                      <MessageSquare size={14} />
                      {msgCounts[s.id] ?? '…'}
                    </span>
                  </td>
                  <td className="text-right">
                    <button
                      className="inline-flex items-center gap-1 text-sm font-medium text-accent hover:underline underline-offset-4 whitespace-nowrap"
                      onClick={(e) => { e.stopPropagation(); navigate(`/admin/logs/${studentId}/${s.id}`); }}
                    >
                      View Conversation
                      <ChevronRight size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sessions.length === 0 && (
          <div className="py-16 flex flex-col items-center text-center text-muted">
            <MessageSquare size={32} className="text-faint mb-3" />
            No sessions yet.
          </div>
        )}
      </div>
    </AdminShell>
  );
};

export default StudentSessionsPage;
