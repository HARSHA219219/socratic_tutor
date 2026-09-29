import React from 'react';
import type { Attachment, LocalAttachment } from '../types/api';
import AuthImage from './AuthImage';
import DocumentCard from './DocumentCard';

type Item = {
  key: string;
  id?: string;
  kind: 'image' | 'document';
  name: string;
  mime: string;
  size: number;
  localUrl?: string;
  summary?: string | null;
  summaryStatus?: string | null;
  textStatus?: string | null;
};

/**
 * Every file on a message: images (with the tutor's saved description) and document cards.
 * Kept compact and scrollable so several attachments don't crowd out the conversation.
 */
const MessageAttachments: React.FC<{
  attachments?: Attachment[];
  local?: LocalAttachment[];
  fetcher: (attachmentId: string) => Promise<Blob>;
  align?: 'start' | 'end';
  /** Instructor view: document extraction status and description failures */
  showStatus?: boolean;
}> = ({ attachments, local, fetcher, align = 'end', showStatus = false }) => {
  const items: Item[] = attachments?.length
    ? attachments.map((a, i) => ({
        key: a.id,
        id: a.id,
        kind: a.kind,
        name: a.name || (a.kind === 'image' ? 'image' : 'document'),
        mime: a.mime_type,
        size: a.size_bytes,
        // Keep showing the local preview right after sending (same order as uploaded)
        localUrl: local?.[i]?.previewUrl,
        summary: a.summary_status === 'ok' ? a.image_summary : null,
        summaryStatus: a.summary_status,
        textStatus: a.text_status,
      }))
    : (local || []).map((l, i) => ({ key: `local-${i}`, kind: l.kind, name: l.name, mime: l.mime, size: l.size, localUrl: l.previewUrl }));
  if (!items.length) return null;

  const images = items.filter(i => i.kind === 'image');
  const docs = items.filter(i => i.kind === 'document');
  const end = align === 'end';

  return (
    <div className={`flex flex-col gap-2 w-full max-h-[28rem] overflow-y-auto ${end ? 'items-end' : 'items-start'}`}>
      {images.length > 0 && (
        <div className={`flex flex-wrap gap-2 max-w-[92%] sm:max-w-[80%] ${end ? 'justify-end' : ''}`}>
          {images.map((img, n) => (
            <figure key={img.key} className={images.length > 1 ? 'w-[calc(50%-0.25rem)] sm:w-44' : 'max-w-full'}>
              <AuthImage
                messageId={img.localUrl ? undefined : img.id}
                localUrl={img.localUrl}
                fetcher={fetcher}
                className="ring-1 ring-line shadow-lg"
                imgClassName={images.length > 1 ? 'h-32 w-full object-cover' : undefined}
                alt={`Image ${n + 1}: ${img.name}`}
              />
              <figcaption className="mt-1 px-0.5 text-[10.5px] text-faint truncate" title={img.name}>{img.name}</figcaption>
              {img.summary && (
                <details className="mt-0.5 px-0.5 text-[11px] text-faint">
                  <summary className="cursor-pointer select-none hover:text-fg">What the tutor noted</summary>
                  <p className="mt-1 text-muted leading-relaxed whitespace-pre-wrap">{img.summary}</p>
                </details>
              )}
              {showStatus && img.summaryStatus === 'failed' && (
                <p className="mt-0.5 px-0.5 text-[10.5px] text-faint">No description; the original is re-sent instead.</p>
              )}
            </figure>
          ))}
        </div>
      )}
      {docs.map(d => (
        <DocumentCard
          key={d.key}
          name={d.name}
          mime={d.mime}
          size={d.size}
          messageId={d.id}
          fetcher={d.id ? fetcher : undefined}
          textStatus={d.textStatus}
          showStatus={showStatus}
          className="max-w-[85%] sm:max-w-[22rem]"
        />
      ))}
    </div>
  );
};

export default MessageAttachments;
