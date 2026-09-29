import React, { useEffect, useState } from 'react';
import { ShieldCheck, KeyRound, Lock, AlertCircle, CheckCircle2, X } from 'lucide-react';
import { fetchAdminSecurity, changeAdminPassword, generateAdminRecoveryCode } from '../services/adminApi';
import { errorDetail } from '../services/api';
import RecoveryCodePanel from './RecoveryCodePanel';
import PasswordInput from './PasswordInput';

type Status = { username: string; has_recovery_code: boolean; password_changed: boolean };
type Panel = 'none' | 'password' | 'code';

/** Admin: change password and generate a one-time recovery code (both need the current password). */
const AdminSecurityCard: React.FC = () => {
  const [status, setStatus] = useState<Status | null>(null);
  const [panel, setPanel] = useState<Panel>('none');
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [newCode, setNewCode] = useState<string | null>(null);

  const load = () => fetchAdminSecurity().then(setStatus).catch(() => {});
  useEffect(() => { load(); }, []);

  const open = (p: Panel) => {
    setPanel(p);
    setCurrent(''); setNext(''); setConfirm('');
    setError(''); setNotice('');
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (panel === 'password' && next !== confirm) {
      setError('New passwords do not match');
      return;
    }
    setBusy(true);
    try {
      if (panel === 'password') {
        await changeAdminPassword(current, next);
        setNotice('Password updated. Use the new password next time you sign in.');
      } else {
        const { recovery_code } = await generateAdminRecoveryCode(current);
        setNewCode(recovery_code);
      }
      setPanel('none');
      load();
    } catch (err: any) {
      setError(errorDetail(err, 'Something went wrong'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-card p-6">
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-accent-soft text-accent">
          <ShieldCheck size={18} />
        </span>
        <div>
          <p className="font-display text-xl text-fg">Security</p>
          <p className="text-xs text-faint">Signed in as {status?.username ?? '…'}</p>
        </div>
      </div>

      <ul className="mt-4 space-y-2 text-sm">
        <li className="flex items-center gap-2 text-muted">
          {status?.has_recovery_code
            ? <CheckCircle2 size={15} className="text-[var(--live-fg)]" />
            : <AlertCircle size={15} className="text-[var(--danger-fg)]" />}
          {status?.has_recovery_code ? 'Recovery code is set' : 'No recovery code yet'}
        </li>
        <li className="flex items-center gap-2 text-muted">
          {status?.password_changed
            ? <CheckCircle2 size={15} className="text-[var(--live-fg)]" />
            : <AlertCircle size={15} className="text-[var(--danger-fg)]" />}
          {status?.password_changed ? 'Custom password set' : 'Still using the default password'}
        </li>
      </ul>

      {notice && <p className="mt-4 text-sm text-[var(--live-fg)]">{notice}</p>}

      {panel === 'none' ? (
        <div className="mt-5 grid gap-2">
          <button onClick={() => open('password')} className="btn-ghost w-full">
            <Lock size={15} /> Change password
          </button>
          <button onClick={() => open('code')} className="btn-ghost w-full">
            <KeyRound size={15} /> {status?.has_recovery_code ? 'Generate new recovery code' : 'Create recovery code'}
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-5 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-fg">{panel === 'password' ? 'Change password' : 'New recovery code'}</p>
            <button type="button" onClick={() => setPanel('none')} className="icon-btn !w-8 !h-8" aria-label="Cancel"><X size={15} /></button>
          </div>
          {error && (
            <div className="alert-error" role="alert">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
          <PasswordInput required autoComplete="current-password" placeholder="Current password" aria-label="Current password"
            className="input-premium" value={current} onChange={(e) => setCurrent(e.target.value)} />
          {panel === 'password' && (
            <>
              <PasswordInput required minLength={8} autoComplete="new-password" placeholder="New password (8+ characters)"
                aria-label="New password" className="input-premium" value={next} onChange={(e) => setNext(e.target.value)} />
              <PasswordInput required autoComplete="new-password" placeholder="Confirm new password"
                aria-label="Confirm new password" className="input-premium" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </>
          )}
          {panel === 'code' && status?.has_recovery_code && (
            <p className="text-xs text-faint">Your current recovery code will stop working.</p>
          )}
          <button type="submit" disabled={busy} className="btn-primary w-full">
            {panel === 'password' ? 'Update password' : 'Generate code'}
          </button>
        </form>
      )}

      {newCode && status && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-card !bg-elev w-full max-w-md p-6 sm:p-8 max-h-[90vh] overflow-y-auto">
            <RecoveryCodePanel
              code={newCode}
              username={status.username}
              title="Save your instructor recovery code"
              continueLabel="Done"
              onContinue={() => setNewCode(null)}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminSecurityCard;
