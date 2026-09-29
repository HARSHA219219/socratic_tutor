/**
 * Focused validation for streaming chat (no test framework needed; Node 22.6+ runs TS directly):
 *   npm run check:streaming
 */
import assert from 'node:assert/strict';
import { createSseParser } from '../src/services/sse.ts';
import { startStream, applySavedUser, appendChunk, completeStream, failStream, streamingId } from '../src/services/chatStream.ts';
import type { Message } from '../src/types/api';

let passed = 0;
const check = (name: string, fn: () => void) => {
  fn();
  passed++;
  console.log(`  ok  ${name}`);
};

// ---------- SSE parsing ----------

check('parses events split across network chunks', () => {
  const got: string[] = [];
  const p = createSseParser(d => got.push(d));
  for (const piece of ['data: {"type":"chunk","te', 'xt":"Hel', 'lo"}\n', '\ndata: {"type":"chunk","text":" there"}\n\nda', 'ta: [DONE]\n\n']) {
    p.push(piece);
  }
  assert.deepEqual(got, ['{"type":"chunk","text":"Hello"}', '{"type":"chunk","text":" there"}', '[DONE]']);
});

check('handles CRLF line endings split between chunks', () => {
  const got: string[] = [];
  const p = createSseParser(d => got.push(d));
  p.push('data: {"type":"start"}\r');
  p.push('\n\r\ndata: [DONE]\r\n\r\n');
  assert.deepEqual(got, ['{"type":"start"}', '[DONE]']);
});

check('emits nothing until the blank line arrives, then flushes on end()', () => {
  const got: string[] = [];
  const p = createSseParser(d => got.push(d));
  p.push('data: {"type":"chunk","text":"partial"}');
  assert.equal(got.length, 0);
  p.end();
  assert.deepEqual(got, ['{"type":"chunk","text":"partial"}']);
});

check('keeps spaces inside chunk text', () => {
  const got: string[] = [];
  const p = createSseParser(d => got.push(d));
  p.push('data: {"type":"chunk","text":"  two spaces"}\n\n');
  assert.equal(JSON.parse(got[0]).text, '  two spaces');
});

// ---------- message state while streaming ----------

const msg = (over: Partial<Message>): Message => ({
  id: 'x', session_id: 's1', role: 'user', content: '', timestamp: '2026-01-01T00:00:00', ...over,
});
const userTemp = msg({ id: 'local-1', content: 'Why is the sky blue?' });
const tempAssistant = streamingId(userTemp.id);

check('text is appended progressively and the reply is marked streaming', () => {
  let state = startStream([msg({ id: 'old', role: 'assistant', content: 'Hi' })], userTemp, tempAssistant, null);
  assert.equal(state.length, 3);
  assert.equal(state[2].streaming, true);
  const seen: string[] = [];
  for (const piece of ['Light ', 'scatters ', 'in air.']) {
    state = appendChunk(state, tempAssistant, piece);
    seen.push(state[2].content);
  }
  assert.deepEqual(seen, ['Light ', 'Light scatters ', 'Light scatters in air.']);
});

check('completion clears streaming and swaps in the saved messages (no duplicates)', () => {
  let state = startStream([], userTemp, tempAssistant, null);
  state = applySavedUser(state, userTemp.id, tempAssistant, msg({ id: 'u-srv', content: userTemp.content }));
  state = appendChunk(state, tempAssistant, 'Light scatters.');
  const saved = {
    user_message: msg({ id: 'u-srv', content: userTemp.content }),
    assistant_message: msg({ id: 'a-srv', role: 'assistant', content: 'Light scatters.' }),
  };
  state = completeStream(state, userTemp.id, tempAssistant, saved);
  assert.deepEqual(state.map(m => m.id), ['u-srv', 'a-srv']);
  assert.equal(state[1].streaming, false);
  // A repeated completion (e.g. a retry) must not add a second reply
  state = completeStream(state, userTemp.id, tempAssistant, saved);
  assert.equal(state.filter(m => m.role === 'assistant').length, 1);
});

check('hint request picks up its level while streaming', () => {
  const hintTemp = msg({ id: 'help-1', kind: 'hint-0' });
  const tempId = streamingId(hintTemp.id);
  let state = startStream([], hintTemp, tempId, 'hint-0');
  state = applySavedUser(state, hintTemp.id, tempId, msg({ id: 'h-srv', kind: 'hint-2', hint_total: 4 }));
  assert.equal(state[1].kind, 'hint-2');
  assert.equal(state[1].hint_total, 4);
});

check('failure before the server saved anything removes both temporary messages', () => {
  const state = failStream(startStream([msg({ id: 'old' })], userTemp, tempAssistant, null), userTemp.id, tempAssistant);
  assert.deepEqual(state.map(m => m.id), ['old']);
});

check('failure after the student message was saved keeps it and drops only the partial reply', () => {
  let state = startStream([], userTemp, tempAssistant, null);
  state = applySavedUser(state, userTemp.id, tempAssistant, msg({ id: 'u-srv', content: userTemp.content }));
  state = appendChunk(state, tempAssistant, 'Half an ans');
  state = failStream(state, userTemp.id, tempAssistant);
  assert.deepEqual(state.map(m => m.id), ['u-srv']);
  assert.equal(state.some(m => m.streaming), false);
});

console.log(`\n${passed} streaming checks passed`);
