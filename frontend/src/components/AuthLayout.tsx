import React from 'react';
import { Link } from 'react-router-dom';
import { Brand } from './Logo';
import ThemeSwitcher from './ThemeSwitcher';

/** Shared chrome for public pages (landing, student/instructor sign-in): full-width header + footer. */
const AuthLayout: React.FC<{ children: React.ReactNode; headerRight?: React.ReactNode }> = ({ children, headerRight }) => (
  <div className="premium-bg min-h-[100dvh] flex flex-col">
    <header className="w-full flex items-center justify-between gap-2 px-4 sm:px-6 md:px-10 py-4 sm:py-5">
      <Link to="/" className="min-w-0 shrink">
        <Brand />
      </Link>
      <div className="flex items-center gap-1.5 sm:gap-3 shrink-0">
        {headerRight}
        <ThemeSwitcher />
      </div>
    </header>

    <div className="flex-1 flex flex-col">{children}</div>

    <footer className="w-full border-t border-line px-4 sm:px-6 md:px-10 py-4 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-faint">
      <p className="text-center sm:text-left">
        © {new Date().getFullYear()} Socratic Tutor · Built for IITGN students
      </p>
      <nav className="flex items-center gap-4">
        <Link to="/login" className="hover:text-fg transition-colors">Student sign in</Link>
        <Link to="/admin" className="hover:text-fg transition-colors">Instructor login</Link>
      </nav>
    </footer>
  </div>
);

export default AuthLayout;
