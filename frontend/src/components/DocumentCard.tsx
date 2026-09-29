import React, { useState } from 'react';
import { FileText, FileType2, FileCode2, Download, ExternalLink, Loader2, X, AlertCircle } from 'lucide-react';

const formatBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / (1024 * 1024)).toFixed(1)} MB`;

const typeInfo = (mime: string, name: string) => {
  const lower = name.toLowerCase();
  if (mime === 'application/pdf' || lower.endsWith('.pdf')) return { label: 'PDF', icon: FileType2, viewable: true };
  if (mime.includes('wordprocessingml') || lower.endsWith('.docx')) return { label: 'DOCX', icon: FileText, viewable: false };
  return { label: 'TXT', icon: FileCode2, viewable: true };
};

/**
 * A document attachment: name, type, size and (for saved documents) View/Download actions.
 * Files are fetched with the bearer token, so plain links can't be used.
 */
const DocumentCard: React.FC<{
  name: string;
  mime: string;
  size: number;
  messageId?: string;
  fetcher?: (id: string) => Promise<Blob>;
  textStatus?: string | null;
  showStatus?: boolean;
  onRemove?: () => void;
  className?: string;
}> = ({ name, mime, size, messageId, fetcher, textStatus, showStatus, onRemove, className = '' }) => {
  const { label, icon: Icon, viewable } = typeInfo(mime, name);
  const [busy, setBusy] = useState<'view' | 'download' | null>(null);
  const [failed, setFailed] = useState(false);

  const open = async (mode: 'view' | 'download') => {
    if (!messageId || !fetcher) return;
    // Open the tab synchronously so pop-up blockers allow it
    const tab = mode === 'view' ? window.open('', '_blank') : null;
    setBusy(mode);
    setFailed(false);
    try {
      const blob = await fetcher(messageId);
      const url = URL.createObjectURL(blob);
      if (tab) {
        tab.location.href = url;
      } else {
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        a.click();
      }
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      tab?.close();
      setFailed(true);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={`doc-card ${className}`}>
      <span className="doc-card-icon">
        <Icon size={20} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-fg truncate" title={name}>{name}</p>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-faint">
          <span className="font-semibold text-muted">{label}</span>
          <span>·</span>
          <span>{formatBytes(size)}</span>
          {showStatus && textStatus && (
            <>
              <span>·</span>
              <span className={textStatus === 'ok' ? 'text-[var(--live-fg)]' : 'text-[var(--gold)]'}>
                {textStatus === 'truncated' ? 'Text extracted (shortened)'
                  : textStatus === 'image' ? 'No text layer · read as page images'
                  : 'Text extracted'}
              </span>
            </>
          )}
          {failed && (
            <span className="inline-flex items-center gap-1 text-[var(--danger-fg)]">
              <AlertCircle size={11} /> Unavailable
            </span>
          )}
        </p>
      </div>
      {messageId && fetcher && (
        <div className="flex items-center gap-0.5 shrink-0">
          {viewable && (
            <button type="button" onClick={() => open('view')} className="icon-btn !w-8 !h-8" title="View" aria-label={`View ${name}`}>
              {busy === 'view' ? <Loader2 size={15} className="animate-spin" /> : <ExternalLink size={15} />}
            </button>
          )}
          <button type="button" onClick={() => open('download')} className="icon-btn !w-8 !h-8" title="Download" aria-label={`Download ${name}`}>
            {busy === 'download' ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
          </button>
        </div>
      )}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-fg text-bg flex items-center justify-center shadow-md"
          aria-label="Remove attachment"
        >
          <X size={13} />
        </button>
      )}
    </div>
  );
};

export default DocumentCard;
