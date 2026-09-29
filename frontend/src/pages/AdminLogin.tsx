import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import { API_BASE_URL } from '../services/api';
import AuthLayout from '../components/AuthLayout';
import PasswordInput from '../components/PasswordInput';
import { ShieldCheck, ArrowLeft, ArrowRight, AlertCircle, User, Lock } from 'lucide-react';

const API_URL = API_BASE_URL;

const AdminLogin: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Ensure any stale token is removed when landing on the login page
  useEffect(() => {
    localStorage.removeItem('admin_token');
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      const payload = new URLSearchParams();
      payload.append('username', username);
      payload.append('password', password);

      const response = await axios.post(`${API_URL}/admin/login`, payload, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      const token = response.data.access_token;
      localStorage.setItem('admin_token', token);
      // after login, go to dashboard
      navigate('/admin/dashboard');
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Login failed');
    }
  };

  return (
    <AuthLayout
      headerRight={
        <Link to="/login" className="link-subtle">
          <ArrowLeft size={16} />
          <span className="hidden sm:inline">Back to student login</span>
        </Link>
      }
    >
      <main className="flex-1 flex items-center justify-center px-4 sm:px-6 py-6 sm:pb-16">
        <div className="w-full max-w-md animate-fade-up">
          <div className="glass-card p-6 sm:p-8 md:p-10">
            <div className="flex flex-col items-center text-center">
              <span className="logo-mark w-14 h-14 mb-5">
                <ShieldCheck size={26} />
              </span>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold">Instructor Portal</p>
              <h2 className="font-display text-3xl text-fg mt-2">Admin Login</h2>
              <p className="mt-2 text-sm text-muted">
                Manage tutor configuration and review student conversations.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="mt-8 space-y-5">
              {error && (
                <div className="alert-error">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}
              <div>
                <label className="field-label">Username</label>
                <div className="relative">
                  <User size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Instructor username"
                    autoComplete="username"
                    className="input-premium !pl-11"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="field-label" htmlFor="admin-password">Password</label>
                <div className="relative">
                  <Lock size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-faint pointer-events-none z-10" />
                  <PasswordInput
                    id="admin-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    autoComplete="current-password"
                    className="input-premium !pl-11"
                    required
                  />
                </div>
              </div>
              <div className="flex justify-end -mt-1">
                <Link to="/admin/forgot-password" className="text-sm link-accent">Forgot password?</Link>
              </div>
              <button type="submit" className="btn-primary w-full !py-3.5 group">
                Login
                <ArrowRight size={18} className="transition-transform group-hover:translate-x-0.5" />
              </button>
            </form>
          </div>
        </div>
      </main>
    </AuthLayout>
  );
};

export default AdminLogin;
