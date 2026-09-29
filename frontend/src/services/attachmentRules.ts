/**
 * Client-side attachment rules. They mirror the backend settings (MAX_ATTACHMENTS_PER_MESSAGE,
 * MAX_TOTAL_ATTACHMENT_BYTES, MAX_IMAGE_BYTES, MAX_DOCUMENT_BYTES); the server re-checks
 * everything, including the context-budget limit that can't be computed here.
 */
export const MAX_ATTACHMENTS = 5;
export const MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const MAX_DOCUMENT_BYTES = 10 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const DOCUMENT_EXTENSIONS = ['.pdf', '.docx', '.txt'];

export type AttachmentKind = 'image' | 'document';

/** The parts of a File the rules need (keeps them testable without a browser). */
export interface FileLike {
  name: string;
  size: number;
  type: string;
}

const mb = (bytes: number) => `${bytes / (1024 * 1024)} MB`;

export function classifyFile(file: FileLike): AttachmentKind | null {
  if (ACCEPTED_IMAGE_TYPES.includes(file.type)) return 'image';
  const lower = file.name.toLowerCase();
  if (DOCUMENT_EXTENSIONS.some(ext => lower.endsWith(ext))) return 'document';
  return null;
}

/**
 * Which of `incoming` can be added to `current`, and a readable error for each one that can't.
 * Accepted files keep their order; a rejected file never blocks the others.
 */
export function checkNewFiles<T extends FileLike>(current: FileLike[], incoming: T[]): { accepted: T[]; errors: string[] } {
  const accepted: T[] = [];
  const errors: string[] = [];
  let count = current.length;
  let total = current.reduce((sum, f) => sum + f.size, 0);
  let countErrorShown = false;

  for (const file of incoming) {
    const kind = classifyFile(file);
    if (!kind) {
      errors.push(`"${file.name}": unsupported file type. Attach JPG, PNG or WebP images, or PDF, DOCX or TXT files.`);
      continue;
    }
    if (file.size === 0) {
      errors.push(`"${file.name}" is empty.`);
      continue;
    }
    const limit = kind === 'image' ? MAX_IMAGE_BYTES : MAX_DOCUMENT_BYTES;
    if (file.size > limit) {
      errors.push(`"${file.name}" is too large (max ${mb(limit)} for ${kind === 'image' ? 'images' : 'documents'}).`);
      continue;
    }
    if (count >= MAX_ATTACHMENTS) {
      if (!countErrorShown) errors.push(`You can attach up to ${MAX_ATTACHMENTS} files per message.`);
      countErrorShown = true;
      continue;
    }
    if (total + file.size > MAX_TOTAL_ATTACHMENT_BYTES) {
      errors.push(`"${file.name}" would make the attachments larger than ${mb(MAX_TOTAL_ATTACHMENT_BYTES)} in total.`);
      continue;
    }
    accepted.push(file);
    count += 1;
    total += file.size;
  }
  return { accepted, errors };
}

export const formatBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1024 * 1024 ? `${Math.round(n / 1024)} KB` : `${(n / (1024 * 1024)).toFixed(1)} MB`;
