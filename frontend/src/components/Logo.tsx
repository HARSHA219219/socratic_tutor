import React from 'react';

/**
 * Socratic Tutor mark: the app icon (white "S" speech ribbon on a blue-violet tile).
 * The PNG already has its own rounded tile and transparent corners; size comes from className.
 */
export const LogoMark: React.FC<{ className?: string }> = ({ className = 'w-9 h-9' }) => (
  <img src="/logo.png" alt="" aria-hidden="true" draggable={false} className={`logo-img ${className}`} />
);

/** Mark + wordmark, used in page headers. */
export const Brand: React.FC<{ sub?: string; markClassName?: string }> = ({ sub = 'for IITGN', markClassName = 'w-9 h-9' }) => (
  <span className="flex items-center gap-3 min-w-0">
    <LogoMark className={`${markClassName} shrink-0`} />
    <span className="min-w-0 leading-tight">
      <span className="block font-display text-[17px] text-fg truncate">Socratic Tutor</span>
      {sub && <span className="block text-[10px] font-semibold uppercase tracking-[0.2em] text-faint">{sub}</span>}
    </span>
  </span>
);
