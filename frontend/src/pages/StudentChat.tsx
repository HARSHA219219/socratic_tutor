import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  getStudentSessions, createSession, getSessionMessages, streamChat, fetchStudentImage, fetchStudentDocument,
  createCheckpoint, getSessionCheckpoints, continueFromCheckpoint,
  fetchAttachment,
  getStudentToken, clearStudentSession, errorDetail,
} from '../services/api';
import type { Session, Message, Checkpoint, LocalAttachment } from '../types/api';
import type { StreamRequest } from '../services/api';
import { streamingId, startStream, applySavedUser, appendChunk, completeStream, failStream } from '../services/chatStream';
import {
  MessageSquare, ArrowUp, LogOut, ImagePlus, X, Menu, AlertCircle, PanelLeftClose,
  Atom, Code2, Sigma, PenLine, Copy, Check, ArrowDown, Search, SquarePen, Lightbulb, Eye, Paperclip, BookmarkPlus, BookmarkCheck, Loader2, History,
} from 'lucide-react';
import ThemeSwitcher from '../components/ThemeSwitcher';
import AuthImage from '../components/AuthImage';
import DocumentCard from '../components/DocumentCard';
import MessageAttachments from '../components/MessageAttachments';
import Markdown from '../components/Markdown';
import { checkNewFiles, classifyFile, formatBytes, MAX_ATTACHMENTS, MAX_TOTAL_ATTACHMENT_BYTES } from '../services/attachmentRules';
import type { AttachmentKind } from '../services/attachmentRules';
import CheckpointModal from '../components/CheckpointModal';
import { LogoMark } from '../components/Logo';

// The hint planner decides how many hints a question gets (1-6); older hints had a fixed ladder of 3
const LEGACY_HINT_TOTAL = 3;
const hintLevel = (kind?: string | null) => (kind?.startsWith('hint-') ? Number(kind.slice(5)) || 0 : 0);
const isHintKind = (kind?: string | null) => !!kind?.startsWith('hint-');
const hintTotalOf = (m: Message) => m.hint_total || Math.max(LEGACY_HINT_TOTAL, hintLevel(m.kind));
const hintStage = (level: number, total: number) =>
  level <= 1 ? 'Nudge' : level >= total ? 'Final hint' : level / total <= 0.5 ? 'Key idea' : 'Next step';

const SUGGESTIONS = [
  { icon: Atom, tag: 'Physics', text: 'Why do objects fall at the same rate?' },
  { icon: Code2, tag: 'Programming', text: 'Help me understand recursion' },
  { icon: Sigma, tag: 'Mathematics', text: 'Why does integration by parts work?' },
  { icon: PenLine, tag: 'Writing', text: 'What makes a good thesis statement?' },
];

type PendingAttachment = { id: string; file: File; kind: AttachmentKind; previewUrl?: string };

// Ids for optimistic messages until the server's copy replaces them
let tempCounter = 0;
const newTempId = (prefix: string) => `${prefix}-${Date.now()}-${++tempCounter}`;

// Backend timestamps are UTC without an offset; treat them as UTC
const parseTs = (iso: string) => new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);

const groupLabel = (iso: string) => {
  const d = parseTs(iso);
  const today = new Date();
  const days = Math.floor((new Date(today.toDateString()).getTime() - new Date(d.toDateString()).getTime()) / 86400000);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return 'Previous 7 days';
  return 'Older';
};

const shortTime = (iso: string) => {
  const d = parseTs(iso);
  const mins = Math.floor((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return 'now';
  if (mins < 60) return `${mins}m`;
  if (mins < 60 * 24) return `${Math.floor(mins / 60)}h`;
  if (mins < 60 * 24 * 7) return d.toLocaleDateString(undefined, { weekday: 'short' });
  return d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
};

const clockTime = (iso: string) => parseTs(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });

const greeting = () => {
  const h = new Date().getHours();
  if (h < 5) return 'Burning the midnight oil';
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
};

export default function StudentChat() {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  // Files chosen for the next message (images and/or documents)
  const [pending, setPending] = useState<PendingAttachment[]>([]);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [creatingCp, setCreatingCp] = useState<string | null>(null);
  const [cpError, setCpError] = useState<{ id: string; text: string } | null>(null);
  const [viewingCp, setViewingCp] = useState<Checkpoint | null>(null);
  const [viewingContext, setViewingContext] = useState<string | null>(null);
  const [continuing, setContinuing] = useState(false);
  const [error, setError] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [query, setQuery] = useState('');
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showJump, setShowJump] = useState(false);
  const [confirmAnswer, setConfirmAnswer] = useState(false);

  const studentId = localStorage.getItem('studentId');
  const studentName = localStorage.getItem('studentName');
  const studentUsername = localStorage.getItem('studentUsername');
  const hasToken = !!getStudentToken();
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docInputRef = useRef<HTMLInputElement>(null);
  const pendingRef = useRef<PendingAttachment[]>([]);
  useEffect(() => { pendingRef.current = pending; }, [pending]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const autoCreatedRef = useRef(false);

  useEffect(() => {
    if (!studentId || !hasToken) {
      clearStudentSession();
      navigate('/login');
      return;
    }
    loadSessions();
  }, [studentId]);

  useEffect(() => {
    if (currentSessionId) {
      loadMessages(currentSessionId);
      getSessionCheckpoints(currentSessionId).then(setCheckpoints).catch(() => {});
    }
  }, [currentSessionId]);

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    const el = scrollRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior });
  };

  useEffect(() => {
    // Follow a streaming reply only if the student hasn't scrolled up to read
    const streamingNow = messages.some(m => m.streaming);
    const el = scrollRef.current;
    const nearBottom = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 400;
    if (!streamingNow || nearBottom) scrollToBottom(streamingNow ? 'auto' : 'smooth');
  }, [messages, loading]);

  // Auto-grow the composer
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [inputValue]);

  // Free the local preview URL when it changes
  // Release previews of files still waiting to be sent when leaving the page
  useEffect(() => () => { pendingRef.current.forEach(p => p.previewUrl && URL.revokeObjectURL(p.previewUrl)); }, []);

  const loadSessions = async () => {
    if (!studentId) return;
    try {
      const data = await getStudentSessions(studentId);
      setSessions(data);
      if (data.length > 0 && !currentSessionId) {
        setCurrentSessionId(data[0].id);
      } else if (data.length === 0 && !autoCreatedRef.current) {
        // First visit: open a fresh chat (guarded against StrictMode's double effect)
        autoCreatedRef.current = true;
        await handleNewChat();
      }
    } catch (err) {
      console.error('Failed to load sessions', err);
    }
  };

  const loadMessages = async (sessionId: string) => {
    try {
      const data = await getSessionMessages(sessionId);
      setMessages(data);
    } catch (err) {
      console.error('Failed to load messages', err);
    }
  };

  // Summarize the conversation through a completed exchange (the tutor reply `replyId`)
  const handleCreateCheckpoint = async (studentMsgId: string, replyId: string) => {
    if (!currentSessionId || creatingCp) return;
    setCreatingCp(studentMsgId);
    setCpError(null);
    try {
      const cp = await createCheckpoint(currentSessionId, replyId);
      setCheckpoints(prev => [...prev, cp]);
    } catch (err) {
      setCpError({ id: studentMsgId, text: errorDetail(err, 'Could not create the checkpoint. Please try again.') });
    } finally {
      setCreatingCp(null);
    }
  };

  const handleContinue = async (cp: Checkpoint) => {
    setContinuing(true);
    try {
      const session = await continueFromCheckpoint(cp.id);
      setSessions(prev => [session, ...prev]);
      setViewingCp(null);
      setCurrentSessionId(session.id);
    } catch (err) {
      setError(errorDetail(err, 'Could not continue from this checkpoint.'));
      setViewingCp(null);
    } finally {
      setContinuing(false);
    }
  };

  const handleNewChat = async () => {
    if (!studentId) return;
    try {
      const session = await createSession(studentId);
      setSessions(prev => [session, ...prev]);
      setCurrentSessionId(session.id);
      setMessages([]);
      setSidebarOpen(false);
    } catch (err) {
      console.error('Failed to create session', err);
    }
  };

  // Validates new files against the per-file, count and total-size limits (the server re-checks)
  const addFiles = (files: File[]) => {
    if (!files.length) return;
    const { accepted, errors } = checkNewFiles(pending.map(p => p.file), files);
    setError(errors.join(' '));
    if (!accepted.length) return;
    setPending(prev => [
      ...prev,
      ...accepted.map(file => {
        const kind = classifyFile(file) as AttachmentKind;
        return { id: newTempId('att'), file, kind, previewUrl: kind === 'image' ? URL.createObjectURL(file) : undefined };
      }),
    ]);
  };

  const removePending = (id: string) => {
    setPending(prev => {
      const gone = prev.find(p => p.id === id);
      if (gone?.previewUrl) URL.revokeObjectURL(gone.previewUrl);
      return prev.filter(p => p.id !== id);
    });
  };

  const onFilesChosen = (e: React.ChangeEvent<HTMLInputElement>) => {
    addFiles(Array.from(e.target.files || []));
    e.target.value = ''; // allow picking the same file again
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    e?.preventDefault();
    if ((!inputValue.trim() && !pending.length) || !currentSessionId || loading) return;

    const userMessageText = inputValue.trim();
    const sent = pending;
    // Previews move to the sent message (not revoked) so they show while the upload finishes
    const localAttachments: LocalAttachment[] = sent.map(p => ({
      name: p.file.name, size: p.file.size, mime: p.file.type, kind: p.kind, previewUrl: p.previewUrl,
    }));
    setInputValue('');
    setPending([]);
    setError('');

    // Optimistic UI update
    const tempId = newTempId('local');
    const tempUserMessage: Message = {
      id: tempId,
      session_id: currentSessionId,
      role: 'user',
      content: userMessageText,
      timestamp: new Date().toISOString(),
      local_attachments: localAttachments.length ? localAttachments : undefined,
    };

    let request: StreamRequest;
    if (sent.length) {
      const form = new FormData();
      form.append('session_id', currentSessionId);
      form.append('message', userMessageText);
      sent.forEach(p => form.append('files', p.file)); // the browser sets the multipart boundary
      request = { type: 'attachments', form };
    } else {
      request = { type: 'json', body: { session_id: currentSessionId, message: userMessageText, mode: 'normal' } };
    }

    const userSaved = await runStream(request, tempUserMessage, null);
    if (!userSaved.current) {
      // The server never stored the message: put the draft back so the student can retry
      setInputValue(userMessageText);
      setPending(sent);
    }
  };

  /**
   * Streams one tutor turn into the chat. The tutor message appears immediately and grows
   * as chunks arrive; on completion it is replaced by the saved server copy (no duplicates).
   * Returns whether the server saved the student's message, so callers can restore drafts.
   */
  const runStream = async (request: StreamRequest, userTemp: Message, kind: string | null) => {
    const sessionId = userTemp.session_id;
    const assistantTempId = streamingId(userTemp.id);
    const userSaved = { current: false };
    setMessages(prev => startStream(prev, userTemp, assistantTempId, kind));
    setLoading(true);
    try {
      await streamChat(request, event => {
        if ((event.type === 'start' || event.type === 'user_message') && event.user_message) {
          userSaved.current = true;
          const saved = event.user_message;
          setMessages(prev => applySavedUser(prev, userTemp.id, assistantTempId, saved));
        } else if (event.type === 'chunk') {
          setMessages(prev => appendChunk(prev, assistantTempId, event.text));
        } else if (event.type === 'complete') {
          userSaved.current = true;
          setMessages(prev => completeStream(prev, userTemp.id, assistantTempId, event));
          if (event.session_title) {
            setSessions(prev => prev.map(s => (s.id === sessionId ? { ...s, title: event.session_title } : s)));
          }
        }
      });
    } catch (err) {
      console.error('Streaming failed', err);
      setMessages(prev => failStream(prev, userTemp.id, assistantTempId));
      setError(errorDetail(err, 'The tutor could not respond. Please try again.'));
    } finally {
      setLoading(false);
    }
    return userSaved;
  };

  // Hint ladder / direct answer: no typed text, the server works out the hint level
  const askTutor = async (mode: 'hint' | 'answer') => {
    if (!currentSessionId || loading) return;
    setConfirmAnswer(false);
    setError('');
    const tempId = newTempId('help');
    const kind = mode === 'hint' ? 'hint-0' : 'answer';
    const optimistic: Message = {
      id: tempId,
      session_id: currentSessionId,
      role: 'user',
      content: '',
      timestamp: new Date().toISOString(),
      kind,
    };
    await runStream({ type: 'json', body: { session_id: currentSessionId, mode } }, optimistic, kind);
  };

  // First click arms the button, second click (within 4s) reveals the answer
  const handleAnswerClick = () => {
    if (confirmAnswer) {
      askTutor('answer');
      return;
    }
    setConfirmAnswer(true);
    setTimeout(() => setConfirmAnswer(false), 4000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    const images = Array.from(e.clipboardData.files).filter(f => f.type.startsWith('image/'));
    if (images.length) {
      e.preventDefault();
      addFiles(images);
    }
  };

  const copyMessage = async (msg: Message) => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopiedId(msg.id);
      setTimeout(() => setCopiedId(id => (id === msg.id ? null : id)), 1500);
    } catch {
      // clipboard blocked; nothing to do
    }
  };

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowJump(el.scrollHeight - el.scrollTop - el.clientHeight > 240);
  };

  if (!studentId) return null;

  const initial = (studentName || '?').trim().charAt(0).toUpperCase();
  const firstName = studentName ? studentName.split(' ')[0] : '';
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const canSend = (!!inputValue.trim() || pending.length > 0) && !!currentSessionId && !loading;
  const pendingBytes = pending.reduce((sum, p) => sum + p.file.size, 0);

  // Current hint ladder (mirrors the server): the latest tutor hint since the last revealed answer
  let lastHintIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.kind === 'answer') break;
    if (m.role === 'assistant' && hintLevel(m.kind)) { lastHintIdx = i; break; }
  }
  const lastHint = lastHintIdx >= 0 ? messages[lastHintIdx] : null;
  const hintsUsed = lastHint ? hintLevel(lastHint.kind) : 0;
  const hintTotal = lastHint ? hintTotalOf(lastHint) : 0;
  const wroteSinceHint = messages.slice(lastHintIdx + 1).some(m => m.role === 'user' && !m.kind);
  const ladderDone = !!lastHint && hintsUsed >= hintTotal;
  const ladderActive = !!lastHint && !(ladderDone && wroteSinceHint);
  const hintsLeft = !ladderDone || wroteSinceHint;
  const nextHint = ladderActive ? hintsUsed + 1 : 1;
  // The planner may decide the answer button shouldn't be offered yet for this question
  const allowAnswer = !ladderActive || lastHint?.hint_allow_answer !== false;
  const hasQuestion = messages.some(m => m.role === 'user' && !m.kind);
  // Only this chat's checkpoints (the list may briefly hold the previous chat's while loading)
  const sessionCheckpoints = checkpoints.filter(c => c.session_id === currentSessionId);

  const visibleSessions = query.trim()
    ? sessions.filter(s => (s.title || 'Untitled chat').toLowerCase().includes(query.trim().toLowerCase()))
    : sessions;
  const grouped: [string, Session[]][] = [];
  visibleSessions.forEach(s => {
    const label = groupLabel(s.started_at);
    const group = grouped.find(g => g[0] === label);
    if (group) group[1].push(s);
    else grouped.push([label, [s]]);
  });

  return (
    <div className="flex h-[100dvh] bg-bg text-fg overflow-hidden">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/40 backdrop-blur-[2px] md:hidden" onClick={() => setSidebarOpen(false)} />
      )}

      {/* ---------------- Sidebar ---------------- */}
      <aside
        className={`chat-sidebar fixed md:static inset-y-0 left-0 z-40 w-[288px] shrink-0 flex flex-col border-r border-line transition-transform duration-300 md:translate-x-0 ${
          sidebarOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'
        }`}
      >
        {/* Brand */}
        <div className="px-4 pt-5 pb-4 flex items-center gap-3">
          <LogoMark className="w-9 h-9" />
          <div className="min-w-0">
            <h2 className="font-display text-[17px] text-fg leading-tight">Socratic Tutor</h2>
            <p className="text-[10px] uppercase tracking-[0.22em] text-faint">Think · Question · Learn</p>
          </div>
          <button onClick={() => setSidebarOpen(false)} className="icon-btn ml-auto md:hidden" aria-label="Close sidebar">
            <PanelLeftClose size={18} />
          </button>
        </div>

        {/* New chat + search */}
        <div className="px-3 space-y-2">
          <button
            onClick={handleNewChat}
            className="group w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold text-fg bg-elev border border-line shadow-sm hover:border-line-strong hover:shadow-md transition-all"
          >
            <span className="flex items-center justify-center w-7 h-7 rounded-lg bg-gradient-to-br from-fill-1 to-fill-2 text-white shadow-sm">
              <SquarePen size={14} />
            </span>
            New chat
          </button>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-faint pointer-events-none" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search chats"
              className="chat-search"
              aria-label="Search chats"
            />
          </div>
        </div>

        {/* Conversations */}
        <nav className="flex-1 overflow-y-auto px-3 pt-3 pb-3">
          {grouped.length === 0 && (
            <p className="px-3 py-6 text-center text-xs text-faint">{query ? 'No chats match your search.' : 'No chats yet.'}</p>
          )}
          {grouped.map(([label, items]) => (
            <div key={label} className="mb-4">
              <p className="px-3 pb-1.5 text-[10.5px] font-semibold uppercase tracking-[0.16em] text-faint">{label}</p>
              <div className="space-y-0.5">
                {items.map(session => {
                  const active = currentSessionId === session.id;
                  return (
                    <button
                      key={session.id}
                      onClick={() => { setCurrentSessionId(session.id); setSidebarOpen(false); setError(''); }}
                      className={`group relative w-full flex items-center gap-2.5 px-3 py-2 text-left rounded-xl transition-all ${
                        active ? 'chat-item-active' : 'text-muted hover:bg-surface-2 hover:text-fg'
                      }`}
                    >
                      {active && <span className="absolute -left-3 top-2 bottom-2 w-[3px] rounded-r-full bg-gradient-to-b from-fill-1 to-fill-2" />}
                      <MessageSquare size={14} className={active ? 'text-accent shrink-0' : 'text-faint shrink-0'} />
                      <span className="flex-1 truncate text-[13.5px] font-medium">
                        {session.title || 'New chat'}
                      </span>
                      <span className="shrink-0 text-[10.5px] text-faint tabular-nums">{shortTime(session.started_at)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* Profile */}
        <div className="p-3">
          <div className="flex items-center gap-3 p-2.5 rounded-2xl bg-elev border border-line shadow-sm">
            <span className="relative">
              <span className="avatar w-9 h-9 text-sm">{initial}</span>
              <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-emerald-500 ring-2 ring-[var(--bg-elev)]" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-fg truncate">{studentName}</p>
              <p className="text-xs text-faint truncate">@{studentUsername}</p>
            </div>
            <button
              onClick={() => {
                clearStudentSession();
                navigate('/');
              }}
              title="Sign out"
              aria-label="Sign out"
              className="icon-btn !w-8 !h-8"
            >
              <LogOut size={15} />
            </button>
          </div>
        </div>
      </aside>

      {/* ---------------- Main chat area ---------------- */}
      <main
        className="flex-1 flex flex-col min-w-0 relative isolate overflow-hidden"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={(e) => { if (e.currentTarget === e.target) setDragging(false); }}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(Array.from(e.dataTransfer.files || []));
        }}
      >
        <div className="absolute inset-0 -z-10 overflow-hidden pointer-events-none" aria-hidden="true">
          <div className="chat-aurora" />
        </div>

        {/* Top bar */}
        <header className="h-14 shrink-0 flex items-center gap-3 px-3 sm:px-6 border-b border-line bg-[var(--header-bg)] backdrop-blur-xl z-10">
          <button onClick={() => setSidebarOpen(true)} className="icon-btn md:hidden" aria-label="Open sidebar">
            <Menu size={19} />
          </button>
          <div className="flex-1 min-w-0 flex items-center gap-3">
            <h1 className="truncate text-sm sm:text-[15px] font-semibold text-fg">
              {currentSession?.title || 'New conversation'}
            </h1>
            <span className="hidden sm:inline-flex items-center gap-1.5 shrink-0 px-2.5 py-1 rounded-full text-[11px] font-medium text-accent bg-accent-soft">
              <span className="w-1.5 h-1.5 rounded-full bg-gradient-to-br from-fill-1 to-fill-2" />
              Socratic mode
            </span>
          </div>
          <ThemeSwitcher />
        </header>

        {dragging && (
          <div className="absolute inset-0 z-20 m-3 rounded-3xl border-2 border-dashed border-accent bg-accent-soft backdrop-blur-sm flex items-center justify-center pointer-events-none">
            <div className="flex flex-col items-center gap-2 text-accent font-medium">
              <ImagePlus size={32} />
              Drop images or documents to attach
            </div>
          </div>
        )}

        {/* Messages */}
        <div ref={scrollRef} onScroll={handleScroll} className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 py-8 space-y-7">
            {messages.length === 0 ? (
              <div className="min-h-[58vh] flex flex-col items-center justify-center text-center">
                <div className="hero-orb hero-orb-logo mb-8 animate-fade-up">
                  <LogoMark className="w-full h-full" />
                </div>
                <h3 className="font-display text-[2rem] sm:text-[2.6rem] leading-tight text-fg animate-fade-up" style={{ animationDelay: '60ms' }}>
                  {greeting()}{firstName ? ',' : ''}{' '}
                  {firstName && <span className="gradient-text italic">{firstName}</span>}
                </h3>
                <p className="mt-3 text-muted max-w-md animate-fade-up" style={{ animationDelay: '120ms' }}>
                  What are you curious about today? I won't just hand you answers. I'll ask the questions that get you there.
                </p>
                <div className="mt-10 grid sm:grid-cols-2 gap-3 w-full max-w-2xl">
                  {SUGGESTIONS.map(({ icon: Icon, tag, text }, i) => (
                    <button
                      key={text}
                      onClick={() => { setInputValue(text); textareaRef.current?.focus(); }}
                      className="suggestion-card animate-fade-up"
                      style={{ animationDelay: `${180 + i * 60}ms` }}
                    >
                      <span className="flex items-center justify-center w-9 h-9 shrink-0 rounded-xl bg-accent-soft text-accent">
                        <Icon size={17} />
                      </span>
                      <span className="min-w-0">
                        <span className="block text-[10.5px] font-semibold uppercase tracking-[0.14em] text-faint">{tag}</span>
                        <span className="block mt-0.5 text-sm font-medium text-fg">{text}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, index) => {
                // Continued chat: the checkpoint context opens the conversation
                if (msg.role === 'system') {
                  return (
                    <div key={msg.id} className="flex justify-center animate-fade-up">
                      <div className="w-full max-w-md flex items-center gap-3 rounded-2xl border border-dashed border-line-strong bg-surface px-4 py-3">
                        <span className="flex items-center justify-center w-9 h-9 shrink-0 rounded-xl bg-accent-soft text-accent">
                          <History size={17} />
                        </span>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-semibold text-fg">Continued from a checkpoint</p>
                          <p className="text-xs text-faint">The tutor remembers where you left off.</p>
                        </div>
                        <button onClick={() => setViewingContext(msg.content)} className="text-xs font-semibold text-accent hover:underline shrink-0">
                          View summary
                        </button>
                      </div>
                    </div>
                  );
                }
                const hasList = !!(msg.attachments?.length || msg.local_attachments?.length);
                const hasImage = !hasList && !!(msg.local_image_url || msg.image_mime_type);
                const level = hintLevel(msg.kind);
                const isAnswer = msg.kind === 'answer';

                // Hint / answer requests show as a compact pill, not a chat bubble
                if (msg.role === 'user' && (isHintKind(msg.kind) || isAnswer)) {
                  return (
                    <div key={msg.id} className="flex justify-end animate-fade-up">
                      <span className={`help-pill ${isAnswer ? 'help-pill-answer' : ''}`}>
                        {isAnswer ? <Eye size={13} /> : <Lightbulb size={13} />}
                        {isAnswer ? 'Asked for the full answer' : level ? `Asked for hint ${level} of ${hintTotalOf(msg)}` : 'Asked for a hint'}
                      </span>
                    </div>
                  );
                }

                return msg.role === 'user' ? (
                  <div key={msg.id} className="flex flex-col items-end gap-1.5 animate-fade-up">
                    {hasImage && (
                      <AuthImage
                        messageId={msg.local_image_url ? undefined : msg.id}
                        localUrl={msg.local_image_url}
                        fetcher={fetchStudentImage}
                        className="max-w-[85%] sm:max-w-[65%] ring-1 ring-line shadow-xl"
                      />
                    )}
                    {hasList && (
                      <MessageAttachments attachments={msg.attachments} local={msg.local_attachments} fetcher={fetchAttachment} />
                    )}
                    {!hasList && (msg.document_name || msg.local_document) && (
                      <DocumentCard
                        name={msg.document_name || msg.local_document!.name}
                        mime={msg.document_mime_type || msg.local_document!.mime}
                        size={msg.document_size_bytes ?? msg.local_document!.size}
                        messageId={msg.document_name ? msg.id : undefined}
                        fetcher={fetchStudentDocument}
                        className="max-w-[85%] sm:max-w-[22rem]"
                      />
                    )}
                    {msg.content && (
                      <div className="msg-user max-w-[85%] sm:max-w-[72%] rounded-[22px] rounded-br-md px-4 py-3 text-[15px] leading-relaxed whitespace-pre-wrap break-words">
                        {msg.content}
                      </div>
                    )}
                    <div className="pr-1 flex items-center gap-2">
                      {(() => {
                        // Checkpoint button only for completed student turns (reply saved on the server)
                        const reply = messages[index + 1];
                        if (!msg.content || msg.kind || !reply || reply.role !== 'assistant' || reply.streaming || /^\d+$/.test(reply.id)) return null;
                        if (sessionCheckpoints.some(c => c.message_id === reply.id)) return null;
                        const busy = creatingCp === msg.id;
                        return (
                          <button
                            type="button"
                            onClick={() => handleCreateCheckpoint(msg.id, reply.id)}
                            disabled={!!creatingCp || loading}
                            className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10.5px] text-faint hover:text-fg hover:bg-surface-2 disabled:opacity-50 transition-colors"
                            title="Save a summary of the conversation up to this point"
                          >
                            {busy ? <Loader2 size={11} className="animate-spin" /> : <BookmarkPlus size={11} />}
                            {busy ? 'Creating checkpoint...' : 'Create checkpoint'}
                          </button>
                        );
                      })()}
                      <span className="text-[10.5px] text-faint">{clockTime(msg.timestamp)}</span>
                    </div>
                    {cpError?.id === msg.id && (
                      <span className="pr-1 text-[11px] text-[var(--danger-fg)]">{cpError.text}</span>
                    )}
                  </div>
                ) : (
                  <div key={msg.id} className="group flex gap-3 sm:gap-4 animate-fade-up">
                    <LogoMark className="w-8 h-8 shrink-0 mt-7" />
                    <div className="min-w-0 flex-1 max-w-[88%]">
                      <div className="flex items-center gap-2 mb-1.5 pl-1">
                        <span className="text-[13px] font-semibold text-fg">Socratic Tutor</span>
                        {level > 0 && (
                          <span className="help-badge">
                            <Lightbulb size={11} /> Hint {level} of {hintTotalOf(msg)} · {hintStage(level, hintTotalOf(msg))}
                          </span>
                        )}
                        {isAnswer && (
                          <span className="help-badge help-badge-answer">
                            <Eye size={11} /> Full answer
                          </span>
                        )}
                        <span className="text-[10.5px] text-faint">{clockTime(msg.timestamp)}</span>
                      </div>
                      <div className={`msg-tutor ${level ? 'msg-hint' : ''} ${isAnswer ? 'msg-answer' : ''} rounded-[22px] rounded-tl-md px-5 py-4 text-[15px] leading-7 break-words`} aria-live={msg.streaming ? 'polite' : undefined}>
                        {msg.streaming && !msg.content ? (
                          <span className="inline-flex items-center gap-3 text-sm text-muted">
                            <span className="flex gap-1">
                              <span className="typing-dot" />
                              <span className="typing-dot" />
                              <span className="typing-dot" />
                            </span>
                            <span className="shimmer-text font-medium">
                              {isAnswer ? 'Writing out the full answer...' : level || msg.kind === 'hint-0' ? 'Preparing a hint for you...' : 'Thinking of a good question...'}
                            </span>
                          </span>
                        ) : (
                          <>
                            <Markdown text={msg.content} />
                            {msg.streaming && <span className="stream-cursor" aria-hidden="true" />}
                          </>
                        )}
                      </div>
                      <div className={`mt-1.5 pl-1 flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ${msg.streaming ? 'hidden' : ''}`}>
                        <button
                          onClick={() => copyMessage(msg)}
                          className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11.5px] text-faint hover:text-fg hover:bg-surface-2 transition-colors"
                        >
                          {copiedId === msg.id ? <Check size={13} className="text-accent" /> : <Copy size={13} />}
                          {copiedId === msg.id ? 'Copied' : 'Copy'}
                        </button>
                      </div>
                      {sessionCheckpoints.filter(c => c.message_id === msg.id).slice(-1).map(cp => (
                        <div key={cp.id} className="mt-1 pl-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] animate-fade-up">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-accent-soft text-accent font-semibold">
                            <BookmarkCheck size={12} />
                            {cp.source === 'automatic' ? 'Auto checkpoint' : 'Checkpoint saved'}
                          </span>
                          <button onClick={() => setViewingCp(cp)} className="text-muted hover:text-fg hover:underline">View summary</button>
                          <button onClick={() => handleContinue(cp)} disabled={continuing} className="text-muted hover:text-fg hover:underline disabled:opacity-50">
                            Continue from checkpoint
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })
            )}
            {loading && !messages.some(m => m.streaming) && (
              <div className="flex gap-3 sm:gap-4 animate-fade-up">
                <LogoMark className="w-8 h-8 shrink-0 mt-7" />
                <div>
                  <div className="mb-1.5 pl-1 text-[13px] font-semibold text-fg">Socratic Tutor</div>
                  <div className="msg-tutor inline-flex items-center gap-3 rounded-[22px] rounded-tl-md px-5 py-4 text-sm">
                    <span className="flex gap-1">
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                      <span className="typing-dot" />
                    </span>
                    <span className="shimmer-text font-medium">
                      {(() => {
                        const pending = messages[messages.length - 1]?.kind;
                        if (pending === 'answer') return 'Writing out the full answer...';
                        if (isHintKind(pending)) return 'Preparing a hint for you...';
                        return 'Thinking of a good question...';
                      })()}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Jump to latest */}
        {showJump && (
          <button
            onClick={() => scrollToBottom()}
            className="absolute left-1/2 -translate-x-1/2 bottom-36 z-10 inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full text-xs font-medium text-fg bg-elev border border-line shadow-lg hover:shadow-xl transition-shadow animate-fade-up"
          >
            <ArrowDown size={14} /> Latest
          </button>
        )}

        {/* Composer */}
        <div className="shrink-0 px-3 sm:px-6 pb-4 sm:pb-6 pt-2">
          <div className="max-w-3xl mx-auto">
            {error && (
              <div className="alert-error mb-3 animate-fade-up" role="alert">
                <AlertCircle size={16} className="mt-0.5 shrink-0" />
                <span className="flex-1">{error}</span>
                <button onClick={() => setError('')} aria-label="Dismiss"><X size={15} /></button>
              </div>
            )}
            {hasQuestion && (
              <div className="mb-2.5 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() => askTutor('hint')}
                  disabled={loading || !hintsLeft}
                  className="help-action"
                  title={!hintsLeft ? 'All hints used. Try a step yourself first.' : ladderActive ? `Hint ${nextHint} of ${hintTotal}: ${hintStage(nextHint, hintTotal)}` : 'Get a hint tailored to this question'}
                >
                  <Lightbulb size={15} className="text-[var(--gold)]" />
                  {hintsLeft ? 'Give me a hint' : 'All hints used'}
                  {ladderActive && (
                    <span className="flex gap-1 ml-0.5" aria-label={`${hintsUsed} of ${hintTotal} hints used`}>
                      {Array.from({ length: hintTotal }, (_, i) => (
                        <span key={i} className={`w-1.5 h-1.5 rounded-full ${i < hintsUsed ? 'bg-[var(--gold)]' : 'bg-[var(--border-strong)]'}`} />
                      ))}
                    </span>
                  )}
                  {ladderActive && hintsLeft && (
                    <span className="hidden sm:inline text-faint font-normal">· {hintStage(nextHint, hintTotal)}</span>
                  )}
                </button>
                {allowAnswer && (
                  <button
                    type="button"
                    onClick={handleAnswerClick}
                    disabled={loading}
                    className={`help-action ${confirmAnswer ? 'help-action-armed' : ''}`}
                  >
                    <Eye size={15} />
                    {confirmAnswer ? 'Tap again to reveal the answer' : 'Show answer'}
                  </button>
                )}
              </div>
            )}
            <form onSubmit={handleSendMessage} className="composer rounded-[26px]">
              {pending.length > 0 && (
                <div className="px-3 pt-2.5">
                  <p className="px-1 pb-1 text-[11px] text-faint" aria-live="polite">
                    {pending.length} of {MAX_ATTACHMENTS} files · {formatBytes(pendingBytes)} of {formatBytes(MAX_TOTAL_ATTACHMENT_BYTES)}
                  </p>
                  <ul className="flex gap-2 overflow-x-auto pt-2 pr-2 pb-1 max-h-32" aria-label="Files to send">
                    {pending.map(p => (
                      <li key={p.id} className="shrink-0">
                        {p.kind === 'image' ? (
                          <div className="relative w-48 flex items-center gap-2.5 pr-3 rounded-2xl bg-surface border border-line">
                            <img src={p.previewUrl} alt="" className="h-14 w-14 object-cover rounded-2xl" />
                            <span className="min-w-0 text-xs">
                              <span className="block font-medium text-fg truncate" title={p.file.name}>{p.file.name}</span>
                              <span className="text-faint">Image · {formatBytes(p.file.size)}</span>
                            </span>
                            <button
                              type="button"
                              onClick={() => removePending(p.id)}
                              className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-fg text-bg flex items-center justify-center shadow-md"
                              aria-label={`Remove ${p.file.name}`}
                            >
                              <X size={13} />
                            </button>
                          </div>
                        ) : (
                          <div className="w-64">
                            <DocumentCard name={p.file.name} mime={p.file.type} size={p.file.size} onRemove={() => removePending(p.id)} />
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="flex items-end gap-1.5 p-2">
                <input
                  ref={docInputRef}
                  type="file"
                  accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                  className="hidden"
                  multiple
                  onChange={onFilesChosen}
                />
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  className="hidden"
                  multiple
                  onChange={onFilesChosen}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!currentSessionId || loading}
                  className="icon-btn !w-10 !h-10 !rounded-2xl shrink-0 disabled:opacity-40"
                  title="Attach images (JPG, PNG, WebP · up to 5 MB each)"
                  aria-label="Attach images"
                >
                  <ImagePlus size={19} />
                </button>
                <button
                  type="button"
                  onClick={() => docInputRef.current?.click()}
                  disabled={!currentSessionId || loading}
                  className="icon-btn !w-10 !h-10 !rounded-2xl shrink-0 -ml-1.5 disabled:opacity-40"
                  title="Attach documents (PDF, DOCX, TXT · up to 10 MB each)"
                  aria-label="Attach documents"
                >
                  <Paperclip size={18} />
                </button>
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onPaste={handlePaste}
                  placeholder={pending.length ? `Ask something about ${pending.length > 1 ? 'these files' : 'this file'} (optional)...` : 'Ask anything, or share how you are thinking about it...'}
                  disabled={!currentSessionId || loading}
                  className="flex-1 resize-none bg-transparent px-2 py-2.5 text-[15px] leading-6 text-fg placeholder:text-faint focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-[200px]"
                />
                <button
                  type="submit"
                  disabled={!canSend}
                  className="btn-primary !p-0 !w-10 !h-10 !rounded-2xl shrink-0"
                  aria-label="Send message"
                >
                  <ArrowUp size={19} strokeWidth={2.5} />
                </button>
              </div>
            </form>
            <p className="mt-2.5 hidden sm:flex items-center justify-center gap-1.5 text-[11px] text-faint">
              <span className="kbd">Enter</span> send
              <span className="mx-1">·</span>
              <span className="kbd">Shift</span>+<span className="kbd">Enter</span> new line
              <span className="mx-1">·</span>
              paste images or drop files (up to 5)
            </p>
          </div>
        </div>
      </main>

      {(viewingCp || viewingContext) && (
        <CheckpointModal
          checkpoint={viewingCp}
          contextText={viewingContext}
          onClose={() => { setViewingCp(null); setViewingContext(null); }}
          onContinue={viewingCp ? () => handleContinue(viewingCp) : undefined}
          continuing={continuing}
        />
      )}
    </div>
  );
}
