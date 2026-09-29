import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowRight, AlertCircle, AtSign, KeyRound, Lock, Loader2, LifeBuoy } from 'lucide-react';
import AuthLayout from '../components/AuthLayout';
import RecoveryCodePanel from '../components/RecoveryCodePanel';
import PasswordInput from '../components/PasswordInput';
import { verifyRecoveryCode, resetPassword, saveStudentSession, errorDetail } from '../services/api';
import { verifyAdminRecoveryCode, resetAdminPassword } from '../services/adminApi';

/** Password reset with username + recovery code. Shared by students and the instructor (admin). */

export default function ForgotPassword({ audience = 'student' }: { audience?: 'student' | 'admin' }) {
  const isAdmin = audience === 'admin';
  const navigate = useNavigate();
  const [step, setStep] = useState<'verify' | 'reset'>('verify');
  const [username, setUsername] = useState('');
  const [code, setCode] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<{ code: string; username: string } | null>(null);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const verify = isAdmin ? verifyAdminRecoveryCode : verifyRecoveryCode;
      const { reset_token } = await verify(username.trim(), code.trim());
      setResetToken(reset_token);
      setStep('reset');
    } catch (err: any) {
      setError(errorDetail(err, 'Invalid username or recovery code.'));
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      if (isAdmin) {
        const res = await resetAdminPassword(resetToken, password);
        localStorage.setItem('admin_token', res.access_token);
        setDone({ code: res.recovery_code, username: username.trim() });
      } else {
        const auth = await resetPassword(resetToken, password);
        saveStudentSession(auth);
        setDone({ code: auth.recovery_code || '', username: auth.student.username });
      }
    } catch (err: any) {
      setError(errorDetail(err, 'Could not reset password. Please start again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      headerRight={
        <Link to={isAdmin ? '/admin' : '/login'} className="link-subtle">
          <ArrowLeft size={16} />
          <span className="hidden sm:inline">{isAdmin ? 'Back to instructor login' : 'Back to sign in'}</span>
        </Link>
      }
    >
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-6 sm:pb-16">
        <div className="w-full max-w-md glass-card p-6 sm:p-8 md:p-10 animate-fade-up">
          {done?.code ? (
            <RecoveryCodePanel
              code={done.code}
              username={done.username}
              title="Password updated. Here's your new recovery code"
              continueLabel={isAdmin ? 'Continue to dashboard' : undefined}
              onContinue={() => navigate(isAdmin ? '/admin/dashboard' : '/chat')}
            />
          ) : (
            <>
              <div className="flex flex-col items-center text-center">
                <span className="logo-mark w-14 h-14 mb-5">
                  {step === 'verify' ? <LifeBuoy size={24} /> : <Lock size={24} />}
                </span>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">{isAdmin ? 'Instructor · ' : ''}Step {step === 'verify' ? '1' : '2'} of 2</p>
                <h2 className="font-display text-3xl text-fg mt-2">
                  {step === 'verify' ? 'Forgot password?' : 'Choose a new password'}
                </h2>
                <p className="mt-2 text-sm text-muted">
                  {step === 'verify'
                    ? isAdmin
                      ? 'Enter the instructor username and the recovery code generated in Dashboard → Security.'
                      : 'Enter your username and the private recovery code you saved when you created your account.'
                    : 'Your old recovery code will stop working and you will get a new one.'}
                </p>
              </div>

              <form onSubmit={step === 'verify' ? handleVerify : handleReset} className="mt-8 space-y-4">
                {error && (
                  <div className="alert-error" role="alert">
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                {step === 'verify' ? (
                  <>
                    <div>
                      <label className="field-label">Username</label>
                      <div className="relative">
                        <AtSign size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
                        <input className="input-premium !pl-11" required autoComplete="username" value={username}
                          onChange={(e) => setUsername(e.target.value)} placeholder="Your username" />
                      </div>
                    </div>
                    <div>
                      <label className="field-label">Recovery code</label>
                      <div className="relative">
                        <KeyRound size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
                        <input className="input-premium !pl-11 font-mono uppercase tracking-wider" required autoComplete="off"
                          spellCheck={false} value={code} onChange={(e) => setCode(e.target.value)} placeholder="XXXXX-XXXXX-XXXXX-XXXXX" />
                      </div>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="field-label" htmlFor="reset-new-password">New password</label>
                      <PasswordInput id="reset-new-password" className="input-premium" required minLength={8} autoComplete="new-password"
                        value={password} onChange={(e) => setPassword(e.target.value)} placeholder="At least 8 characters" />
                    </div>
                    <div>
                      <label className="field-label" htmlFor="reset-confirm-password">Confirm new password</label>
                      <PasswordInput id="reset-confirm-password" className="input-premium" required autoComplete="new-password"
                        value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Repeat your new password" />
                    </div>
                  </>
                )}

                <button type="submit" disabled={loading} className="btn-primary w-full !py-3.5">
                  {loading ? <Loader2 size={18} className="animate-spin" /> : null}
                  {step === 'verify' ? 'Verify' : 'Update password'}
                  {!loading && <ArrowRight size={18} />}
                </button>
              </form>

              <p className="mt-6 text-center text-xs text-faint">
                Without the recovery code a password can't be reset, so always keep it somewhere safe.
              </p>
            </>
          )}
        </div>
      </main>
    </AuthLayout>
  );
}
