import React, { useState } from 'react';
import { KeyRound, Copy, Check, Download, ArrowRight, ShieldAlert } from 'lucide-react';

/** Shows a freshly issued recovery code exactly once and makes the student confirm they saved it. */
const RecoveryCodePanel: React.FC<{ code: string; username: string; onContinue: () => void; title?: string; continueLabel?: string }> = ({
  code,
  username,
  onContinue,
  title = 'Save your recovery code',
  continueLabel = 'Continue to my chats',
}) => {
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked: the code is still visible to copy manually
    }
  };

  const download = () => {
    const text = `Socratic Tutor recovery code\nUsername: ${username}\nRecovery code: ${code}\n\nKeep this private. It is the only way to reset your password.\n`;
    const link = document.createElement('a');
    link.href = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
    link.download = `socratic-tutor-recovery-${username}.txt`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  return (
    <div className="animate-fade-up">
      <div className="flex flex-col items-center text-center">
        <span className="logo-mark w-14 h-14 mb-5">
          <KeyRound size={24} />
        </span>
        <h2 className="font-display text-2xl sm:text-3xl text-fg">{title}</h2>
        <p className="mt-2 text-sm text-muted">
          If you forget your password, you'll need this code together with your username <strong className="text-fg">{username}</strong>.
        </p>
      </div>

      <div className="mt-6 rounded-2xl border border-dashed border-line-strong bg-surface p-5 text-center">
        <code className="block font-mono text-lg sm:text-xl tracking-[0.12em] text-fg break-all select-all">{code}</code>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <button type="button" onClick={copy} className="btn-ghost !py-2">
            {copied ? <Check size={15} className="text-accent" /> : <Copy size={15} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button type="button" onClick={download} className="btn-ghost !py-2">
            <Download size={15} />
            Download
          </button>
        </div>
      </div>

      <div className="mt-5 alert-error !items-start">
        <ShieldAlert size={16} className="mt-0.5 shrink-0" />
        <span>
          This code is shown <strong>only once</strong>. Keep it private: anyone with your username and this code can reset
          your password.
        </span>
      </div>

      <label className="mt-5 flex items-start gap-3 text-sm text-muted cursor-pointer select-none">
        <input
          type="checkbox"
          checked={saved}
          onChange={(e) => setSaved(e.target.checked)}
          className="mt-0.5 w-4 h-4 accent-[var(--fill-1)]"
        />
        I have saved my recovery code somewhere safe.
      </label>

      <button type="button" disabled={!saved} onClick={onContinue} className="btn-primary w-full mt-5 !py-3.5">
        {continueLabel}
        <ArrowRight size={18} />
      </button>
    </div>
  );
};

export default RecoveryCodePanel;
