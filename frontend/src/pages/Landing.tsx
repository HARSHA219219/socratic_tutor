import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Camera, Lightbulb, ShieldCheck } from 'lucide-react';
import { LogoMark } from '../components/Logo';
import AuthLayout from '../components/AuthLayout';
import { getStudentToken } from '../services/api';

type DemoLine = { role: 'user' | 'tutor' | 'hint'; text: string; badge?: string };

// Scripted conversation for the hero demo
const DEMO: DemoLine[] = [
  { role: 'user', text: 'Why does ice float on water?' },
  { role: 'tutor', text: 'Great question! What do you know about the density of ice compared to liquid water?' },
  { role: 'user', text: "Isn't ice heavier because it's solid?" },
  { role: 'tutor', text: 'Interesting guess. If ice were denser, what would you see when you drop a cube into a glass?' },
  { role: 'hint', text: 'Asked for hint 1 of 3' },
  { role: 'tutor', badge: 'Hint 1 · Nudge', text: 'Think about how water molecules arrange themselves when they freeze. Closer together, or further apart?' },
  { role: 'user', text: 'Further apart, in a lattice! So ice is less dense and floats.' },
  { role: 'tutor', text: 'Exactly. You just reasoned it out yourself. 🎉' },
];

const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function DemoChat() {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? DEMO.length : 0));
  // The tutor "types" while its next line is pending
  const typing = shown < DEMO.length && DEMO[shown].role === 'tutor';

  useEffect(() => {
    if (prefersReducedMotion()) return;
    const delay = shown >= DEMO.length ? 4500 : typing ? 1400 : shown === 0 ? 700 : 1300;
    const t = setTimeout(() => setShown(s => (s >= DEMO.length ? 0 : s + 1)), delay);
    return () => clearTimeout(t);
  }, [shown, typing]);

  return (
    <div className="glass-card !rounded-3xl overflow-hidden">
      {/* window chrome */}
      <div className="flex items-center gap-2 px-4 h-11 border-b border-line bg-surface">
        <span className="w-2.5 h-2.5 rounded-full bg-[#ff5f57]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#febc2e]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-xs font-medium text-muted truncate">Why ice floats · Physics</span>
      </div>
      <div className="h-[340px] sm:h-[420px] overflow-hidden px-4 sm:px-5 py-5 flex flex-col justify-end gap-3">
        {DEMO.slice(Math.max(0, shown - 6), shown).map((line, j) => {
          const i = Math.max(0, shown - 6) + j; // stable key: position in the script
          if (line.role === 'hint') {
            return (
              <div key={i} className="flex justify-end animate-fade-up">
                <span className="help-pill"><Lightbulb size={12} /> {line.text}</span>
              </div>
            );
          }
          if (line.role === 'user') {
            return (
              <div key={i} className="flex justify-end animate-fade-up">
                <div className="msg-user max-w-[80%] rounded-2xl rounded-br-md px-3.5 py-2.5 text-sm leading-relaxed">{line.text}</div>
              </div>
            );
          }
          return (
            <div key={i} className="flex gap-2.5 animate-fade-up">
              <LogoMark className="w-7 h-7 shrink-0" />
              <div className="max-w-[85%]">
                {line.badge && (
                  <span className="help-badge mb-1"><Lightbulb size={10} /> {line.badge}</span>
                )}
                <div className={`msg-tutor ${line.badge ? 'msg-hint' : ''} rounded-2xl rounded-tl-md px-3.5 py-2.5 text-sm leading-relaxed`}>
                  {line.text}
                </div>
              </div>
            </div>
          );
        })}
        {typing && (
          <div className="flex gap-2.5">
            <LogoMark className="w-7 h-7 shrink-0" />
            <div className="msg-tutor rounded-2xl rounded-tl-md px-3.5 py-3 flex gap-1">
              <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
            </div>
          </div>
        )}
      </div>
      <div className="px-4 pb-4">
        <div className="composer rounded-2xl flex items-center gap-2 px-4 py-3 text-sm text-faint">
          <span className="flex-1 truncate">Ask anything, or share how you are thinking about it...</span>
          <span className="btn-primary !p-0 !w-8 !h-8 !rounded-xl"><ArrowRight size={15} /></span>
        </div>
      </div>
    </div>
  );
}

export default function Landing() {
  const signedIn = !!getStudentToken();

  return (
    <AuthLayout
      headerRight={
        signedIn ? (
          <Link to="/chat" className="btn-primary !py-2 !px-3 sm:!px-4 !text-sm">Open chats</Link>
        ) : (
          <>
            <Link to="/admin" className="hidden md:inline-flex link-subtle">
              <ShieldCheck size={16} />
              Instructor login
            </Link>
            <Link to="/login" className="hidden sm:inline-flex btn-ghost !py-2 !text-sm">Sign in</Link>
            <Link to="/login?mode=signup" className="btn-primary !py-2 !px-3 sm:!px-4 !text-sm whitespace-nowrap">Get started</Link>
          </>
        )
      }
    >
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-6 md:px-10 py-8 sm:py-12 grid lg:grid-cols-[1.05fr_1fr] gap-10 lg:gap-12 items-center">
        <section className="animate-fade-up text-center lg:text-left">
          <span className="badge mb-5 sm:mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-gold" />
            Made for IIT Gandhinagar students
          </span>
          <h1 className="font-display text-[2.1rem] leading-[1.08] sm:text-5xl lg:text-6xl sm:leading-[1.04] text-fg">
            Don't just get answers.<br />
            <span className="gradient-text italic">Learn to find them.</span>
          </h1>
          <p className="mt-5 sm:mt-6 text-base sm:text-lg text-muted max-w-xl mx-auto lg:mx-0 leading-relaxed">
            An AI tutor that teaches the way Socrates did, by asking you the right questions.
            Stuck? Climb the hint ladder one step at a time, or reveal the answer when you need it.
          </p>
          <div className="mt-7 sm:mt-8 flex flex-col sm:flex-row items-stretch sm:items-center justify-center lg:justify-start gap-3">
            <Link to={signedIn ? '/chat' : '/login?mode=signup'} className="btn-primary !px-6 !py-3.5 group">
              {signedIn ? 'Continue learning' : 'Start learning free'}
              <ArrowRight size={18} className="transition-transform group-hover:translate-x-0.5" />
            </Link>
            {!signedIn && (
              <Link to="/login" className="btn-ghost !px-5 !py-3.5">I already have an account</Link>
            )}
          </div>
          <div className="mt-7 sm:mt-8 flex flex-wrap items-center justify-center lg:justify-start gap-x-6 gap-y-2 text-sm text-faint">
            <span className="inline-flex items-center gap-1.5"><ShieldCheck size={15} className="text-accent" /> No email needed</span>
            <span className="inline-flex items-center gap-1.5"><Camera size={15} className="text-accent" /> Photo doubts</span>
            <span className="inline-flex items-center gap-1.5"><Lightbulb size={15} className="text-accent" /> Step-by-step hints</span>
          </div>
        </section>
        <section className="animate-fade-up w-full max-w-xl mx-auto lg:max-w-none" style={{ animationDelay: '120ms' }}>
          <DemoChat />
        </section>
      </main>
    </AuthLayout>
  );
}
