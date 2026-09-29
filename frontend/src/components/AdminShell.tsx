import React from 'react';
import { NavLink, Link } from 'react-router-dom';
import { Settings2, Users, LogOut, Loader2, AlertCircle } from 'lucide-react';
import { LogoMark } from './Logo';
import ThemeSwitcher from './ThemeSwitcher';

// Shared visual chrome for admin pages (presentation only).
const navClass = ({ isActive }: { isActive: boolean }) =>
  `inline-flex items-center gap-2 px-2.5 sm:px-3.5 py-2 rounded-xl text-sm font-medium transition-colors ${
    isActive
      ? 'bg-accent-soft text-fg border border-line'
      : 'text-muted hover:text-fg hover:bg-surface-2 border border-transparent'
  }`;

export const AdminShell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="premium-bg min-h-screen">
    <header className="sticky top-0 z-30 border-b border-line bg-[var(--header-bg)] backdrop-blur-xl">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-2 sm:gap-4">
        <Link to="/admin/dashboard" className="flex items-center gap-2 sm:gap-3 min-w-0">
          <LogoMark className="w-8 h-8" />
          <span className="font-display text-lg text-fg hidden sm:inline">Socratic Tutor</span>
          <span className="badge !text-[10px] uppercase tracking-[0.14em] hidden min-[380px]:inline-flex">Admin</span>
        </Link>
        <nav className="flex items-center gap-0.5 sm:gap-1 shrink-0">
          <NavLink to="/admin/dashboard" className={navClass}>
            <Settings2 size={15} />
            <span className="hidden sm:inline">Configuration</span>
          </NavLink>
          <NavLink to="/admin/logs" className={navClass}>
            <Users size={15} />
            <span className="hidden sm:inline">Student Logs</span>
          </NavLink>
          <span className="mx-0.5 sm:mx-1 h-6 w-px bg-[var(--border)]" />
          <ThemeSwitcher />
          <Link to="/admin" title="Sign out" aria-label="Sign out" className=" p-2 rounded-xl text-faint hover:text-fg hover:bg-surface-2 transition-colors">
            <LogOut size={16} />
          </Link>
        </nav>
      </div>
    </header>
    <main className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-10 animate-fade-up">{children}</main>
  </div>
);

export const PageHeader: React.FC<{
  eyebrow?: string;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}> = ({ eyebrow, title, subtitle, actions }) => (
  <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
    <div>
      {eyebrow && (
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-gold mb-2">{eyebrow}</p>
      )}
      <h1 className="font-display text-3xl md:text-4xl text-fg">{title}</h1>
      {subtitle && <p className="mt-2 text-muted">{subtitle}</p>}
    </div>
    {actions}
  </div>
);

export const LoadingState: React.FC<{ label?: string }> = ({ label = 'Loading...' }) => (
  <div className="premium-bg min-h-screen flex items-center justify-center">
    <div className="flex items-center gap-3 text-muted">
      <Loader2 size={20} className="animate-spin text-accent" />
      {label}
    </div>
  </div>
);

export const ErrorState: React.FC<{ message: string }> = ({ message }) => (
  <div className="premium-bg min-h-screen flex items-center justify-center p-6">
    <div className="glass-card p-8 max-w-md w-full text-center">
      <span className="inline-flex items-center justify-center w-12 h-12 rounded-2xl bg-[var(--danger-bg)] text-[var(--danger-fg)] mb-4">
        <AlertCircle size={22} />
      </span>
      <p className="font-display text-xl text-fg">Something went wrong</p>
      <p className="mt-2 text-sm text-muted">Error: {message}</p>
    </div>
  </div>
);
