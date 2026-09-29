import { useSyncExternalStore } from 'react';

export type Mode = 'light' | 'dark';
export type Palette = 'iris' | 'ocean' | 'sunset' | 'forest' | 'saffron' | 'plum' | 'graphite';

export const PALETTES: { id: Palette; label: string; colors: [string, string] }[] = [
  { id: 'iris', label: 'Iris', colors: ['#4f46e5', '#7c3aed'] },
  { id: 'ocean', label: 'Ocean', colors: ['#0f766e', '#1d4ed8'] },
  { id: 'sunset', label: 'Sunset', colors: ['#e11d48', '#c2410c'] },
  { id: 'forest', label: 'Forest', colors: ['#047857', '#15803d'] },
  { id: 'saffron', label: 'Saffron', colors: ['#c2410c', '#b45309'] },
  { id: 'plum', label: 'Plum', colors: ['#a21caf', '#7e22ce'] },
  { id: 'graphite', label: 'Graphite', colors: ['#334155', '#1d4ed8'] },
];

const MODE_KEY = 'theme-mode';
const PALETTE_KEY = 'theme-palette';

const read = <T extends string>(key: string, allowed: readonly T[], fallback: T): T => {
  try {
    const v = localStorage.getItem(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
};

let state = {
  mode: read<Mode>(MODE_KEY, ['light', 'dark'], 'light'),
  palette: read<Palette>(PALETTE_KEY, PALETTES.map((p) => p.id), 'ocean'),
};
const listeners = new Set<() => void>();

const apply = () => {
  const root = document.documentElement;
  root.dataset.mode = state.mode;
  root.dataset.palette = state.palette;
};
apply();

const update = (next: Partial<typeof state>) => {
  state = { ...state, ...next };
  try {
    localStorage.setItem(MODE_KEY, state.mode);
    localStorage.setItem(PALETTE_KEY, state.palette);
  } catch {
    // storage unavailable: theme still applies for this visit
  }
  apply();
  listeners.forEach((l) => l());
};

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function useTheme() {
  const snapshot = useSyncExternalStore(subscribe, () => state);
  return {
    ...snapshot,
    setMode: (mode: Mode) => update({ mode }),
    toggleMode: () => update({ mode: state.mode === 'light' ? 'dark' : 'light' }),
    setPalette: (palette: Palette) => update({ palette }),
  };
}
