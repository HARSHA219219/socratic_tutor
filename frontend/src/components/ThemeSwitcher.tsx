import React, { useEffect, useRef, useState } from 'react';
import { Moon, Sun, Palette as PaletteIcon, Check } from 'lucide-react';
import { PALETTES, useTheme } from '../theme';

/** Light/dark toggle + palette picker. `placement` controls which way the menu opens. */
const ThemeSwitcher: React.FC<{ placement?: 'down' | 'up' }> = ({ placement = 'down' }) => {
  const { mode, palette, toggleMode, setPalette } = useTheme();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', close);
    return () => {
      document.removeEventListener('mousedown', close);
      document.removeEventListener('keydown', close);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative flex items-center gap-1">
      <button
        type="button"
        onClick={toggleMode}
        className="icon-btn"
        title={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        aria-label={mode === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
      >
        {mode === 'light' ? <Moon size={17} /> : <Sun size={17} />}
      </button>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="icon-btn"
        title="Color theme"
        aria-label="Color theme"
        aria-expanded={open}
      >
        <PaletteIcon size={17} />
      </button>

      {open && (
        <div
          role="menu"
          className={`absolute right-0 z-50 w-56 glass-card !bg-elev !rounded-2xl p-2 animate-fade-up ${
            placement === 'up' ? 'bottom-full mb-2' : 'top-full mt-2'
          }`}
        >
          <p className="px-2 pt-1 pb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-faint">Color theme</p>
          {PALETTES.map((p) => (
            <button
              key={p.id}
              role="menuitemradio"
              aria-checked={palette === p.id}
              onClick={() => { setPalette(p.id); setOpen(false); }}
              className={`w-full flex items-center gap-3 px-2 py-2 rounded-xl text-sm transition-colors ${
                palette === p.id ? 'bg-accent-soft text-fg' : 'text-muted hover:bg-surface-2 hover:text-fg'
              }`}
            >
              <span
                className="w-6 h-6 rounded-full ring-1 ring-black/10 shrink-0"
                style={{ background: `linear-gradient(135deg, ${p.colors[0]}, ${p.colors[1]})` }}
              />
              <span className="font-medium">{p.label}</span>
              {palette === p.id && <Check size={16} className="ml-auto text-accent" />}
            </button>
          ))}
          <div className="mt-1 pt-2 border-t border-line flex gap-1">
            {(['light', 'dark'] as const).map((m) => (
              <button
                key={m}
                onClick={() => { if (m !== mode) toggleMode(); }}
                className={`flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  mode === m ? 'bg-accent-soft text-accent' : 'text-muted hover:bg-surface-2'
                }`}
              >
                {m === 'light' ? <Sun size={13} /> : <Moon size={13} />}
                {m === 'light' ? 'Light' : 'Dark'}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ThemeSwitcher;
