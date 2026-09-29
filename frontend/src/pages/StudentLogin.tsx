import React, { useEffect, useId, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { signupStudent, loginStudent, saveStudentSession, getStudentToken, errorDetail } from '../services/api';
import type { StudentAuthResponse } from '../types/api';
import { ArrowRight, Loader2, ShieldCheck, AlertCircle, User, Hash, AtSign, Lock, Info } from 'lucide-react';
import AuthLayout from '../components/AuthLayout';
import RecoveryCodePanel from '../components/RecoveryCodePanel';
import PasswordInput from '../components/PasswordInput';

type Tab = 'signin' | 'signup';

const Field: React.FC<{
  label: string;
  icon: React.ReactNode;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>> = ({ label, icon, hint, type, ...input }) => {
  const id = useId();
  return (
    <div>
      <label className="field-label" htmlFor={id}>{label}</label>
      <div className="relative">
        <span className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none z-10">{icon}</span>
        {type === 'password' ? (
          <PasswordInput {...input} id={id} className="input-premium !pl-11" />
        ) : (
          <input {...input} type={type} id={id} className="input-premium !pl-11" />
        )}
      </div>
      {hint && <p className="mt-1.5 text-xs text-faint">{hint}</p>}
    </div>
  );
};

export default function StudentLogin() {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(searchParams.get('mode') === 'signup' ? 'signup' : 'signin');
  const [name, setName] = useState('');
  const [rollNo, setRollNo] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [newAccount, setNewAccount] = useState<StudentAuthResponse | null>(null);
  const navigate = useNavigate();

  // Already signed in: go straight to the chat
  useEffect(() => {
    if (getStudentToken()) navigate('/chat', { replace: true });
  }, [navigate]);

  const switchTab = (t: Tab) => {
    setTab(t);
    setError('');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (tab === 'signup' && password !== confirm) {
      setError('Passwords do not match');
      return;
    }

    setLoading(true);
    try {
      if (tab === 'signin') {
        saveStudentSession(await loginStudent(username.trim(), password));
        navigate('/chat');
      } else {
        const auth = await signupStudent({ name: name.trim(), roll_no: rollNo.trim(), username: username.trim(), password });
        saveStudentSession(auth);
        setNewAccount(auth);
      }
    } catch (err: any) {
      setError(errorDetail(err, 'An error occurred. Please try again.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      headerRight={
        <Link to="/admin" className="link-subtle">
          <ShieldCheck size={16} />
          <span className="hidden sm:inline">Instructor login</span>
        </Link>
      }
    >
      <main className="flex-1 grid lg:grid-cols-2 gap-12 items-center px-4 sm:px-6 md:px-10 py-6 sm:py-10 max-w-6xl w-full mx-auto">
        {/* Hero copy */}
        <section className="hidden lg:block animate-fade-up">
          <span className="badge mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-gold" />
            Learn by questioning
          </span>
          <h1 className="font-display text-5xl xl:text-6xl leading-[1.05] text-fg">
            Think deeper.<br />
            <span className="gradient-text italic">Discover answers</span><br />
            on your own.
          </h1>
          <p className="mt-6 text-lg text-muted max-w-md leading-relaxed">
            An AI tutor that guides you with thoughtful questions instead of handing
            out solutions, the way Socrates taught.
          </p>
          <blockquote className="mt-10 pl-5 border-l-2 border-line-strong max-w-md">
            <p className="font-display italic text-muted">
              “I cannot teach anybody anything. I can only make them think.”
            </p>
            <footer className="mt-2 text-xs uppercase tracking-[0.2em] text-faint">Socrates</footer>
          </blockquote>
        </section>

        {/* Form card */}
        <section className="w-full max-w-md mx-auto lg:ml-auto animate-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="glass-card p-6 sm:p-8 md:p-10">
            {newAccount?.recovery_code ? (
              <RecoveryCodePanel
                code={newAccount.recovery_code}
                username={newAccount.student.username}
                title="Account ready. Save your recovery code"
                onContinue={() => navigate('/chat')}
              />
            ) : (
              <>
                <h2 className="font-display text-3xl text-fg">{tab === 'signin' ? 'Welcome back' : 'Create your account'}</h2>
                <p className="mt-2 text-sm text-muted">
                  {tab === 'signin' ? 'Sign in to continue your learning journey.' : 'Pick a username and password to get started.'}
                </p>

                {/* Tabs */}
                <div className="mt-6 grid grid-cols-2 p-1 rounded-xl bg-surface border border-line" role="tablist">
                  {(['signin', 'signup'] as Tab[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      role="tab"
                      aria-selected={tab === t}
                      onClick={() => switchTab(t)}
                      className={`py-2 rounded-lg text-sm font-medium transition-all ${
                        tab === t ? 'bg-elev text-fg shadow-sm ring-1 ring-line' : 'text-muted hover:text-fg'
                      }`}
                    >
                      {t === 'signin' ? 'Sign in' : 'Sign up'}
                    </button>
                  ))}
                </div>

                <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
                  {error && (
                    <div className="alert-error" role="alert">
                      <AlertCircle size={16} className="mt-0.5 shrink-0" />
                      <span>{error}</span>
                    </div>
                  )}

                  {tab === 'signup' && (
                    <div className="grid sm:grid-cols-2 gap-4">
                      <Field label="Name" icon={<User size={16} />} type="text" required autoComplete="name"
                        placeholder="Your full name" value={name} onChange={(e) => setName(e.target.value)} />
                      <Field label="Roll Number" icon={<Hash size={16} />} type="text" required
                        placeholder="e.g. 21CS1042" value={rollNo} onChange={(e) => setRollNo(e.target.value)} />
                    </div>
                  )}

                  <Field label="Username" icon={<AtSign size={16} />} type="text" required autoComplete="username"
                    placeholder={tab === 'signup' ? 'Choose a username' : 'Your username'}
                    minLength={tab === 'signup' ? 3 : undefined} maxLength={30}
                    pattern={tab === 'signup' ? '[A-Za-z0-9_.\\-]{3,30}' : undefined}
                    title="3-30 characters: letters, numbers, _ . -"
                    hint={tab === 'signup' ? '3-30 characters: letters, numbers, _ . - (not case-sensitive)' : undefined}
                    value={username} onChange={(e) => setUsername(e.target.value)} />

                  <Field label="Password" icon={<Lock size={16} />} type="password" required
                    autoComplete={tab === 'signup' ? 'new-password' : 'current-password'}
                    minLength={tab === 'signup' ? 8 : undefined}
                    placeholder={tab === 'signup' ? 'At least 8 characters' : 'Your password'}
                    value={password} onChange={(e) => setPassword(e.target.value)} />

                  {tab === 'signup' && (
                    <Field label="Confirm Password" icon={<Lock size={16} />} type="password" required autoComplete="new-password"
                      placeholder="Repeat your password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
                  )}

                  {tab === 'signin' && (
                    <div className="flex justify-end -mt-1">
                      <Link to="/forgot-password" className="text-sm link-accent">Forgot password?</Link>
                    </div>
                  )}

                  <button type="submit" disabled={loading} className="btn-primary w-full !py-3.5 group">
                    {loading ? (
                      <>
                        <Loader2 size={18} className="animate-spin" />
                        {tab === 'signin' ? 'Signing in...' : 'Creating account...'}
                      </>
                    ) : (
                      <>
                        {tab === 'signin' ? 'Start Learning' : 'Create Account'}
                        <ArrowRight size={18} className="transition-transform group-hover:translate-x-0.5" />
                      </>
                    )}
                  </button>
                </form>

                {tab === 'signup' ? (
                  <p className="mt-5 flex gap-2 text-xs text-faint">
                    <Info size={14} className="shrink-0 mt-px" />
                    Used Socratic Tutor before accounts existed? Sign up with the same name and roll number to keep your chat history.
                  </p>
                ) : (
                  <p className="mt-6 text-center text-sm text-muted">
                    New here?{' '}
                    <button type="button" onClick={() => switchTab('signup')} className="link-accent">Create an account</button>
                  </p>
                )}
              </>
            )}
          </div>
        </section>
      </main>
    </AuthLayout>
  );
}
