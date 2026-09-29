import React, { useEffect, useState } from 'react';
import { ImageOff, Loader2, X } from 'lucide-react';

/**
 * Displays a chat image that requires a bearer token (so a plain <img src> can't be used).
 * Click to view full size.
 */
const AuthImage: React.FC<{
  messageId?: string;
  fetcher?: (id: string) => Promise<Blob>;
  localUrl?: string;
  className?: string;
  /** Classes for the <img> itself (e.g. fixed-height thumbnails in a grid) */
  imgClassName?: string;
  alt?: string;
}> = ({ messageId, fetcher, localUrl, className = '', imgClassName, alt = 'Attached by student' }) => {
  const [url, setUrl] = useState<string | null>(localUrl ?? null);
  const [failed, setFailed] = useState(false);
  const [zoom, setZoom] = useState(false);

  useEffect(() => {
    if (localUrl || !messageId || !fetcher) return;
    let objectUrl: string | null = null;
    let cancelled = false;
    fetcher(messageId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => !cancelled && setFailed(true));
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [messageId, fetcher, localUrl]);

  if (failed) {
    return (
      <div className={`flex items-center gap-2 px-4 py-6 rounded-xl bg-surface text-faint text-sm ${className}`}>
        <ImageOff size={16} /> Image unavailable
      </div>
    );
  }
  if (!url) {
    return (
      <div className={`flex items-center justify-center ${imgClassName ? 'w-full h-32' : 'w-56 h-40'} rounded-xl bg-surface text-faint ${className}`}>
        <Loader2 size={18} className="animate-spin" />
      </div>
    );
  }
  return (
    <>
      <button type="button" onClick={() => setZoom(true)} className={`block overflow-hidden rounded-xl ${className}`} aria-label={`View ${alt} full size`}>
        <img src={url} alt={alt} className={`${imgClassName ?? 'max-h-72 w-auto max-w-full object-contain'} hover:scale-[1.02] transition-transform`} />
      </button>
      {zoom && (
        <div
          className="fixed inset-0 z-[60] bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-up"
          onClick={() => setZoom(false)}
        >
          <button className="absolute top-4 right-4 icon-btn !text-white hover:!bg-white/10" aria-label="Close">
            <X size={20} />
          </button>
          <img src={url} alt={alt} className="max-w-full max-h-full rounded-xl shadow-2xl" />
        </div>
      )}
    </>
  );
};

export default AuthImage;
