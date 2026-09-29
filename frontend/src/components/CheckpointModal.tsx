import React, { useEffect } from 'react';
import { BookmarkCheck, X, ArrowRight, Loader2 } from 'lucide-react';
import type { Checkpoint, CheckpointSummary } from '../types/api';

const LIST_SECTIONS: [keyof CheckpointSummary, string][] = [
  ['student_knowledge', 'What you have shown you know'],
  ['correct_understanding', 'Correct understanding reached'],
  ['student_attempts', 'Your attempts'],
  ['misconceptions', 'Misconceptions to watch'],
  ['hints_given', 'Hints given'],
  ['answers_revealed', 'Answers revealed'],
  ['attachments', 'Attachments'],
  ['unresolved_questions', 'Still unresolved'],
];

const known = (v?: string) => (v && v.toLowerCase() !== 'unknown' ? v : null);

/** Shows a checkpoint's learning-state summary (or the context of a continued chat). */
const CheckpointModal: React.FC<{
  checkpoint?: Checkpoint | null;
  contextText?: string | null;
  onClose: () => void;
  onContinue?: () => void;
  continuing?: boolean;
}> = ({ checkpoint, contextText, onClose, onContinue, continuing }) => {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const s = checkpoint?.summary;
  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4" onClick={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Checkpoint summary"
        onClick={(e) => e.stopPropagation()}
        className="glass-card !bg-elev w-full sm:max-w-xl max-h-[88vh] flex flex-col !rounded-b-none sm:!rounded-3xl animate-fade-up"
      >
        <div className="flex items-start gap-3 p-5 sm:p-6 border-b border-line">
          <span className="flex items-center justify-center w-10 h-10 shrink-0 rounded-xl bg-accent-soft text-accent">
            <BookmarkCheck size={19} />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-gold">
              {checkpoint ? (checkpoint.source === 'automatic' ? 'Automatic checkpoint' : 'Checkpoint') : 'Continued conversation'}
            </p>
            <h2 className="font-display text-xl text-fg leading-snug">
              {known(s?.topic) || (checkpoint ? 'Learning summary' : 'Context from your earlier chat')}
            </h2>
          </div>
          <button onClick={onClose} className="icon-btn !w-9 !h-9" aria-label="Close"><X size={17} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-5 text-sm">
          {s ? (
            <>
              {known(s.learning_objective) && (
                <section>
                  <h3 className="field-label !mb-1">Learning goal</h3>
                  <p className="text-fg leading-relaxed">{s.learning_objective}</p>
                </section>
              )}
              {LIST_SECTIONS.map(([key, label]) => {
                const items = (s[key] as string[] | undefined) || [];
                if (!items.length) return null;
                return (
                  <section key={key}>
                    <h3 className="field-label !mb-1.5">{label}</h3>
                    <ul className="space-y-1.5">
                      {items.map((item, i) => (
                        <li key={i} className="flex gap-2 text-fg leading-relaxed">
                          <span className="mt-2 w-1.5 h-1.5 rounded-full bg-[var(--fill-1)] shrink-0" />
                          <span>{item}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                );
              })}
              {known(s.next_tutoring_action) && (
                <section className="rounded-2xl bg-accent-soft p-4">
                  <h3 className="field-label !mb-1 !text-accent">Next step</h3>
                  <p className="text-fg leading-relaxed">{s.next_tutoring_action}</p>
                </section>
              )}
            </>
          ) : (
            <p className="text-fg leading-relaxed whitespace-pre-wrap">
              {(contextText || '').replace(/^\[Trusted tutor context:[^\]]*\]\s*/, '')}
            </p>
          )}
        </div>

        {onContinue && (
          <div className="p-4 sm:p-5 border-t border-line flex flex-col-reverse sm:flex-row sm:justify-end gap-2">
            <button onClick={onClose} className="btn-ghost">Close</button>
            <button onClick={onContinue} disabled={continuing} className="btn-primary">
              {continuing ? <Loader2 size={16} className="animate-spin" /> : null}
              Continue from checkpoint
              {!continuing && <ArrowRight size={16} />}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default CheckpointModal;
