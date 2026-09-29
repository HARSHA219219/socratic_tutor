import React, { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { fetchSessionMessages, fetchAdminImage, fetchAdminDocument, fetchAdminAttachment } from '../services/adminApi';
import MessageAttachments from '../components/MessageAttachments';
import Markdown from '../components/Markdown';
import DocumentCard from '../components/DocumentCard';
import AuthImage from '../components/AuthImage';
import type { Message, HintAssessment } from '../types/api';
import { ArrowLeft, MessageSquare, Lightbulb, Eye } from 'lucide-react';
import { LogoMark } from '../components/Logo';
import { AdminShell, PageHeader, LoadingState, ErrorState } from '../components/AdminShell';

const label = (v: string) => v.replace(/_/g, ' ');

/** Instructor-only view of the hint planner's assessment for a hint reply. */
const HintPlanDetails: React.FC<{ plan: HintAssessment }> = ({ plan }) => (
  <details className="mb-2 w-full max-w-md rounded-xl border border-dashed border-line bg-surface px-3 py-2 text-xs text-muted">
    <summary className="cursor-pointer font-semibold text-fg select-none">
      Hint plan · {label(plan.question_depth)} · {plan.recommended_hint_count} hints
    </summary>
    <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
      <dt className="text-faint">Student level</dt><dd>{label(plan.student_level)}</dd>
      <dt className="text-faint">Student state</dt><dd>{label(plan.student_state)}</dd>
      <dt className="text-faint">Hint level</dt><dd>{plan.current_hint_level} of {plan.recommended_hint_count}</dd>
      {plan.learning_goal && (<><dt className="text-faint">Learning goal</dt><dd>{plan.learning_goal}</dd></>)}
      {plan.hint_purpose && (<><dt className="text-faint">Hint purpose</dt><dd>{plan.hint_purpose}</dd></>)}
      {plan.misconceptions.length > 0 && (
        <><dt className="text-faint">Misconceptions</dt><dd>{plan.misconceptions.join('; ')}</dd></>
      )}
    </dl>
  </details>
);

const StudentConversationPage: React.FC = () => {
  const { studentId, sessionId } = useParams<{ studentId: string; sessionId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!studentId || !sessionId) return;

    fetchSessionMessages(studentId, sessionId)
      .then(setMessages)
      .catch((err: any) => {
        setError(err?.response?.data?.detail || 'Failed to load conversation');
      })
      .finally(() => setLoading(false));
  }, [studentId, sessionId]);

  if (loading) return <LoadingState label="Loading conversation..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <AdminShell>
      <div className="max-w-3xl mx-auto">
        <Link to={`/admin/logs/${studentId}`} className="link-subtle mb-6">
          <ArrowLeft size={16} />
          Back to Sessions
        </Link>
        <PageHeader
          eyebrow="Transcript"
          title="Conversation"
          subtitle={`${messages.length} message${messages.length === 1 ? '' : 's'}`}
        />
        {messages.length === 0 ? (
          <div className="glass-card py-16 flex flex-col items-center text-center text-muted">
            <MessageSquare size={32} className="text-faint mb-3" />
            No messages in this session yet.
          </div>
        ) : (
          <div className="glass-card p-4 sm:p-6 md:p-8 space-y-6">
            {messages.map((message) => {
              const isUser = message.role === 'user';
              return (
                <article key={message.id} className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
                  {isUser ? (
                    <span className="avatar w-8 h-8 text-xs shrink-0 !bg-none !bg-surface-2 !text-fg">S</span>
                  ) : (
                    <LogoMark className="w-8 h-8 shrink-0" />
                  )}
                  <div className={`max-w-[85%] sm:max-w-[80%] flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
                    <div className="flex items-center gap-2 text-xs text-faint mb-1.5">
                      <span className="font-semibold uppercase tracking-[0.1em] text-muted">{message.role}</span>
                      <span>·</span>
                      <time>{new Date(message.timestamp).toLocaleString()}</time>
                      {message.kind?.startsWith('hint-') && (
                        <span className="help-badge">
                          <Lightbulb size={11} /> Hint {message.kind.slice(5)}{message.hint_total ? ` of ${message.hint_total}` : ''}
                        </span>
                      )}
                      {message.kind === 'answer' && (
                        <span className="help-badge help-badge-answer"><Eye size={11} /> Full answer</span>
                      )}
                    </div>
                    {message.attachments?.length ? (
                      <div className="mb-2 w-full">
                        <MessageAttachments
                          attachments={message.attachments}
                          fetcher={fetchAdminAttachment}
                          align={isUser ? 'end' : 'start'}
                          showStatus
                        />
                      </div>
                    ) : null}
                    {!message.attachments?.length && message.image_mime_type && (
                      <AuthImage messageId={message.id} fetcher={fetchAdminImage} className="mb-2 ring-1 ring-line" />
                    )}
                    {!message.attachments?.length && message.document_name && (
                      <DocumentCard
                        name={message.document_name}
                        mime={message.document_mime_type || ''}
                        size={message.document_size_bytes ?? 0}
                        messageId={message.id}
                        fetcher={fetchAdminDocument}
                        textStatus={message.document_text_status}
                        showStatus
                        className="mb-2"
                      />
                    )}
                    {message.hint_assessment && <HintPlanDetails plan={message.hint_assessment} />}
                    {message.content && isUser && (
                      <p className="whitespace-pre-wrap break-words leading-relaxed px-4 py-3 rounded-2xl bubble-user rounded-tr-md">
                        {message.content}
                      </p>
                    )}
                    {message.content && !isUser && (
                      <div className="break-words leading-relaxed px-4 py-3 rounded-2xl bubble-tutor rounded-tl-md">
                        <Markdown text={message.content} />
                      </div>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </AdminShell>
  );
};

export default StudentConversationPage;
