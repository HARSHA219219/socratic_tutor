/**
 * Pure helpers that update the chat's message list while a tutor reply streams in.
 * Kept free of React so they can be validated on their own (scripts/check-streaming.ts).
 */
import type { Message } from '../types/api';

export const streamingId = (base: string) => `streaming-${base}`;

/** Adds the student's optimistic message (if any) and an empty, streaming tutor message. */
export function startStream(messages: Message[], userTemp: Message | null, assistantTempId: string, kind?: string | null): Message[] {
  const placeholder: Message = {
    id: assistantTempId,
    session_id: userTemp?.session_id ?? '',
    role: 'assistant',
    content: '',
    timestamp: new Date().toISOString(),
    kind: kind ?? null,
    streaming: true,
  };
  return [...messages, ...(userTemp ? [userTemp] : []), placeholder];
}

/** The server saved the student's message: swap the optimistic copy for it (keeping local previews). */
export function applySavedUser(messages: Message[], tempUserId: string, assistantTempId: string, saved: Message): Message[] {
  return messages.map(m => {
    if (m.id === tempUserId) return { ...saved, local_image_url: m.local_image_url, local_attachments: m.local_attachments, local_document: undefined };
    // Hints: the level/total are only known once the planner ran
    if (m.id === assistantTempId && saved.kind) return { ...m, kind: saved.kind, hint_total: saved.hint_total };
    return m;
  });
}

/** Appends one streamed piece of text to the tutor message. */
export function appendChunk(messages: Message[], assistantTempId: string, text: string): Message[] {
  return messages.map(m => (m.id === assistantTempId ? { ...m, content: m.content + text } : m));
}

/** Replaces the temporary messages with the persisted ones; never leaves two copies of the reply. */
export function completeStream(
  messages: Message[],
  tempUserId: string,
  assistantTempId: string,
  saved: { user_message: Message; assistant_message: Message },
): Message[] {
  const alreadyThere = messages.some(m => m.id === saved.assistant_message.id);
  return messages
    .filter(m => !(alreadyThere && m.id === assistantTempId))
    .map(m => {
      if (m.id === tempUserId) return { ...saved.user_message, local_image_url: m.local_image_url, local_attachments: m.local_attachments };
      if (m.id === assistantTempId) return { ...saved.assistant_message, streaming: false };
      return m;
    });
}

/**
 * Streaming failed: drop the unfinished tutor message. The optimistic student message is
 * removed too unless the server had already saved it (it was replaced by then).
 */
export function failStream(messages: Message[], tempUserId: string, assistantTempId: string): Message[] {
  return messages.filter(m => m.id !== assistantTempId && m.id !== tempUserId);
}
